const loginView = document.getElementById("login-view");
const authenticatedView = document.getElementById("authenticated-view");
const loginForm = document.getElementById("login-form");
const submitButton = document.getElementById("submit-button");
const statusMessage = document.getElementById("status-message");
const sessionMessage = document.getElementById("session-message");
const logoutButton = document.getElementById("logout-button");

let csrfToken = "";

async function obterCsrfToken() {
    const resposta = await fetch("/admin/api/csrf", { credentials: "same-origin" });
    if (!resposta.ok) throw new Error("Não foi possível iniciar uma sessão segura.");
    const dados = await resposta.json();
    csrfToken = dados.csrf_token;
}

function mostrarSessao(usuario) {
    window.location.assign("/admin");
}

async function verificarSessao() {
    const resposta = await fetch("/admin/api/session", { credentials: "same-origin" });
    if (!resposta.ok) return;
    const dados = await resposta.json();
    csrfToken = dados.csrf_token;
    mostrarSessao(dados.usuario);
}

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusMessage.textContent = "";
    submitButton.disabled = true;

    try {
        await obterCsrfToken();
        const resposta = await fetch("/admin/api/login", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            body: JSON.stringify({
                usuario: document.getElementById("usuario").value,
                senha: document.getElementById("senha").value,
            }),
        });

        if (!resposta.ok) {
            statusMessage.textContent = resposta.status === 429
                ? "Muitas tentativas. Aguarde antes de tentar novamente."
                : "Não foi possível autenticar com as credenciais fornecidas.";
            return;
        }

        const dados = await resposta.json();
        document.getElementById("senha").value = "";
        const sessao = await fetch("/admin/api/session", { credentials: "same-origin" });
        const sessaoDados = await sessao.json();
        csrfToken = sessaoDados.csrf_token;
        mostrarSessao(dados.usuario);
    } catch (error) {
        statusMessage.textContent = "Não foi possível conectar ao serviço de autenticação.";
        console.error(error);
    } finally {
        submitButton.disabled = false;
    }
});

logoutButton.addEventListener("click", async () => {
    sessionMessage.textContent = "";
    try {
        const resposta = await fetch("/admin/api/logout", {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRF-Token": csrfToken },
        });
        if (!resposta.ok) throw new Error("Logout não concluído.");
        authenticatedView.hidden = true;
        loginView.hidden = false;
        await obterCsrfToken();
        document.getElementById("usuario").focus();
    } catch (error) {
        sessionMessage.textContent = "Não foi possível encerrar a sessão. Tente novamente.";
        console.error(error);
    }
});

verificarSessao().catch(() => {});