import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.services.text_normalizer import normalizar_texto, tokens_de_busca


@dataclass(frozen=True)
class ConsultaInterpretada:
    texto_busca: str
    numeros: tuple[int, ...]
    comarcas: tuple[str, ...]
    comarca_desconhecida: bool
    trecho_comarca: str | None = None

    def tokens_de_unidade(self, nome: str, comarca: str | None) -> list[str]:
        if comarca:
            comarca_normalizada = normalizar_texto(comarca)
            nome = re.sub(
                rf"(?<!\w){re.escape(comarca_normalizada)}(?!\w)",
                " ",
                nome,
            )
        return tokens_de_busca(nome)


def interpretar_pergunta(
    pergunta: str,
    comarcas_cadastradas: list[str],
) -> ConsultaInterpretada:
    texto = normalizar_texto(pergunta)
    comarcas_normalizadas = tuple(
        dict.fromkeys(
            normalizar_texto(comarca)
            for comarca in comarcas_cadastradas
        )
    )
    localidades_exatas = tuple(
        comarca
        for comarca in comarcas_normalizadas
        if re.search(rf"(?<!\w){re.escape(comarca)}(?!\w)", texto)
    )
    comarca_desconhecida = False
    trecho_comarca = None
    comarcas_encontradas = localidades_exatas

    if localidades_exatas:
        for comarca in localidades_exatas:
            texto = re.sub(rf"(?<!\w){re.escape(comarca)}(?!\w)", " ", texto)
    else:
        localidade_suffix = re.search(
            r"\b(?:de|em)\s+([a-z]+(?:\s+[a-z]+){0,2})$",
            texto,
        )
        if localidade_suffix:
            trecho_comarca = localidade_suffix.group(1)
            localidade_tokens = trecho_comarca.split()
            scores = []
            for comarca in comarcas_normalizadas:
                quantidade = len(comarca.split())
                for tamanho in range(max(1, quantidade - 1), quantidade + 2):
                    for inicio in range(max(0, len(localidade_tokens) - tamanho + 1)):
                        janela = " ".join(localidade_tokens[inicio:inicio + tamanho])
                        scores.append((fuzz.ratio(comarca, janela), comarca))

            maior_score = max((score for score, _ in scores), default=0)
            if maior_score >= 82:
                comarcas_encontradas = tuple(
                    dict.fromkeys(
                        comarca
                        for score, comarca in scores
                        if score >= 82 and maior_score - score <= 2
                    )
                )
                texto = re.sub(
                    rf"\b(?:de|em)\s+{re.escape(trecho_comarca)}$",
                    " ",
                    texto,
                )
            else:
                comarca_desconhecida = True
                texto = texto[:localidade_suffix.start()].strip()

    numeros = tuple(dict.fromkeys(int(numero) for numero in re.findall(r"\b\d+\b", texto)))
    tokens = tokens_de_busca(texto)
    return ConsultaInterpretada(
        texto_busca=" ".join(tokens),
        numeros=numeros,
        comarcas=comarcas_encontradas,
        comarca_desconhecida=comarca_desconhecida,
        trecho_comarca=trecho_comarca,
    )