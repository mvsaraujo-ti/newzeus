import re

from sqlalchemy import select

from app.database.config import SessionLocal
from app.models import CompetenciaUnidade, Unidade
from app.services.text_normalizer import normalizar_texto


_MARCADOR_COMPETENCIA = re.compile(r"(?im)^\s*compet[eê]ncia\s*:\s*")


def extrair_competencias(
    descricao: str | None,
    categoria: str | None = None,
) -> list[str]:
    if not descricao:
        return []
    marcador = _MARCADOR_COMPETENCIA.search(descricao)
    if marcador is not None:
        conteudo = descricao[marcador.end():]
    else:
        if "vara" not in normalizar_texto(categoria or ""):
            return []
        conteudo = descricao
        partes = re.split(r"[;\n]+|(?<=[.!?])\s+", conteudo)
        partes = [parte.strip(" \t\r\n.;:-") for parte in partes if parte.strip(" \t\r\n.;:-")]
        if len(partes) < 5 or any(len(parte) > 160 for parte in partes):
            return []

    itens = re.split(r"[;\n]+|(?<=[.!?])\s+", conteudo)
    unicos: dict[str, str] = {}
    for item in itens:
        competencia = re.sub(r"\s+", " ", item).strip(" \t\r\n.;:-")
        chave = normalizar_texto(competencia)
        if competencia and chave:
            unicos.setdefault(chave, competencia)
    return list(unicos.values())


def migrar_competencias_descricao() -> int:
    inseridas = 0
    with SessionLocal.begin() as session:
        unidades = session.scalars(
            select(Unidade).where(Unidade.descricao.is_not(None))
        ).all()
        for unidade in unidades:
            existentes = {
                normalizar_texto(nome)
                for nome in session.scalars(
                    select(CompetenciaUnidade.nome).where(
                        CompetenciaUnidade.unidade_id == unidade.id
                    )
                ).all()
            }
            for nome in extrair_competencias(unidade.descricao, unidade.categoria):
                chave = normalizar_texto(nome)
                if chave in existentes:
                    continue
                session.add(
                    CompetenciaUnidade(
                        unidade_id=unidade.id,
                        nome=nome,
                        ativo=True,
                    )
                )
                existentes.add(chave)
                inseridas += 1
    return inseridas