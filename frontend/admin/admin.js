const state = {
    csrfToken: "",
    user: null,
    editingUnitId: null,
    editingUserId: null,
    removedContactIds: new Set(),
};

const views = {
    dashboard: document.getElementById("dashboard-view"),
    units: document.getElementById("units-view"),
    users: document.getElementById("users-view"),
    audit: document.getElementById("audit-view"),
};

const titles = {
    dashboard: "Visão geral",
    units: "Unidades",
    users: "Usuários",
    audit: "Auditoria",
};

function showMessage(message, isError = true) {
    const target = document.getElementById("global-message");
    target.textContent = message;
    target.style.color = isError ? "#f0aaaa" : "#8bd8b8";
    if (message) window.scrollTo({ top: 0, behavior: "smooth" });
}

async function api(url, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    if (!new Set(["GET", "HEAD", "OPTIONS"]).has(method)) {
        headers.set("X-CSRF-Token", state.csrfToken);
    }
    const response = await fetch(url, {
        ...options,
        method,
        headers,
        credentials: "same-origin",
    });
    if (response.status === 401) {
        window.location.assign("/admin/login");
        throw new Error("Sua sessão expirou.");
    }
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Não foi possível concluir a operação.");
    }
    if (response.status === 204) return null;
    return response.json();
}

function cell(row, value, className = "") {
    const element = document.createElement("td");
    element.textContent = value ?? "—";
    if (className) element.className = className;
    row.append(element);
    return element;
}

function emptyRow(body, columns, message) {
    const row = document.createElement("tr");
    const empty = document.createElement("td");
    empty.colSpan = columns;
    empty.className = "empty-state";
    empty.textContent = message;
    row.append(empty);
    body.replaceChildren(row);
}

function actionButton(label, action, id, danger = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `row-button${danger ? " danger" : ""}`;
    button.dataset.action = action;
    button.dataset.id = id;
    button.textContent = label;
    return button;
}

function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}

function labelAction(action) {
    const labels = {
        cadastro: "Cadastro",
        edicao: "Edição",
        desativacao: "Desativação",
        reativacao: "Reativação",
        exclusao_logica: "Exclusão lógica",
    };
    return labels[action] || action;
}

function renderAuditRows(body, entries, columns, details = false) {
    body.replaceChildren();
    if (!entries.length) {
        emptyRow(body, columns, "Nenhuma alteração registrada.");
        return;
    }
    for (const entry of entries) {
        const row = document.createElement("tr");
        cell(row, formatDate(entry.data_hora));
        cell(row, entry.usuario || "Usuário removido");
        cell(row, labelAction(entry.acao));
        if (details) {
            cell(row, entry.entidade);
            cell(row, String(entry.registro_id ?? "—"));
            const content = document.createElement("td");
            content.textContent = JSON.stringify(entry.detalhes);
            row.append(content);
        } else {
            cell(row, `${entry.entidade} #${entry.registro_id ?? "—"}`);
        }
        body.append(row);
    }
}

function renderDistribution(targetId, entries) {
    const target = document.getElementById(targetId);
    target.replaceChildren();
    if (!entries.length) {
        const empty = document.createElement("p");
        empty.className = "distribution-empty";
        empty.textContent = "Sem dados cadastrados.";
        target.append(empty);
        return;
    }

    const maximum = Math.max(...entries.map((entry) => entry.unidades));
    for (const entry of entries) {
        const row = document.createElement("div");
        row.className = "distribution-item";
        const label = document.createElement("div");
        label.className = "distribution-label";
        const name = document.createElement("span");
        name.textContent = entry.nome;
        const count = document.createElement("strong");
        count.textContent = entry.unidades;
        label.append(name, count);
        const track = document.createElement("div");
        track.className = "distribution-track";
        const fill = document.createElement("span");
        fill.style.width = `${Math.max(4, (entry.unidades / maximum) * 100)}%`;
        track.append(fill);
        row.append(label, track);
        target.append(row);
    }
}

async function loadDashboard() {
    const data = await api("/admin/api/dashboard");
    document.getElementById("about-version").textContent = data.versao
        ? `Versão ${data.versao}`
        : "";
    document.getElementById("metric-units").textContent = data.total_unidades;
    document.getElementById("metric-unit-status").textContent =
        `${data.unidades_ativas} ativas · ${data.unidades_inativas} inativas`;
    document.getElementById("metric-contacts").textContent = data.total_contatos;
    document.getElementById("metric-active-contacts").textContent = `${data.contatos_ativos} ativos`;
    document.getElementById("metric-categories").textContent = data.total_categorias;
    document.getElementById("metric-comarcas").textContent = data.total_comarcas;
    document.getElementById("metric-queries").textContent =
        data.consultas_registradas === null ? "—" : data.consultas_registradas;
    renderDistribution("category-distribution", data.distribuicao_categorias || []);
    renderDistribution("comarca-distribution", data.distribuicao_comarcas || []);
    renderAuditRows(
        document.getElementById("recent-audit-body"),
        data.alteracoes_recentes || [],
        4,
    );

    for (const [id, values] of [
        ["filter-category", data.categorias],
        ["filter-comarca", data.comarcas],
    ]) {
        const select = document.getElementById(id);
        const currentValue = select.value;
        const first = select.options[0];
        select.replaceChildren(first);
        for (const value of values) {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            select.append(option);
        }
        select.value = currentValue;
    }
}

function unitFiltersUrl() {
    const params = new URLSearchParams();
    const search = document.getElementById("filter-search").value.trim();
    const category = document.getElementById("filter-category").value;
    const comarca = document.getElementById("filter-comarca").value;
    const active = document.getElementById("filter-status").value;
    if (search) params.set("busca", search);
    if (category) params.set("categoria", category);
    if (comarca) params.set("comarca", comarca);
    if (active) params.set("ativo", active);
    return `/admin/api/units?${params}`;
}

async function loadUnits() {
    const units = await api(unitFiltersUrl());
    const body = document.getElementById("units-body");
    body.replaceChildren();
    if (!units.length) emptyRow(body, 6, "Nenhuma unidade corresponde aos filtros.");

    for (const unit of units) {
        const row = document.createElement("tr");
        const name = document.createElement("td");
        name.className = "unit-name";
        name.textContent = unit.nome;
        const nameNote = document.createElement("span");
        nameNote.className = "unit-subtitle";
        nameNote.textContent = unit.descricao || "";
        name.append(nameNote);
        row.append(name);
        cell(row, unit.categoria);
        cell(row, unit.comarca || "—");

        const contacts = unit.contatos.filter((contact) => contact.ativo);
        const mainContact = contacts.find((contact) => contact.principal) || contacts[0];
        cell(
            row,
            mainContact
                ? `${mainContact.tipo}: ${mainContact.valor}${contacts.length > 1 ? ` (+${contacts.length - 1})` : ""}`
                : "Sem contato ativo",
            "contact-summary",
        );

        const stateCell = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = `badge${unit.ativo ? "" : " inactive"}`;
        badge.textContent = unit.ativo ? "Ativa" : "Inativa";
        stateCell.append(badge);
        row.append(stateCell);

        const actions = document.createElement("td");
        actions.className = "row-actions";
        actions.append(actionButton("Editar", "edit-unit", unit.id));
        if (state.user.perfil === "administrador") {
            actions.append(actionButton(unit.ativo ? "Desativar" : "Reativar", "toggle-unit", unit.id, unit.ativo));
        }
        row.append(actions);
        body.append(row);
    }
    document.getElementById("units-count").textContent = `${units.length} unidade(s) exibida(s)`;
}

async function loadUsers() {
    const users = await api("/admin/api/users");
    const body = document.getElementById("users-body");
    body.replaceChildren();
    if (!users.length) emptyRow(body, 5, "Nenhum usuário cadastrado.");
    for (const user of users) {
        const row = document.createElement("tr");
        cell(row, user.nome, "unit-name");
        cell(row, user.usuario);
        cell(row, user.perfil === "administrador" ? "Administrador" : "Operador");
        const status = document.createElement("span");
        status.className = `badge${user.ativo ? "" : " inactive"}`;
        status.textContent = user.ativo ? "Ativo" : "Inativo";
        const statusCell = document.createElement("td");
        statusCell.append(status);
        row.append(statusCell);
        const actions = document.createElement("td");
        actions.className = "row-actions";
        actions.append(actionButton("Editar", "edit-user", user.id));
        row.append(actions);
        body.append(row);
    }
}

async function loadAudit() {
    const entries = await api("/admin/api/audit?limit=200");
    renderAuditRows(document.getElementById("audit-body"), entries, 6, true);
}

async function showView(name) {
    if (!views[name]) return;
    for (const [key, view] of Object.entries(views)) view.hidden = key !== name;
    document.getElementById("page-title").textContent = titles[name];
    for (const button of document.querySelectorAll(".nav-item[data-view]")) {
        button.classList.toggle("is-active", button.dataset.view === name);
    }
    document.getElementById("sidebar").classList.remove("is-open");
    document.getElementById("menu-button").setAttribute("aria-expanded", "false");
    showMessage("");
    try {
        if (name === "dashboard") await loadDashboard();
        if (name === "units") await loadUnits();
        if (name === "users") await loadUsers();
        if (name === "audit") await loadAudit();
    } catch (error) {
        showMessage(error.message);
    }
}

function createContactRow(contact = {}) {
    const row = document.createElement("div");
    row.className = "contact-row";
    if (contact.id) row.dataset.id = contact.id;

    const type = document.createElement("select");
    type.className = "contact-kind";
    type.setAttribute("aria-label", "Tipo de contato");
    for (const [value, label] of [
        ["ramal", "Ramal"],
        ["telefone_fixo", "Telefone fixo"],
        ["whatsapp", "WhatsApp"],
        ["email", "E-mail"],
        ["telefone_alternativo", "Telefone alternativo"],
        ["outro", "Outro"],
    ]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        type.append(option);
    }
    type.value = contact.tipo || "ramal";

    const value = document.createElement("input");
    value.className = "contact-value";
    value.maxLength = 100;
    value.placeholder = "Valor do contato";
    value.setAttribute("aria-label", "Valor do contato");
    value.value = contact.valor || "";

    const description = document.createElement("input");
    description.className = "contact-description";
    description.maxLength = 255;
    description.placeholder = "Finalidade ou observação";
    description.setAttribute("aria-label", "Finalidade ou observação");
    description.value = contact.descricao || "";

    const principalLabel = document.createElement("label");
    principalLabel.className = "contact-principal";
    const principal = document.createElement("input");
    principal.type = "checkbox";
    principal.className = "contact-is-principal";
    principal.checked = Boolean(contact.principal);
    principalLabel.append(principal, document.createTextNode("Principal"));

    const activeLabel = document.createElement("label");
    activeLabel.className = "contact-active";
    const active = document.createElement("input");
    active.type = "checkbox";
    active.className = "contact-is-active";
    active.checked = contact.ativo !== false;
    activeLabel.append(active, document.createTextNode("Ativo"));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "contact-remove";
    remove.textContent = "Remover";
    remove.addEventListener("click", () => {
        if (row.dataset.id) state.removedContactIds.add(Number(row.dataset.id));
        row.remove();
    });

    row.append(type, value, description, principalLabel, activeLabel, remove);
    return row;
}

function openUnitDialog(unit = null) {
    state.editingUnitId = unit?.id || null;
    state.removedContactIds = new Set();
    document.getElementById("unit-dialog-title").textContent = unit ? "Editar unidade" : "Nova unidade";
    document.getElementById("unit-name").value = unit?.nome || "";
    document.getElementById("unit-category").value = unit?.categoria || "";
    document.getElementById("unit-comarca").value = unit?.comarca || "";
    document.getElementById("unit-description").value = unit?.descricao || "";
    document.getElementById("unit-competencies").value = (unit?.competencias || []).join("\n");
    document.getElementById("unit-form-message").textContent = "";
    const editor = document.getElementById("contacts-editor");
    editor.replaceChildren();
    for (const contact of unit?.contatos || []) editor.append(createContactRow(contact));
    if (!unit) editor.append(createContactRow());
    document.getElementById("unit-dialog").showModal();
}

async function saveUnit(event) {
    event.preventDefault();
    const button = document.getElementById("save-unit-button");
    const message = document.getElementById("unit-form-message");
    button.disabled = true;
    message.textContent = "";
    const body = {
        nome: document.getElementById("unit-name").value.trim(),
        categoria: document.getElementById("unit-category").value.trim(),
        comarca: document.getElementById("unit-comarca").value.trim() || null,
        descricao: document.getElementById("unit-description").value.trim() || null,
        competencias: document.getElementById("unit-competencies").value
            .split("\n")
            .map((competencia) => competencia.trim())
            .filter(Boolean),
    };

    try {
        let unitId = state.editingUnitId;
        if (unitId) {
            await api(`/admin/api/units/${unitId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        } else {
            const created = await api("/admin/api/units", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...body, contatos: [] }),
            });
            unitId = created.id;
        }

        for (const contactId of state.removedContactIds) {
            await api(`/admin/api/contacts/${contactId}`, { method: "DELETE" });
        }
        for (const row of document.querySelectorAll("#contacts-editor .contact-row")) {
            const value = row.querySelector(".contact-value").value.trim();
            if (!value) continue;
            const contact = {
                tipo: row.querySelector(".contact-kind").value,
                valor: value,
                descricao: row.querySelector(".contact-description").value.trim() || null,
                principal: row.querySelector(".contact-is-principal").checked,
                ativo: row.querySelector(".contact-is-active").checked,
            };
            if (row.dataset.id) {
                await api(`/admin/api/contacts/${row.dataset.id}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(contact),
                });
            } else {
                await api(`/admin/api/units/${unitId}/contacts`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(contact),
                });
            }
        }
        document.getElementById("unit-dialog").close();
        showMessage("Unidade e contatos salvos.", false);
        await loadUnits();
        await loadDashboard();
    } catch (error) {
        message.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

async function toggleUnit(unitId, active) {
    try {
        await api(`/admin/api/units/${unitId}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ativo: active }),
        });
        showMessage(active ? "Unidade reativada." : "Unidade desativada.", false);
        await loadUnits();
        await loadDashboard();
    } catch (error) {
        showMessage(error.message);
    }
}

function openUserDialog(user = null) {
    state.editingUserId = user?.id || null;
    document.getElementById("user-dialog-title").textContent = user ? "Editar usuário" : "Novo usuário";
    document.getElementById("user-name").value = user?.nome || "";
    document.getElementById("user-username").value = user?.usuario || "";
    document.getElementById("user-username").readOnly = Boolean(user);
    document.getElementById("user-profile").value = user?.perfil || "operador";
    document.getElementById("user-active").checked = user?.ativo !== false;
    document.getElementById("user-active").disabled = user?.id === state.user.id;
    document.getElementById("user-password").value = "";
    document.getElementById("user-password").required = !user;
    document.getElementById("user-password-label").textContent = user ? "Nova senha (opcional)" : "Senha *";
    document.getElementById("user-form-message").textContent = "";
    document.getElementById("user-dialog").showModal();
}

async function saveUser(event) {
    event.preventDefault();
    const message = document.getElementById("user-form-message");
    message.textContent = "";
    const body = {
        nome: document.getElementById("user-name").value.trim(),
        perfil: document.getElementById("user-profile").value,
    };
    const password = document.getElementById("user-password").value;
    if (password) body.senha = password;
    if (state.editingUserId) {
        body.ativo = document.getElementById("user-active").checked;
    } else {
        body.usuario = document.getElementById("user-username").value.trim();
        if (!password) {
            message.textContent = "Informe uma senha com ao menos 12 caracteres.";
            return;
        }
    }
    try {
        await api(
            state.editingUserId
                ? `/admin/api/users/${state.editingUserId}`
                : "/admin/api/users",
            {
                method: state.editingUserId ? "PATCH" : "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            },
        );
        document.getElementById("user-dialog").close();
        showMessage("Usuário salvo.", false);
        await loadUsers();
    } catch (error) {
        message.textContent = error.message;
    }
}

async function startPanel() {
    try {
        const response = await fetch("/admin/api/session", { credentials: "same-origin" });
        if (!response.ok) {
            window.location.assign("/admin/login");
            return;
        }
        const data = await response.json();
        state.csrfToken = data.csrf_token;
        state.user = data.usuario;
        document.getElementById("current-user").textContent = data.usuario.nome;
        document.getElementById("current-role").textContent = data.usuario.perfil;
        for (const item of document.querySelectorAll(".admin-only")) {
            item.hidden = data.usuario.perfil !== "administrador";
        }
        await showView("dashboard");
    } catch (error) {
        showMessage(error.message);
    }
}

document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
});

document.querySelectorAll("[data-open-unit]").forEach((button) => {
    button.addEventListener("click", () => openUnitDialog());
});

document.getElementById("unit-filters").addEventListener("submit", async (event) => {
    event.preventDefault();
    await loadUnits().catch((error) => showMessage(error.message));
});

document.getElementById("clear-filters").addEventListener("click", async () => {
    document.getElementById("unit-filters").reset();
    await loadUnits().catch((error) => showMessage(error.message));
});

document.getElementById("units-body").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    if (button.dataset.action === "toggle-unit") {
        await toggleUnit(Number(button.dataset.id), button.textContent === "Reativar");
        return;
    }
    if (button.dataset.action === "edit-unit") {
        try {
            openUnitDialog(await api(`/admin/api/units/${button.dataset.id}`));
        } catch (error) {
            showMessage(error.message);
        }
    }
});

document.getElementById("add-contact-button").addEventListener("click", () => {
    document.getElementById("contacts-editor").append(createContactRow());
});
document.getElementById("unit-form").addEventListener("submit", saveUnit);
document.getElementById("new-user-button").addEventListener("click", () => openUserDialog());
document.getElementById("user-form").addEventListener("submit", saveUser);

document.getElementById("users-body").addEventListener("click", async (event) => {
    const button = event.target.closest('button[data-action="edit-user"]');
    if (!button) return;
    try {
        const users = await api("/admin/api/users");
        const user = users.find((item) => item.id === Number(button.dataset.id));
        if (user) openUserDialog(user);
    } catch (error) {
        showMessage(error.message);
    }
});

document.querySelectorAll(".close-dialog").forEach((button) => {
    button.addEventListener("click", () => button.closest("dialog").close());
});

document.getElementById("logout-button").addEventListener("click", async () => {
    try {
        await api("/admin/api/logout", { method: "POST" });
        window.location.assign("/admin/login");
    } catch (error) {
        showMessage(error.message);
    }
});

document.getElementById("menu-button").addEventListener("click", (event) => {
    const sidebar = document.getElementById("sidebar");
    const isOpen = sidebar.classList.toggle("is-open");
    event.currentTarget.setAttribute("aria-expanded", String(isOpen));
});

document.getElementById("about-button").addEventListener("click", () => {
    document.getElementById("about-dialog").showModal();
});

startPanel();