from app.services.text_normalizer import normalizar_texto


_NOMES_FEMININOS = {"administracao", "vara", "secretaria", "unidade"}


def _referencia_unidade(unidade: str, comarca: str | None) -> str:
    nome_normalizado = normalizar_texto(unidade)
    artigo = "da" if nome_normalizado.split()[0].isdigit() else "do"
    if nome_normalizado.split()[0] in _NOMES_FEMININOS:
        artigo = "da"

    local = ""
    if comarca and normalizar_texto(comarca) not in nome_normalizado:
        local = f" de {comarca}"
    return f"{artigo} {unidade}{local}"


def formatar_resposta(resultado: dict) -> str:
    if not resultado["encontrado"]:
        opcoes = resultado.get("opcoes") or resultado.get("sugestoes") or []
        mensagem = resultado["mensagem"]
        if opcoes:
            nomes = ", ".join(
                f"{opcao['unidade']} — {opcao['comarca']}"
                if opcao.get("comarca")
                else opcao["unidade"]
                for opcao in opcoes
            )
            return f"{mensagem}\nOpções: {nomes}."
        return mensagem

    unidade = resultado["unidade"]
    comarca = resultado.get("comarca")
    referencia = _referencia_unidade(unidade, comarca)
    contatos = resultado.get("contatos", [])
    ramais = [
        contato for contato in contatos if contato["tipo"].casefold() == "ramal"
    ]

    if not contatos:
        return f"A unidade {unidade} está cadastrada, mas não há contatos ativos registrados."

    if len(contatos) == 1 and ramais:
        resposta = f"O ramal {referencia} é:\n{ramais[0]['valor']}"
    elif len(contatos) == len(ramais):
        linhas = [
            f"- {contato['valor']}" + (f" ({contato['descricao']})" if contato["descricao"] else "")
            for contato in contatos
        ]
        resposta = f"Os ramais {referencia} são:\n" + "\n".join(linhas)
    else:
        linhas = []
        for contato in contatos:
            finalidade = f" ({contato['descricao']})" if contato["descricao"] else ""
            principal = " (principal)" if contato["principal"] else ""
            linhas.append(f"- {contato['tipo'].capitalize()}{principal}{finalidade}: {contato['valor']}")
        resposta = f"Os contatos {referencia} são:\n" + "\n".join(linhas)

    return f"{resposta}\n\nPosso ajudar com outro contato?"