from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


def test_contatos_sao_renderizados_com_text_nodes_sem_html_dinamico():
    source = (FRONTEND_DIR / "chat.js").read_text(encoding="utf-8")

    assert "elemento.textContent = valor" in source
    assert 'criarTexto("strong", "contact-value", contato.valor)' in source
    assert "innerHTML" not in source
    assert "insertAdjacentHTML" not in source


def test_contexto_de_esclarecimento_nao_persiste_nem_e_compartilhado():
    source = (FRONTEND_DIR / "chat.js").read_text(encoding="utf-8")

    assert "let esclarecimentoPendente = null" in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
