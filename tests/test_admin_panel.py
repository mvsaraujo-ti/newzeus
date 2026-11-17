from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import admin_auth
from app.database.config import Base, get_db
from app.main import app
from app.models import Auditoria, Contato, Unidade, UsuarioAdmin
from app.services.auth_service import hash_senha
from app.services import ramais_service


@pytest.fixture
def panel_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    @asynccontextmanager
    async def no_lifespan(_app):
        yield

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(app.router, "lifespan_context", no_lifespan)
    monkeypatch.setattr(admin_auth, "_tentativas_login", {})
    monkeypatch.setattr(ramais_service, "SessionLocal", factory)

    with factory.begin() as session:
        admin = UsuarioAdmin(
            nome="Admin Painel",
            usuario="admin.painel",
            senha_hash=hash_senha("senha-admin-painel-segura-2026"),
            perfil="administrador",
            ativo=True,
        )
        operator = UsuarioAdmin(
            nome="Operador Painel",
            usuario="operador.painel",
            senha_hash=hash_senha("senha-operador-painel-segura"),
            perfil="operador",
            ativo=True,
        )
        unidade = Unidade(
            nome="4ª Vara Cível",
            categoria="Varas Cíveis",
            comarca="São Luís",
        )
        session.add_all([admin, operator, unidade])
        session.flush()
        session.add(
            Contato(
                unidade_id=unidade.id,
                tipo="ramal",
                valor="2555",
                principal=True,
                ativo=True,
            )
        )
        session.add(
            Auditoria(
                usuario_id=admin.id,
                acao="cadastro",
                entidade="unidade",
                registro_id=unidade.id,
                detalhes='{"depois":{"nome":"4ª Vara Cível"}}',
            )
        )

    with TestClient(app) as client:
        yield client, factory

    app.dependency_overrides.clear()
    engine.dispose()


def login(client, username="admin.painel", password="senha-admin-painel-segura-2026"):
    csrf = client.get("/admin/api/csrf").json()["csrf_token"]
    response = client.post(
        "/admin/api/login",
        json={"usuario": username, "senha": password},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text


def request_as_user(client, method, path, **kwargs):
    csrf = client.get("/admin/api/session").json()["csrf_token"]
    headers = kwargs.pop("headers", {})
    headers["X-CSRF-Token"] = csrf
    return client.request(method, path, headers=headers, **kwargs)


def test_rotas_de_painel_exigem_autenticacao(panel_client):
    client, _ = panel_client

    assert client.get("/admin").status_code == 401
    assert client.get("/admin/api/dashboard").status_code == 401
    assert client.get("/admin/api/units").status_code == 401
    assert client.get("/admin/api/audit").status_code == 401


def test_operador_pode_consultar_criar_editar_mas_nao_admin(panel_client):
    client, _ = panel_client
    login(client, "operador.painel", "senha-operador-painel-segura")

    assert client.get("/admin/api/units").status_code == 200
    dashboard = client.get("/admin/api/dashboard").json()
    assert dashboard["alteracoes_recentes"] == []
    assert dashboard["versao"] == "1.0.0"
    assert dashboard["unidades_inativas"] == 0
    assert dashboard["consultas_registradas"] is None
    assert sum(
        item["unidades"] for item in dashboard["distribuicao_categorias"]
    ) == dashboard["total_unidades"]
    assert sum(
        item["unidades"] for item in dashboard["distribuicao_comarcas"]
    ) == dashboard["total_unidades"]

    criada = request_as_user(
        client,
        "POST",
        "/admin/api/units",
        json={"nome": "Unidade Operacional", "categoria": "Atendimento"},
    )
    assert criada.status_code == 201
    editada = request_as_user(
        client,
        "PATCH",
        f"/admin/api/units/{criada.json()['id']}",
        json={"descricao": "Atualização feita pelo operador"},
    )
    assert editada.status_code == 200

    contato = request_as_user(
        client,
        "POST",
        f"/admin/api/units/{criada.json()['id']}/contacts",
        json={"tipo": "ramal", "valor": "4411", "descricao": "Recepção"},
    )
    assert contato.status_code == 201
    contato_editado = request_as_user(
        client,
        "PATCH",
        f"/admin/api/contacts/{contato.json()['id']}",
        json={"descricao": "Atendimento geral"},
    )
    assert contato_editado.status_code == 200
    assert contato_editado.json()["descricao"] == "Atendimento geral"

    assert request_as_user(
        client,
        "PATCH",
        f"/admin/api/units/{criada.json()['id']}/status",
        json={"ativo": False},
    ).status_code == 403
    assert request_as_user(
        client,
        "POST",
        "/admin/api/units",
        json={"nome": "Unidade Inativa Indevida", "categoria": "Teste", "ativo": False},
    ).status_code == 422
    assert client.get("/admin/api/audit").status_code == 403
    assert client.get("/admin/api/users").status_code == 403
    assert client.post(
        "/admin/api/users",
        json={
            "nome": "Operador Indevido",
            "usuario": "operador.indevido",
            "senha": "senha-indevida-bem-comprida",
            "perfil": "operador",
        },
    ).status_code == 403


def test_admin_cria_edita_filtra_unidade_e_audita(panel_client):
    client, factory = panel_client
    login(client)

    criada = request_as_user(
        client,
        "POST",
        "/admin/api/units",
        json={
            "nome": "Núcleo de Atendimento",
            "categoria": "Apoio",
            "comarca": "Imperatriz",
            "descricao": "Atendimento ao público",
            "contatos": [
                {
                    "tipo": "telefone_fixo",
                    "valor": "(99) 3333-4444",
                    "descricao": "Recepção",
                    "principal": True,
                }
            ],
        },
    )
    assert criada.status_code == 201, criada.text
    unidade = criada.json()
    assert unidade["contatos"][0]["valor"] == "(99) 3333-4444"

    duplicada = request_as_user(
        client,
        "POST",
        "/admin/api/units",
        json={
            "nome": "nucleo de atendimento",
            "categoria": "Apoio",
            "comarca": "Imperatriz",
        },
    )
    assert duplicada.status_code == 409

    editada = request_as_user(
        client,
        "PATCH",
        f"/admin/api/units/{unidade['id']}",
        json={"descricao": "Unidade atualizada"},
    )
    assert editada.status_code == 200
    assert editada.json()["descricao"] == "Unidade atualizada"
    total_auditoria_apos_edicao = len(client.get("/admin/api/audit").json())
    sem_mudanca = request_as_user(
        client,
        "PATCH",
        f"/admin/api/units/{unidade['id']}",
        json={"descricao": "Unidade atualizada"},
    )
    assert sem_mudanca.status_code == 200
    assert len(client.get("/admin/api/audit").json()) == total_auditoria_apos_edicao

    filtrada = client.get(
        "/admin/api/units",
        params={"busca": "Atendimento", "categoria": "Apoio", "comarca": "Imperatriz", "ativo": "true"},
    )
    assert filtrada.status_code == 200
    assert [item["id"] for item in filtrada.json()] == [unidade["id"]]

    with factory() as session:
        registros = session.scalars(
            select(Auditoria).where(Auditoria.entidade == "unidade")
        ).all()
    assert [item.acao for item in registros].count("cadastro") == 2
    assert any(item.acao == "edicao" for item in registros)
    details = client.get("/admin/api/audit").json()
    assert details[0]["detalhes"]["depois"]["descricao"] == "Unidade atualizada"


def test_mesmo_nome_pode_existir_em_comarcas_diferentes(panel_client):
    client, _ = panel_client
    login(client)
    payload = {"nome": "Vara Homônima", "categoria": "Vara Judicial"}

    sao_luis = request_as_user(
        client,
        "POST",
        "/admin/api/units",
        json={**payload, "comarca": "São Luís"},
    )
    balsas = request_as_user(
        client,
        "POST",
        "/admin/api/units",
        json={**payload, "comarca": "Balsas"},
    )
    duplicada_na_mesma_comarca = request_as_user(
        client,
        "POST",
        "/admin/api/units",
        json={**payload, "comarca": "São Luís"},
    )

    assert sao_luis.status_code == 201
    assert balsas.status_code == 201
    assert duplicada_na_mesma_comarca.status_code == 409


def test_administrador_desativa_e_reativa_unidade_e_busca_publica(panel_client):
    client, _ = panel_client
    login(client)
    unit = client.get("/admin/api/units", params={"busca": "4ª Vara Cível"}).json()[0]
    path = f"/admin/api/units/{unit['id']}/status"

    desativada = request_as_user(client, "PATCH", path, json={"ativo": False})
    assert desativada.status_code == 200
    resposta_inativa = client.post(
        "/chat", json={"mensagem": "Qual o ramal da 4ª Vara Cível?"}
    ).json()
    assert resposta_inativa["dados"]["encontrado"] is False

    reativada = request_as_user(client, "PATCH", path, json={"ativo": True})
    assert reativada.status_code == 200
    resposta_ativa = client.post(
        "/chat", json={"mensagem": "Qual o ramal da 4ª Vara Cível?"}
    ).json()
    assert resposta_ativa["dados"]["ramais"] == ["2555"]

    auditoria = client.get("/admin/api/audit").json()
    assert {item["acao"] for item in auditoria} >= {"desativacao", "reativacao"}


def test_contatos_sao_editados_e_excluidos_logicamente_sem_sumir_unidade(panel_client):
    client, factory = panel_client
    login(client)
    unidade = client.get("/admin/api/units", params={"busca": "4ª Vara Cível"}).json()[0]
    with factory() as session:
        auditorias_antes = len(session.scalars(select(Auditoria)).all())

    duplicado = request_as_user(
        client,
        "POST",
        f"/admin/api/units/{unidade['id']}/contacts",
        json={"tipo": "ramal", "valor": "2555"},
    )
    assert duplicado.status_code == 409
    with factory() as session:
        assert len(session.scalars(select(Auditoria)).all()) == auditorias_antes

    criado = request_as_user(
        client,
        "POST",
        f"/admin/api/units/{unidade['id']}/contacts",
        json={
            "tipo": "whatsapp",
            "valor": "+55 98 99999-0000",
            "descricao": "Plantão",
        },
    )
    assert criado.status_code == 201, criado.text
    contato_id = criado.json()["id"]

    editado = request_as_user(
        client,
        "PATCH",
        f"/admin/api/contacts/{contato_id}",
        json={"valor": "+55 98 98888-0000", "descricao": "Atendimento"},
    )
    assert editado.status_code == 200
    assert editado.json()["valor"] == "+55 98 98888-0000"

    email_invalido = request_as_user(
        client,
        "PATCH",
        f"/admin/api/contacts/{contato_id}",
        json={"tipo": "email", "valor": "endereco-invalido"},
    )
    assert email_invalido.status_code == 422

    excluido = request_as_user(client, "DELETE", f"/admin/api/contacts/{contato_id}")
    assert excluido.status_code == 200
    assert excluido.json()["ativo"] is False
    resultado_publico = client.post(
        "/chat", json={"mensagem": "Qual o contato da 4ª Vara Cível?"}
    ).json()["dados"]
    assert resultado_publico["ramais"] == ["2555"]
    assert all(item["valor"] != "+55 98 98888-0000" for item in resultado_publico["contatos"])

    with factory() as session:
        contato = session.get(Contato, contato_id)
        assert contato is not None and contato.ativo is False
        assert session.get(Unidade, unidade["id"]) is not None
        actions = session.scalars(
            select(Auditoria.acao).where(Auditoria.entidade == "contato")
        ).all()
    assert "cadastro" in actions and "edicao" in actions and "exclusao_logica" in actions


def test_admin_gerencia_usuarios_sem_expor_hash_ou_permitir_orfao(panel_client):
    client, factory = panel_client
    login(client)

    usuarios = client.get("/admin/api/users")
    assert usuarios.status_code == 200
    assert all("senha_hash" not in item and "senha" not in item for item in usuarios.json())

    criado = request_as_user(
        client,
        "POST",
        "/admin/api/users",
        json={
            "nome": "Operadora Nova",
            "usuario": "operadora.nova",
            "senha": "senha-nova-operadora-segura",
            "perfil": "operador",
        },
    )
    assert criado.status_code == 201
    assert "senha_hash" not in criado.json()

    alterado = request_as_user(
        client,
        "PATCH",
        f"/admin/api/users/{criado.json()['id']}",
        json={"ativo": False},
    )
    assert alterado.status_code == 200 and alterado.json()["ativo"] is False

    with factory() as session:
        registros = session.scalars(
            select(Auditoria).where(Auditoria.entidade == "usuario")
        ).all()
        assert all("senha_hash" not in item.detalhes for item in registros)
        assert all("senha-nova-operadora-segura" not in item.detalhes for item in registros)

    admin = client.get("/admin/api/users").json()
    admin_id = next(item["id"] for item in admin if item["usuario"] == "admin.painel")
    sem_admin = request_as_user(
        client,
        "PATCH",
        f"/admin/api/users/{admin_id}",
        json={"ativo": False},
    )
    assert sem_admin.status_code == 409


def test_csrf_e_validado_em_alteracoes_de_painel(panel_client):
    client, _ = panel_client
    login(client)

    resposta = client.post(
        "/admin/api/units",
        json={"nome": "Sem CSRF", "categoria": "Teste"},
    )
    assert resposta.status_code == 403


def test_admin_cadastra_edita_e_audita_competencias(panel_client):
    client, _ = panel_client
    login(client)
    criada = request_as_user(
        client,
        "POST",
        "/admin/api/units",
        json={
            "nome": "1ª Vara de Balsas",
            "categoria": "Vara Judicial",
            "comarca": "Balsas",
            "competencias": ["Saúde Pública", "Cível e Comércio"],
            "contatos": [{"tipo": "ramal", "valor": "3201", "principal": True}],
        },
    )
    assert criada.status_code == 201, criada.text
    unidade_id = criada.json()["id"]
    assert set(criada.json()["competencias"]) == {"Saúde Pública", "Cível e Comércio"}

    editada = request_as_user(
        client,
        "PATCH",
        f"/admin/api/units/{unidade_id}",
        json={"competencias": ["Execuções Fiscais"]},
    )
    assert editada.status_code == 200
    assert editada.json()["competencias"] == ["Execuções Fiscais"]

    resultado = client.post(
        "/chat",
        json={"mensagem": "Qual unidade atende execuções fiscais em Balsas?"},
    ).json()["dados"]
    assert resultado["unidade"] == "1ª Vara de Balsas"
    assert resultado["ramais"] == ["3201"]

    antiga = client.post(
        "/chat",
        json={"mensagem": "Qual unidade atende Saúde Pública em Balsas?"},
    ).json()["dados"]
    assert antiga["encontrado"] is False
    auditoria = client.get("/admin/api/audit").json()
    assert any(item["entidade"] == "competencia" for item in auditoria)