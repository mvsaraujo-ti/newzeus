import re
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SessaoAdmin, UsuarioAdmin


PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{3,80}$")


class UsuarioAdminJaExiste(Exception):
    pass


class AdministradorInicialJaExiste(Exception):
    pass


def normalizar_usuario(usuario: str) -> str:
    return usuario.strip().casefold()


def validar_usuario(usuario: str) -> str:
    usuario_normalizado = normalizar_usuario(usuario)
    if not _USERNAME_PATTERN.fullmatch(usuario_normalizado):
        raise ValueError(
            "O usuário deve ter de 3 a 80 caracteres: letras, números, ponto, hífen ou sublinhado."
        )
    return usuario_normalizado


def hash_senha(senha: str) -> str:
    if len(senha) < 12:
        raise ValueError("A senha precisa ter pelo menos 12 caracteres.")
    if len(senha) > 1024:
        raise ValueError("A senha excede o tamanho máximo permitido.")
    return PASSWORD_HASHER.hash(senha)


def verificar_senha(senha_hash: str | None, senha: str) -> bool:
    hash_para_verificar = senha_hash or _DUMMY_PASSWORD_HASH
    try:
        senha_valida = PASSWORD_HASHER.verify(hash_para_verificar, senha)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False
    return senha_valida and senha_hash is not None


def autenticar_usuario(
    session: Session,
    usuario: str,
    senha: str,
) -> UsuarioAdmin | None:
    usuario_normalizado = normalizar_usuario(usuario)
    registro = session.scalar(
        select(UsuarioAdmin).where(
            func.lower(UsuarioAdmin.usuario) == usuario_normalizado
        )
    )
    senha_valida = verificar_senha(
        registro.senha_hash if registro else None,
        senha,
    )
    if registro is None or not senha_valida or not registro.ativo:
        return None
    return registro


def criar_primeiro_administrador(
    session_factory,
    nome: str,
    usuario: str,
    senha: str,
) -> UsuarioAdmin:
    nome = nome.strip()
    if not nome or len(nome) > 160:
        raise ValueError("O nome precisa ter de 1 a 160 caracteres.")
    usuario_normalizado = validar_usuario(usuario)
    senha_hash = hash_senha(senha)

    session = session_factory()
    try:
        session.execute(text("BEGIN IMMEDIATE"))
        administrador_existente = session.scalar(
            select(UsuarioAdmin.id).where(UsuarioAdmin.perfil == "administrador")
        )
        if administrador_existente is not None:
            raise AdministradorInicialJaExiste(
                "Já existe um administrador; o cadastro inicial não pode ser repetido."
            )

        registro = UsuarioAdmin(
            nome=nome,
            usuario=usuario_normalizado,
            senha_hash=senha_hash,
            perfil="administrador",
            ativo=True,
        )
        session.add(registro)
        session.commit()
        return registro
    except IntegrityError as erro:
        session.rollback()
        raise UsuarioAdminJaExiste("Esse nome de usuário já está cadastrado.") from erro
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def criar_sessao_admin(
    session: Session,
    usuario: UsuarioAdmin,
    token: str,
    csrf_token: str,
    duracao: timedelta,
) -> SessaoAdmin:
    expira_em = datetime.now(timezone.utc).replace(tzinfo=None) + duracao
    sessao = SessaoAdmin(
        usuario_id=usuario.id,
        token_hash=hash_token(token),
        csrf_hash=hash_token(csrf_token),
        expira_em=expira_em,
    )
    session.add(sessao)
    session.commit()
    return sessao