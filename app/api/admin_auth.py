import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import SESSION_MAX_AGE_SECONDS
from app.database.config import get_db
from app.models import SessaoAdmin, UsuarioAdmin
from app.services.auth_service import (
    autenticar_usuario,
    criar_sessao_admin,
    hash_token,
    normalizar_usuario,
)


BASE_DIR = Path(__file__).resolve().parents[2]
LOGIN_PAGE = BASE_DIR / "frontend" / "admin" / "login.html"
PANEL_PAGE = BASE_DIR / "frontend" / "admin" / "index.html"
router = APIRouter(prefix="/admin", tags=["admin-auth"])

MAX_TENTATIVAS_LOGIN = 5
JANELA_TENTATIVAS_SEGUNDOS = 15 * 60
_tentativas_login: dict[str, list[float]] = {}
_lock_tentativas = threading.Lock()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    senha: Annotated[str, StringConstraints(min_length=1, max_length=1024)]


def _tentativas_atuais(chave: str, agora: float) -> list[float]:
    tentativas = [
        instante
        for instante in _tentativas_login.get(chave, [])
        if agora - instante < JANELA_TENTATIVAS_SEGUNDOS
    ]
    _tentativas_login[chave] = tentativas
    return tentativas


def _login_bloqueado(chave: str) -> bool:
    with _lock_tentativas:
        return len(_tentativas_atuais(chave, time.monotonic())) >= MAX_TENTATIVAS_LOGIN


def _registrar_falha_login(chave: str) -> None:
    with _lock_tentativas:
        tentativas = _tentativas_atuais(chave, time.monotonic())
        tentativas.append(time.monotonic())


def _limpar_tentativas_login(chave: str) -> None:
    with _lock_tentativas:
        _tentativas_login.pop(chave, None)


def _falha_autenticacao(status_code: int = 401) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail="Não foi possível autenticar com as credenciais fornecidas.",
    )


def _validar_csrf(request: Request, token_esperado: str | None) -> bool:
    token_recebido = request.headers.get("x-csrf-token", "")
    return bool(
        token_esperado
        and token_recebido
        and secrets.compare_digest(token_esperado, token_recebido)
    )


def get_current_admin(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> UsuarioAdmin:
    token = request.session.get("admin_session_id")
    csrf_token = request.session.get("csrf_token")
    if not token or not csrf_token:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")

    registro_sessao = session.scalar(
        select(SessaoAdmin)
        .options(joinedload(SessaoAdmin.usuario_admin))
        .where(
            SessaoAdmin.token_hash == hash_token(token),
            SessaoAdmin.expira_em > datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    if registro_sessao is None or not registro_sessao.usuario_admin.ativo:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Autenticação necessária.")

    if not secrets.compare_digest(
        registro_sessao.csrf_hash,
        hash_token(csrf_token),
    ):
        raise HTTPException(status_code=403, detail="Token CSRF inválido.")

    if request.method not in {"GET", "HEAD", "OPTIONS"} and not _validar_csrf(
        request,
        csrf_token,
    ):
        raise HTTPException(status_code=403, detail="Token CSRF inválido.")

    return registro_sessao.usuario_admin


def require_profile(*perfis_permitidos: str):
    def verificar_perfil(
        usuario: Annotated[UsuarioAdmin, Depends(get_current_admin)],
    ) -> UsuarioAdmin:
        if usuario.perfil not in perfis_permitidos:
            raise HTTPException(status_code=403, detail="Permissão insuficiente.")
        return usuario

    return verificar_perfil


@router.get("/login", include_in_schema=False)
def admin_login_page():
    return FileResponse(LOGIN_PAGE)


@router.get("/api/csrf")
def emitir_csrf(request: Request):
    token = request.session.get("csrf_token") or request.session.get("login_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["login_csrf_token"] = token
    return {"csrf_token": token}


@router.post("/api/login")
def login(
    dados: LoginRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    x_csrf_token: Annotated[str | None, Header()] = None,
):
    csrf_esperado = request.session.get("login_csrf_token")
    if not csrf_esperado or not x_csrf_token or not secrets.compare_digest(
        csrf_esperado,
        x_csrf_token,
    ):
        raise HTTPException(status_code=403, detail="Token CSRF inválido.")

    chave = request.client.host if request.client else "unknown"
    if _login_bloqueado(chave):
        raise _falha_autenticacao(status_code=429)

    usuario = autenticar_usuario(session, dados.usuario, dados.senha)
    if usuario is None:
        _registrar_falha_login(chave)
        raise _falha_autenticacao()

    _limpar_tentativas_login(chave)
    token_sessao = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    criar_sessao_admin(
        session,
        usuario,
        token_sessao,
        csrf_token,
        timedelta(seconds=SESSION_MAX_AGE_SECONDS),
    )

    request.session.clear()
    request.session["admin_session_id"] = token_sessao
    request.session["csrf_token"] = csrf_token
    return {
        "autenticado": True,
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "usuario": usuario.usuario,
            "perfil": usuario.perfil,
        },
    }


@router.get("/api/session")
def verificar_sessao(
    request: Request,
    usuario: Annotated[UsuarioAdmin, Depends(get_current_admin)],
):
    return {
        "autenticado": True,
        "csrf_token": request.session["csrf_token"],
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "usuario": usuario.usuario,
            "perfil": usuario.perfil,
        },
    }


@router.post("/api/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    usuario: Annotated[UsuarioAdmin, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db)],
):
    token = request.session.get("admin_session_id")
    registro_sessao = session.scalar(
        select(SessaoAdmin).where(SessaoAdmin.token_hash == hash_token(token))
    )
    if registro_sessao is not None:
        session.delete(registro_sessao)
        session.commit()
    request.session.clear()
    response.delete_cookie(
        "oi_zeus_session",
        path="/",
        httponly=True,
        samesite="lax",
    )


@router.get("")
def admin_home(
    usuario: Annotated[UsuarioAdmin, Depends(get_current_admin)],
):
    return FileResponse(PANEL_PAGE)