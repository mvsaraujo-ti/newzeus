import json
from pathlib import Path

from sqlalchemy import select

from app.database.config import Base, SessionLocal, engine
from app.models import Contato, Unidade


BASE_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_RAMais = BASE_DIR / "data" / "ramais.json"


def importar_ramais_json(caminho: Path = ARQUIVO_RAMais) -> dict[str, int]:
    with caminho.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    unidades_json = dados.get("unidades")
    if not isinstance(unidades_json, list):
        raise ValueError("A base JSON precisa conter uma lista de unidades.")

    Base.metadata.create_all(bind=engine)
    unidades_adicionadas = 0
    contatos_adicionados = 0

    with SessionLocal.begin() as session:
        for item in unidades_json:
            nome = item.get("nome")
            categoria = item.get("categoria")
            ramais = item.get("ramais", [])

            if not isinstance(nome, str) or not nome.strip():
                raise ValueError("Cada unidade precisa ter um nome válido.")
            if not isinstance(categoria, str) or not categoria.strip():
                raise ValueError(f"A unidade {nome!r} precisa ter uma categoria válida.")
            if not isinstance(ramais, list):
                raise ValueError(f"Os ramais da unidade {nome!r} precisam ser uma lista.")

            unidade = session.scalar(
                select(Unidade).where(Unidade.nome == nome.strip())
            )
            if unidade is None:
                unidade = Unidade(
                    nome=nome.strip(),
                    categoria=categoria.strip(),
                    comarca=item.get("comarca") or dados.get("comarca"),
                )
                session.add(unidade)
                session.flush()
                unidades_adicionadas += 1

            for indice, ramal in enumerate(ramais):
                valor = str(ramal).strip()
                if not valor:
                    raise ValueError(f"A unidade {nome!r} contém um ramal vazio.")

                contato_existente = session.scalar(
                    select(Contato.id).where(
                        Contato.unidade_id == unidade.id,
                        Contato.tipo == "ramal",
                        Contato.valor == valor,
                    )
                )
                if contato_existente is None:
                    session.add(
                        Contato(
                            unidade_id=unidade.id,
                            tipo="ramal",
                            valor=valor,
                            principal=indice == 0,
                        )
                    )
                    contatos_adicionados += 1

    return {
        "unidades_adicionadas": unidades_adicionadas,
        "contatos_adicionados": contatos_adicionados,
    }