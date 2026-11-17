
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("messages");
const sendButton = document.getElementById("send-button");
let esclarecimentoPendente = null;

function adicionarMensagem(texto, tipo) {
    const mensagem = document.createElement("article");

    mensagem.classList.add("message", tipo === "usuario" ? "user-message" : "bot-message");

    const remetente = document.createElement("span");
    remetente.className = "message-sender";
    remetente.textContent = tipo === "usuario" ? "Você" : "ZEUS";

    const conteudo = document.createElement("p");
    conteudo.className = "message-content";
    conteudo.textContent = texto;
    mensagem.append(remetente, conteudo);

    messages.appendChild(mensagem);

    const container = document.querySelector(".chat-container");
    container.scrollTop = container.scrollHeight;
}

function adicionarIndicadorProcessamento() {
    const indicador = document.createElement("div");
    indicador.className = "message bot-message typing-message";
    indicador.setAttribute("role", "status");
    indicador.setAttribute("aria-label", "ZEUS está consultando");

    const remetente = document.createElement("span");
    remetente.className = "message-sender";
    remetente.textContent = "ZEUS";

    const pontos = document.createElement("span");
    pontos.className = "typing-dots";
    pontos.setAttribute("aria-hidden", "true");
    pontos.append(document.createElement("i"), document.createElement("i"), document.createElement("i"));
    indicador.append(remetente, pontos);
    messages.appendChild(indicador);
    document.querySelector(".chat-container").scrollTop = document.querySelector(".chat-container").scrollHeight;
    return indicador;
}

function normalizarLocalidade(texto) {
    return texto
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLocaleLowerCase("pt-BR")
        .replace(/[^\w\s]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

function resolverEsclarecimento(texto) {
    if (!esclarecimentoPendente) return texto;

    const textoNormalizado = normalizarLocalidade(texto)
        .replace(/^(?:comarca\s+de|em|de)\s+/, "");
    const opcao = esclarecimentoPendente.opcoes.find(
        (item) => normalizarLocalidade(item.comarca) === textoNormalizado,
    );
    const perguntaOriginal = esclarecimentoPendente.pergunta;
    esclarecimentoPendente = null;
    return opcao ? `${perguntaOriginal} de ${opcao.comarca}` : texto;
}

function criarTexto(tag, className, valor) {
    const elemento = document.createElement(tag);
    elemento.className = className;
    elemento.textContent = valor;
    return elemento;
}

function adicionarRespostaComContatos(payload) {
    const dados = payload.dados;
    const mensagem = document.createElement("article");
    mensagem.className = "message bot-message structured-response";
    mensagem.append(criarTexto("span", "message-sender", "ZEUS"));

    const conteudo = document.createElement("div");
    conteudo.className = "message-content contact-response";
    const cabecalho = document.createElement("div");
    cabecalho.className = "contact-response-heading";
    cabecalho.append(criarTexto("strong", "contact-unit-name", dados.unidade));
    const localizacao = [dados.categoria, dados.comarca].filter(Boolean).join(" · ");
    if (localizacao) cabecalho.append(criarTexto("span", "contact-unit-meta", localizacao));
    conteudo.append(cabecalho);

    const lista = document.createElement("div");
    lista.className = "contact-card-list";
    const rotulos = {
        ramal: "RAMAL",
        telefone_fixo: "TELEFONE FIXO",
        whatsapp: "WHATSAPP",
        email: "E-MAIL",
        telefone_alternativo: "TELEFONE ALTERNATIVO",
        outro: "CONTATO",
    };

    for (const contato of dados.contatos) {
        const tipo = String(contato.tipo || "outro").toLocaleLowerCase("pt-BR");
        const cartao = document.createElement("div");
        cartao.className = `contact-card${tipo === "ramal" ? " contact-card-ramal" : ""}`;
        cartao.append(criarTexto("span", "contact-type", rotulos[tipo] || "CONTATO"));
        cartao.append(criarTexto("strong", "contact-value", contato.valor));
        if (contato.principal) cartao.append(criarTexto("span", "contact-primary", "PRINCIPAL"));
        if (contato.descricao) cartao.append(criarTexto("small", "contact-purpose", contato.descricao));
        lista.append(cartao);
    }
    conteudo.append(lista);
    conteudo.append(criarTexto("p", "contact-followup", "Posso ajudar com outro contato?"));
    mensagem.append(conteudo);
    messages.append(mensagem);
    document.querySelector(".chat-container").scrollTop =
        document.querySelector(".chat-container").scrollHeight;
}

function adicionarRespostaZeus(payload, pergunta) {
    const dados = payload.dados || {};
    if (dados.ambigua && Array.isArray(dados.opcoes)) {
        const unicas = new Map();
        for (const opcao of dados.opcoes) {
            if (opcao.comarca) unicas.set(normalizarLocalidade(opcao.comarca), opcao);
        }
        esclarecimentoPendente = unicas.size > 1
            ? { pergunta, opcoes: [...unicas.values()] }
            : null;
    } else {
        esclarecimentoPendente = null;
    }

    if (dados.encontrado && Array.isArray(dados.contatos) && dados.contatos.length) {
        adicionarRespostaComContatos(payload);
    } else {
        adicionarMensagem(payload.resposta, "zeus");
    }
}

async function enviarMensagem(texto) {
    const textoVisivel = texto.trim();
    if (!textoVisivel) return;
    const pergunta = resolverEsclarecimento(textoVisivel);

    adicionarMensagem(textoVisivel, "usuario");

    input.value = "";
    sendButton.disabled = true;
    sendButton.classList.add("is-loading");
    document.getElementById("send-label").textContent = "Consultando";
    const indicador = adicionarIndicadorProcessamento();

    try {
        const resposta = await fetch("/chat", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                mensagem: pergunta
            })
        });

        if (!resposta.ok) {
            throw new Error("Não foi possível concluir a consulta.");
        }

        const dados = await resposta.json();
        indicador.remove();
        adicionarRespostaZeus(dados, pergunta);

    } catch (erro) {
        indicador.remove();
        adicionarMensagem(
            "Não consegui concluir a consulta agora. Tente novamente em instantes.",
            "zeus"
        );

        console.error(erro);

    } finally {
        sendButton.disabled = false;
        sendButton.classList.remove("is-loading");
        document.getElementById("send-label").textContent = "Enviar";
        input.focus();
    }
}

form.addEventListener("submit", function(event) {
    event.preventDefault();
    enviarMensagem(input.value);
});

function enviarSugestao(texto) {
    enviarMensagem(texto);
}
