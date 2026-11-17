
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.config import SessionLocal
from app.models import Unidade
from app.services.query_interpreter import ConsultaInterpretada, interpretar_pergunta
from app.services.response_formatter import formatar_resposta
from app.services.text_normalizer import normalizar_texto


def _carregar_unidades_ativas() -> list[Unidade]:
    with SessionLocal() as session:
        return list(session.scalars(
            select(Unidade)
            .options(
                selectinload(Unidade.contatos),
                selectinload(Unidade.competencias),
            )
            .where(Unidade.ativo.is_(True))
            .order_by(Unidade.id)
        ).all())


def identificar_unidade(
    consulta: ConsultaInterpretada,
    unidades: list[Unidade],
) -> list[tuple[Unidade, float]]:
    from rapidfuzz import fuzz

    if consulta.comarca_desconhecida:
        return []

    correspondencias: list[tuple[Unidade, float]] = []
    for unidade in unidades:
        comarca = normalizar_texto(unidade.comarca or "")
        if consulta.comarcas and comarca not in consulta.comarcas:
            continue

        nome_unidade = normalizar_texto(unidade.nome)
        numeros_unidade = {
            int(numero)
            for numero in re.findall(r"\b\d+\b", nome_unidade)
        }
        if consulta.numeros:
            if not numeros_unidade or not numeros_unidade.intersection(consulta.numeros):
                continue

        tokens_consulta = set(consulta.texto_busca.split())
        alias_nome = " ".join(
            consulta.tokens_de_unidade(nome_unidade, unidade.comarca)
        )
        tokens_nome = set(alias_nome.split())
        alias_categoria = " ".join(
            consulta.tokens_de_unidade(normalizar_texto(unidade.categoria), None)
        )
        alias_categoria_tokens = set(alias_categoria.split())

        scores: list[float] = []
        if consulta.texto_busca and alias_nome:
            score_nome = max(
                fuzz.ratio(consulta.texto_busca, alias_nome),
                fuzz.token_sort_ratio(consulta.texto_busca, alias_nome),
            )
            if tokens_consulta.issubset(tokens_nome) or score_nome >= 78:
                scores.append(float(score_nome))

        if (
            tokens_consulta
            and alias_categoria
            and tokens_consulta.issubset(alias_categoria_tokens)
        ):
            scores.append(100.0)

        termos_competencia = tokens_consulta - {str(numero) for numero in consulta.numeros}
        if termos_competencia:
            texto_competencia = " ".join(sorted(termos_competencia))
            for competencia in unidade.competencias:
                if not competencia.ativo:
                    continue
                alias_competencia = " ".join(
                    sorted(normalizar_texto(competencia.nome).split())
                )
                tokens_competencia = set(alias_competencia.split())
                score_competencia = max(
                    fuzz.token_sort_ratio(texto_competencia, alias_competencia),
                    fuzz.token_set_ratio(texto_competencia, alias_competencia),
                )
                if (
                    termos_competencia.issubset(tokens_competencia)
                    or score_competencia >= 82
                ):
                    scores.append(float(score_competencia))

        score = max(scores, default=0.0)
        correspondencias.append((unidade, score))

    return sorted(correspondencias, key=lambda item: (-item[1], item[0].id))


def buscar_ramal(pergunta: str) -> dict:
    unidades = _carregar_unidades_ativas()
    comarcas = [unidade.comarca for unidade in unidades if unidade.comarca]
    consulta = interpretar_pergunta(pergunta, comarcas)
    correspondencias = identificar_unidade(consulta, unidades)
    limiar = 76.0
    relevantes = [item for item in correspondencias if item[1] >= limiar]

    mesmo_nome_em_comarcas = (
        not consulta.comarcas
        and len({normalizar_texto(unidade.nome) for unidade, _ in relevantes}) == 1
        and len({normalizar_texto(unidade.comarca or "") for unidade, _ in relevantes}) > 1
    )
    scores_proximos = (
        len(relevantes) > 1
        and relevantes[0][1] - relevantes[1][1] <= 5
    )
    if len(relevantes) > 1 and (
        mesmo_nome_em_comarcas
        or not consulta.numeros
        or len(consulta.numeros) > 1
        or scores_proximos
    ):
        opcoes = [
            {
                "unidade": unidade.nome,
                "categoria": unidade.categoria,
                "comarca": unidade.comarca,
            }
            for unidade, _ in relevantes[:5]
        ]
        return {
            "encontrado": False,
            "ambigua": True,
            "opcoes": opcoes,
            "mensagem": "Encontrei unidades compatíveis em mais de uma opção. Informe a comarca ou a unidade desejada.",
        }

    if not relevantes:
        if consulta.comarcas or consulta.comarca_desconhecida:
            localidade = next(
                (
                    unidade.comarca
                    for unidade in unidades
                    if normalizar_texto(unidade.comarca or "") in consulta.comarcas
                ),
                None,
            )
            mensagem = (
                f"Não encontrei uma unidade compatível na comarca de {localidade}."
                if localidade
                else "Não encontrei uma unidade compatível na comarca consultada."
            )
            return {
                "encontrado": False,
                "ambigua": False,
                "sugestoes": [],
                "mensagem": mensagem,
                "comarca_consultada": localidade or consulta.trecho_comarca,
            }
        sugestoes = [
            {
                "unidade": unidade.nome,
                "categoria": unidade.categoria,
                "comarca": unidade.comarca,
            }
            for unidade, score in correspondencias
            if score >= 60
        ][:3]
        return {
            "encontrado": False,
            "ambigua": False,
            "sugestoes": sugestoes,
            "mensagem": "Não encontrei esse contato cadastrado na minha base.",
        }

    unidade = relevantes[0][0]
    contatos = [
        {
            "tipo": contato.tipo,
            "valor": contato.valor,
            "descricao": contato.descricao,
            "principal": contato.principal,
        }
        for contato in sorted(
            unidade.contatos,
            key=lambda contato: (not contato.principal, contato.id),
        )
        if contato.ativo
    ]
    return {
        "encontrado": True,
        "unidade": unidade.nome,
        "categoria": unidade.categoria,
        "comarca": unidade.comarca,
        "competencias": [
            competencia.nome
            for competencia in unidade.competencias
            if competencia.ativo
        ],
        "contatos": contatos,
        "ramais": [
            contato["valor"]
            for contato in contatos
            if contato["tipo"].casefold() == "ramal"
        ],
    }


__all__ = ["buscar_ramal", "formatar_resposta", "identificar_unidade"]
