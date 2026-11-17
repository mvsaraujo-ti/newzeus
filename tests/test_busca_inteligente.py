import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.config import Base
from app.main import Pergunta, chat
from app.models import CompetenciaUnidade, Contato, Unidade
from app.services import ramais_service
from app.services import competency_migrator
from app.services.competency_migrator import migrar_competencias_descricao
from app.services.ramais_service import buscar_ramal, formatar_resposta


@pytest.fixture
def banco_teste(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    sessao_teste = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(ramais_service, "SessionLocal", sessao_teste)

    unidades = []
    with sessao_teste.begin() as sessao:
        for numero in range(1, 17):
            unidade = Unidade(
                nome=f"{numero}ª Vara Cível",
                categoria="Varas Cíveis",
                comarca="São Luís",
            )
            sessao.add(unidade)
            unidades.append(unidade)

        unidades.extend(
            [
                Unidade(
                    nome="Fórum de São Luís",
                    categoria="Administração",
                    comarca="São Luís",
                ),
                Unidade(
                    nome="Administração do Fórum",
                    categoria="Administração",
                    comarca="São Luís",
                ),
                Unidade(
                    nome="Diretor do Fórum",
                    categoria="Administração",
                    comarca="São Luís",
                ),
            ]
        )
        sessao.add_all(unidades[16:])
        sessao.flush()

        contatos = {
            1: ["2549"],
            2: ["2552"],
            4: ["2555"],
            12: ["2576", "2577"],
        }
        for numero, valores in contatos.items():
            unidade = unidades[numero - 1]
            for indice, valor in enumerate(valores):
                sessao.add(
                    Contato(
                        unidade_id=unidade.id,
                        tipo="Ramal" if numero == 12 and indice == 1 else "ramal",
                        valor=valor,
                        principal=indice == 0,
                    )
                )

        for unidade, valores in zip(
            unidades[16:],
            (["2600"], ["2598", "2599"], ["2595", "2596"]),
        ):
            for indice, valor in enumerate(valores):
                sessao.add(
                    Contato(
                        unidade_id=unidade.id,
                        tipo="ramal",
                        valor=valor,
                        principal=indice == 0,
                    )
                )

        balsas = Unidade(
            nome="1ª Vara de Balsas",
            categoria="Vara Judicial",
            comarca="Balsas",
            descricao=(
                "Competência:\nAção Acidentária. Cível e Comércio. "
                "Fazenda Pública - Execuções Fiscais. Saúde Pública."
            ),
        )
        sessao.add(balsas)
        sessao.flush()
        sessao.add(
            Contato(
                unidade_id=balsas.id,
                tipo="ramal",
                valor="3201",
                principal=True,
                ativo=True,
            )
        )
        sessao.add_all(
            CompetenciaUnidade(unidade_id=balsas.id, nome=nome, ativo=True)
            for nome in (
                "Ação Acidentária",
                "Cível e Comércio",
                "Fazenda Pública - Execuções Fiscais",
                "Saúde Pública",
            )
        )

    yield sessao_teste
    engine.dispose()


@pytest.mark.parametrize(
    ("pergunta", "unidade", "ramais"),
    [
        ("Qual o ramal da 4ª Vara Cível?", "4ª Vara Cível", ["2555"]),
        ("Oi Zeus, qual o ramal da quarta vara cível?", "4ª Vara Cível", ["2555"]),
        ("Telefone da quarta vara civil", "4ª Vara Cível", ["2555"]),
        ("Qual o contato da vara cível número quatro?", "4ª Vara Cível", ["2555"]),
        ("Qual o telefone da 12a Vara Cível?", "12ª Vara Cível", ["2576", "2577"]),
        (
            "Qual o ramal da décima segunda Vara Cível?",
            "12ª Vara Cível",
            ["2576", "2577"],
        ),
        ("Fale com a 4 vara civeu", "4ª Vara Cível", ["2555"]),
    ],
)
def test_reconhece_variacoes_de_unidade(banco_teste, pergunta, unidade, ramais):
    resultado = buscar_ramal(pergunta)

    assert resultado["encontrado"] is True
    assert resultado["unidade"] == unidade
    assert resultado["ramais"] == ramais


def test_nao_confunde_segunda_com_decima_segunda(banco_teste):
    segunda = buscar_ramal("Qual o ramal da 2ª Vara Cível?")
    decima_segunda = buscar_ramal("Qual o ramal da 12ª Vara Cível?")

    assert segunda["unidade"] == "2ª Vara Cível"
    assert segunda["ramais"] == ["2552"]
    assert decima_segunda["unidade"] == "12ª Vara Cível"
    assert decima_segunda["ramais"] == ["2576", "2577"]


@pytest.mark.parametrize(
    "pergunta",
    [
        "Como entro em contato com a administração do Fórum?",
        "Preciso falar com o setor administrativo do forum",
    ],
)
def test_reconhece_sinonimos_e_linguagem_natural(banco_teste, pergunta):
    resultado = buscar_ramal(pergunta)

    assert resultado["encontrado"] is True
    assert resultado["unidade"] == "Administração do Fórum"


def test_usa_comarca_informada_para_filtrar_unidades(banco_teste):
    resultado = buscar_ramal("Qual o ramal da 12ª Vara Cível de São Luís?")

    assert resultado["unidade"] == "12ª Vara Cível"
    assert resultado["comarca"] == "São Luís"


def test_nao_associa_unidade_a_comarca_nao_cadastrada(banco_teste):
    resultado = buscar_ramal("Qual o ramal da 12ª Vara Cível de Imperatriz?")

    assert resultado["encontrado"] is False
    assert resultado["sugestoes"] == []


def test_consulta_sem_numero_pede_esclarecimento(banco_teste):
    resultado = buscar_ramal("Qual o ramal da Vara Cível?")

    assert resultado["encontrado"] is False
    assert resultado["ambigua"] is True
    assert len(resultado["opcoes"]) > 1


def test_unidade_inexistente_nao_inventa_contato(banco_teste):
    resultado = buscar_ramal("Qual o telefone do Núcleo Lunar?")

    assert resultado["encontrado"] is False
    assert resultado["mensagem"] == "Não encontrei esse contato cadastrado na minha base."
    assert "ramais" not in resultado


def test_formata_todos_os_ramais_e_suas_finalidades(banco_teste):
    resultado = buscar_ramal("Fale com o Diretor do Fórum")
    resposta = formatar_resposta(resultado)

    assert resultado["ramais"] == ["2595", "2596"]
    assert "2595" in resposta and "2596" in resposta
    assert "Posso ajudar com outro contato?" in resposta


def test_nao_repete_comarca_que_ja_esta_no_nome(banco_teste):
    resultado = buscar_ramal("Qual o telefone do Fórum de São Luís?")
    resposta = formatar_resposta(resultado)

    assert resultado["unidade"] == "Fórum de São Luís"
    assert "Fórum de São Luís de São Luís" not in resposta
    assert "do Fórum de São Luís" in resposta


def test_endpoint_chat_mantem_contrato_de_resposta(banco_teste):
    resposta = chat(Pergunta(mensagem="Qual o ramal da 12ª Vara Cível?"))

    assert set(resposta) == {"resposta", "dados"}
    assert "12ª Vara Cível" in resposta["resposta"]
    assert "2576" in resposta["resposta"]
    assert "2577" in resposta["resposta"]
    assert resposta["dados"]["ramais"] == ["2576", "2577"]


@pytest.mark.parametrize(
    ("pergunta", "unidade", "comarca", "ramal"),
    [
        (
            "Qual o ramal da 1ª Vara Cível de São Luís?",
            "1ª Vara Cível",
            "São Luís",
            "2549",
        ),
        (
            "Qual o ramal da 1ª Vara Cível em Balsas?",
            "1ª Vara de Balsas",
            "Balsas",
            "3201",
        ),
        (
            "Qual o ramal da primeira vara de balsaz?",
            "1ª Vara de Balsas",
            "Balsas",
            "3201",
        ),
    ],
)
def test_filtra_comarca_explicita_e_com_erros_simples(
    banco_teste,
    pergunta,
    unidade,
    comarca,
    ramal,
):
    resultado = buscar_ramal(pergunta)

    assert resultado["encontrado"] is True
    assert resultado["unidade"] == unidade
    assert resultado["comarca"] == comarca
    assert resultado["ramais"] == [ramal]


def test_unidade_sem_comarca_retorna_quando_nome_unico(banco_teste):
    resultado = buscar_ramal("Qual o telefone do Fórum de São Luís?")

    assert resultado["encontrado"] is True
    assert resultado["unidade"] == "Fórum de São Luís"


def test_pede_esclarecimento_para_unidade_compativel_em_varias_comarcas(banco_teste):
    resultado = buscar_ramal("Qual o ramal da 1ª Vara Cível?")

    assert resultado["encontrado"] is False
    assert resultado["ambigua"] is True
    assert {opcao["comarca"] for opcao in resultado["opcoes"]} == {"São Luís", "Balsas"}
    resposta = formatar_resposta(resultado)
    assert "São Luís" in resposta and "Balsas" in resposta


def test_comarca_inexistente_nao_substitui_por_sao_luis(banco_teste):
    resultado = buscar_ramal("Qual o ramal da 1ª Vara Cível de Imperatriz?")

    assert resultado["encontrado"] is False
    assert resultado["sugestoes"] == []
    assert "comarca consultada" in resultado["mensagem"]


def test_unidade_inexistente_na_comarca_informada_nao_busca_em_outra(banco_teste):
    resultado = buscar_ramal("Qual o ramal da 4ª Vara Cível em Balsas?")

    assert resultado["encontrado"] is False
    assert resultado["sugestoes"] == []
    assert "Balsas" in resultado["mensagem"]


def test_nome_identico_em_duas_comarcas_pede_localidade(banco_teste):
    with banco_teste.begin() as session:
        session.add_all(
            [
                Unidade(
                    nome="Núcleo Compartilhado",
                    categoria="Atendimento",
                    comarca="São Luís",
                ),
                Unidade(
                    nome="Núcleo Compartilhado",
                    categoria="Atendimento",
                    comarca="Balsas",
                ),
            ]
        )

    resultado = buscar_ramal("Qual o contato do Núcleo Compartilhado?")

    assert resultado["ambigua"] is True
    assert {opcao["comarca"] for opcao in resultado["opcoes"]} == {"São Luís", "Balsas"}


@pytest.mark.parametrize(
    ("pergunta", "ramal"),
    [
        ("Qual vara atende casos de Saúde Pública em Balsas?", "3201"),
        ("Qual unidade é responsável por execuções fiscais em Balsas?", "3201"),
        ("Preciso do contato da unidade que atende Cível e Comércio.", "3201"),
    ],
)
def test_busca_por_competencia_cadastrada(banco_teste, pergunta, ramal):
    resultado = buscar_ramal(pergunta)

    assert resultado["encontrado"] is True
    assert resultado["unidade"] == "1ª Vara de Balsas"
    assert resultado["comarca"] == "Balsas"
    assert resultado["ramais"] == [ramal]


def test_comarca_acentuada_e_sem_acento_filtra_da_mesma_forma(banco_teste):
    com_acento = buscar_ramal("Qual o ramal da 1ª Vara Cível de São Luís?")
    sem_acento = buscar_ramal("Qual o ramal da 1ª Vara Civel de Sao Luis?")

    assert com_acento["unidade"] == sem_acento["unidade"] == "1ª Vara Cível"
    assert com_acento["ramais"] == sem_acento["ramais"] == ["2549"]


def test_competencia_nao_cadastrada_nao_e_inferida(banco_teste):
    resultado = buscar_ramal("Qual vara atende transplante em Balsas?")

    assert resultado["encontrado"] is False
    assert "ramais" not in resultado


def test_migracao_de_competencias_e_idempotente(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(competency_migrator, "SessionLocal", factory)
    descricao = "Competência:\nAção Acidentária. Cível e Comércio. Saúde Pública."
    with factory.begin() as session:
        unidade = Unidade(
            nome="1ª Vara de Balsas",
            categoria="Vara Judicial",
            comarca="Balsas",
            descricao=descricao,
        )
        session.add(unidade)

    assert migrar_competencias_descricao() == 3
    assert migrar_competencias_descricao() == 0
    with factory() as session:
        unidade = session.scalar(select(Unidade))
        assert unidade.descricao == descricao
        assert {item.nome for item in unidade.competencias} == {
            "Ação Acidentária",
            "Cível e Comércio",
            "Saúde Pública",
        }
    engine.dispose()


def test_extrai_lista_curta_de_competencias_de_descricao_de_vara():
    descricao = (
        "Ação Acidentária. Cível e Comércio. Fazenda Estadual e Fazenda Municipal. "
        "Fazenda Pública - Execuções Fiscais. Improbidade Administrativa. "
        "Interesses difusos e coletivos. Juizado Especial da Fazenda Pública. "
        "Recuperação de Empresas. Saúde Pública."
    )

    valores = competency_migrator.extrair_competencias(descricao, "Vara Judicial")

    assert len(valores) == 9
    assert "Saúde Pública" in valores
    assert "Fazenda Pública - Execuções Fiscais" in valores
    assert competency_migrator.extrair_competencias(descricao, "Administração") == []


def test_migrador_importa_lista_legada_de_vara_sem_marcador(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(competency_migrator, "SessionLocal", factory)
    descricao = (
        "Ação Acidentária. Cível e Comércio. Saúde Pública. Execuções Fiscais. "
        "Fazenda Estadual."
    )
    with factory.begin() as session:
        session.add(
            Unidade(
                nome="1ª Vara de Balsas",
                categoria="Vara Judicial",
                comarca="Balsas",
                descricao=descricao,
            )
        )

    assert migrar_competencias_descricao() == 5
    assert migrar_competencias_descricao() == 0
    with factory() as session:
        unidade = session.scalar(select(Unidade))
        assert {item.nome for item in unidade.competencias} == {
            "Ação Acidentária",
            "Cível e Comércio",
            "Saúde Pública",
            "Execuções Fiscais",
            "Fazenda Estadual",
        }
        assert unidade.descricao == descricao
    engine.dispose()


def test_formatador_inclui_um_ramal():
    resposta = formatar_resposta(
        {
            "encontrado": True,
            "unidade": "1ª Vara de Balsas",
            "comarca": "Balsas",
            "contatos": [
                {"tipo": "ramal", "valor": "3201", "descricao": None, "principal": True}
            ],
        }
    )

    assert "3201" in resposta
    assert "1ª Vara de Balsas" in resposta


def test_formatador_inclui_varios_ramais():
    resposta = formatar_resposta(
        {
            "encontrado": True,
            "unidade": "Unidade de Teste",
            "comarca": "Balsas",
            "contatos": [
                {"tipo": "ramal", "valor": "3201", "descricao": "Recepção", "principal": True},
                {"tipo": "ramal", "valor": "3202", "descricao": "Cartório", "principal": False},
            ],
        }
    )

    assert "3201" in resposta and "3202" in resposta
    assert "Recepção" in resposta and "Cartório" in resposta


def test_formatador_distingue_tipos_de_contato():
    resposta = formatar_resposta(
        {
            "encontrado": True,
            "unidade": "Unidade de Teste",
            "comarca": "Balsas",
            "contatos": [
                {"tipo": "ramal", "valor": "3201", "descricao": None, "principal": True},
                {"tipo": "whatsapp", "valor": "+55 99 90000-0000", "descricao": "Plantão", "principal": False},
                {"tipo": "email", "valor": "contato@example.org", "descricao": None, "principal": False},
            ],
        }
    )

    assert "Ramal" in resposta
    assert "Whatsapp" in resposta
    assert "Email" in resposta
    assert "contato@example.org" in resposta