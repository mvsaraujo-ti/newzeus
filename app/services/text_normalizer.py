import re
import unicodedata


_ORDINAIS = {
    "primeiro": 1,
    "primeira": 1,
    "segundo": 2,
    "segunda": 2,
    "terceiro": 3,
    "terceira": 3,
    "quarto": 4,
    "quarta": 4,
    "quinto": 5,
    "quinta": 5,
    "sexto": 6,
    "sexta": 6,
    "setimo": 7,
    "setima": 7,
    "oitavo": 8,
    "oitava": 8,
    "nono": 9,
    "nona": 9,
    "decimo": 10,
    "decima": 10,
}
_CARDINAIS = {
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
    "treze": 13,
    "catorze": 14,
    "quatorze": 14,
    "quinze": 15,
    "dezesseis": 16,
    "dezasseis": 16,
}

for _numero in range(11, 20):
    _unidade = _CARDINAIS.get(_numero - 10)
    _ordinal_unidade = {
        1: ("primeiro", "primeira"),
        2: ("segundo", "segunda"),
        3: ("terceiro", "terceira"),
        4: ("quarto", "quarta"),
        5: ("quinto", "quinta"),
        6: ("sexto", "sexta"),
        7: ("setimo", "setima"),
        8: ("oitavo", "oitava"),
        9: ("nono", "nona"),
    }.get(_numero - 10)
    if _ordinal_unidade:
        for _base in ("decimo", "decima"):
            for _forma in _ordinal_unidade:
                _ORDINAIS[f"{_base} {_forma}"] = _numero

_STOPWORDS = {
    "a", "as", "ao", "aos", "da", "das", "de", "do", "dos", "e", "em",
    "entre", "eu", "favor", "gostaria", "me", "na", "nas", "no", "nos", "o",
    "oi", "ola", "os", "para", "por", "preciso", "qual", "quais", "quero",
    "ramal", "ramais", "telefone", "telefones", "contato", "contatos", "numero",
    "n", "nro", "ligar", "ligue", "falar", "conversar", "como", "entro", "com",
    "passa", "passe", "diga", "informe", "voce", "sabe", "zeus", "tem", "um", "uma",
    "fale", "setor", "atende", "caso", "casos", "responsavel", "responsaveis",
    "competencia", "competencias", "vara", "comarca", "unidade",
}


def _remover_acentos(texto: str) -> str:
    decomposicao = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(
        caractere
        for caractere in decomposicao
        if unicodedata.category(caractere) != "Mn"
    )


def _substituir_numeros(texto: str) -> str:
    texto = re.sub(r"\b(?:numero|nro|n)\s+(?:um|uma)\b", "1", texto)
    for termo, numero in sorted(
        {**_ORDINAIS, **_CARDINAIS}.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        texto = re.sub(rf"(?<!\w){re.escape(termo)}(?!\w)", str(numero), texto)
    return re.sub(r"\b(\d+)\s*(?:a|o)\b", r"\1", texto)


def normalizar_texto(texto: str) -> str:
    texto = _remover_acentos(texto)
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = _substituir_numeros(texto)
    texto = re.sub(r"\bcivil\b", "civel", texto)
    texto = re.sub(r"\bcivis\b", "civeis", texto)
    texto = re.sub(r"\bvaras\b", "vara", texto)
    texto = re.sub(r"\bciveis\b", "civel", texto)
    texto = re.sub(r"\badministrativ[oa]s?\b", "administracao", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tokens_de_busca(texto: str) -> list[str]:
    return [token for token in normalizar_texto(texto).split() if token not in _STOPWORDS]