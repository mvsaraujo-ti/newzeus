from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import admin_auth
from app.database.config import Base, get_db
from app.main import app
from app.models import UsuarioAdmin
from app.services.auth_service import (
    AdministradorInicialJaExiste,
    criar_primeiro_administrador,
    hash_senha,
    validar_usuario,
)


@pytest.fixture
def auth_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = session_factory()
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

    with session_factory.begin() as session:
        session.add_all(
            [
                UsuarioAdmin(
                    nome="Administradora de Teste",
                    usuario="admin.teste",
                    senha_hash=hash_senha("senha-segura-de-teste-2026"),
                    perfil="administrador",
                    ativo=True,
                ),
                UsuarioAdmin(
                    nome="Operador de Teste",
                    usuario="operador.teste",
                    senha_hash=hash_senha("senha-segura-de-teste-2026"),
                    perfil="operador",
                    ativo=True,
                ),
                UsuarioAdmin(
                    nome="Usuário Desativado",
                    usuario="inativo.teste",
                    senha_hash=hash_senha("senha-segura-de-teste-2026"),
                    perfil="operador",
                    ativo=False,
                ),
            ]
        )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    engine.dispose()


def csrf_token(client):
    resposta = client.get("/admin/api/csrf")
    assert resposta.status_code == 200
    return resposta.json()["csrf_token"]


def fazer_login(client, usuario="admin.teste", senha="senha-segura-de-teste-2026"):
    token = csrf_token(client)
    return client.post(
        "/admin/api/login",
        json={"usuario": usuario, "senha": senha},
        headers={"X-CSRF-Token": token},
    )


def test_login_valido_cria_sessao_e_acessa_rota_protegida(auth_client):
    resposta = fazer_login(auth_client)

    assert resposta.status_code == 200
    assert resposta.json()["autenticado"] is True
    sessao = auth_client.get("/admin/api/session")
    protegido = auth_client.get("/admin")
    assert sessao.status_code == 200
    assert sessao.json()["usuario"]["perfil"] == "administrador"
    assert protegido.status_code == 200


@pytest.mark.parametrize(
    ("usuario", "senha"),
    [
        ("admin.teste", "senha-incorreta-2026"),
        ("desconhecido", "senha-segura-de-teste-2026"),
        ("inativo.teste", "senha-segura-de-teste-2026"),
    ],
)
def test_credenciais_invalidas_nao_revelam_estado_do_usuario(
    auth_client,
    usuario,
    senha,
):
    resposta = fazer_login(auth_client, usuario, senha)

    assert resposta.status_code == 401
    assert resposta.json()["detail"] == (
        "Não foi possível autenticar com as credenciais fornecidas."
    )


def test_login_exige_csrf(auth_client):
    resposta = auth_client.post(
        "/admin/api/login",
        json={"usuario": "admin.teste", "senha": "senha-segura-de-teste-2026"},
    )

    assert resposta.status_code == 403


def test_cookie_de_sessao_tem_atributos_de_seguranca(auth_client):
    resposta = auth_client.get("/admin/api/csrf")
    cookie = resposta.headers["set-cookie"].casefold()

    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "oi_zeus_session" in cookie


def test_logout_revoga_a_sessao(auth_client):
    assert fazer_login(auth_client).status_code == 200
    sessao = auth_client.get("/admin/api/session").json()
    resposta = auth_client.post(
        "/admin/api/logout",
        headers={"X-CSRF-Token": sessao["csrf_token"]},
    )

    assert resposta.status_code == 204
    assert auth_client.get("/admin/api/session").status_code == 401


def test_acesso_sem_autenticacao_e_protegido(auth_client):
    assert auth_client.get("/admin").status_code == 401
    assert auth_client.get("/admin/api/session").status_code == 401


def test_limita_tentativas_excessivas(auth_client):
    for _ in range(admin_auth.MAX_TENTATIVAS_LOGIN):
        assert fazer_login(auth_client, senha="senha-errada-de-teste-2026").status_code == 401

    bloqueado = fazer_login(auth_client)
    assert bloqueado.status_code == 429
    assert bloqueado.json()["detail"] == (
        "Não foi possível autenticar com as credenciais fornecidas."
    )


def test_permissoes_por_perfil(auth_client):
    administrador = UsuarioAdmin(
        nome="Admin",
        usuario="admin",
        senha_hash="hash",
        perfil="administrador",
        ativo=True,
    )
    operador = UsuarioAdmin(
        nome="Operador",
        usuario="operador",
        senha_hash="hash",
        perfil="operador",
        ativo=True,
    )
    somente_administrador = admin_auth.require_profile("administrador")

    assert somente_administrador(administrador) is administrador
    with pytest.raises(HTTPException) as erro:
        somente_administrador(operador)
    assert erro.value.status_code == 403


def test_chat_publico_permanece_sem_login(auth_client, monkeypatch):
    resultado = {
        "encontrado": True,
        "unidade": "4ª Vara Cível",
        "categoria": "Varas Cíveis",
        "comarca": "São Luís",
        "contatos": [
            {"tipo": "ramal", "valor": "2555", "descricao": None, "principal": True}
        ],
        "ramais": ["2555"],
    }
    monkeypatch.setattr("app.main.buscar_ramal", lambda _: resultado)

    resposta = auth_client.post("/chat", json={"mensagem": "ramal da 4ª vara"})

    assert resposta.status_code == 200
    assert set(resposta.json()) == {"resposta", "dados"}
    assert resposta.json()["dados"] == resultado


def test_pagina_de_login_e_served(auth_client):
    resposta = auth_client.get("/admin/login")

    assert resposta.status_code == 200
    assert "Acesso administrativo" in resposta.text
    assert auth_client.get("/static/admin/login.css").status_code == 200
    assert auth_client.get("/static/admin/login.js").status_code == 200


def test_usuario_normalizado_e_validado():
    assert validar_usuario("  Admin.Teste ") == "admin.teste"
    with pytest.raises(ValueError):
        validar_usuario("x")


def test_primeiro_administrador_usa_argon2_e_nao_pode_ser_repetido():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    administrador = criar_primeiro_administrador(
        session_factory,
        "Admin Inicial",
        "Admin.Inicial",
        "senha-inicial-comprida-e-segura",
    )

    assert administrador.usuario == "admin.inicial"
    assert administrador.perfil == "administrador"
    assert administrador.senha_hash.startswith("$argon2id$")
    assert administrador.senha_hash != "senha-inicial-comprida-e-segura"
    with pytest.raises(AdministradorInicialJaExiste):
        criar_primeiro_administrador(
            session_factory,
            "Outro Admin",
            "outro.admin",
            "outra-senha-inicial-segura",
        )
    engine.dispose()