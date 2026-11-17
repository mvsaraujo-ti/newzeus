from getpass import getpass

from sqlalchemy import select

from app.database.config import engine, SessionLocal
from app.models import SessaoAdmin, UsuarioAdmin
from app.services.auth_service import (
    AdministradorInicialJaExiste,
    UsuarioAdminJaExiste,
    criar_primeiro_administrador,
)


def main() -> int:
    UsuarioAdmin.__table__.create(bind=engine, checkfirst=True)
    SessaoAdmin.__table__.create(bind=engine, checkfirst=True)

    nome = input("Nome: ").strip()
    usuario = input("Usuário: ").strip()
    senha = getpass("Senha (mínimo 12 caracteres): ")
    confirmacao = getpass("Confirme a senha: ")

    if senha != confirmacao:
        print("As senhas não conferem. Nenhum usuário foi criado.")
        return 1

    try:
        administrador = criar_primeiro_administrador(
            SessionLocal,
            nome,
            usuario,
            senha,
        )
    except (ValueError, UsuarioAdminJaExiste, AdministradorInicialJaExiste) as erro:
        print(f"Não foi possível criar o administrador: {erro}")
        return 1

    print(f"Administrador {administrador.usuario!r} criado com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())