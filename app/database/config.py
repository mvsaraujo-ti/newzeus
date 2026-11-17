import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
DATABASE_PATH = BASE_DIR / "data" / "oi_zeus.db"
DATABASE_URL = os.getenv(
    "OI_ZEUS_DATABASE_URL",
    f"sqlite:///{DATABASE_PATH.as_posix()}",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def habilitar_chaves_estrangeiras(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()