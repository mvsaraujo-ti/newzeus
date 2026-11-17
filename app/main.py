
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from app.api.admin_auth import router as admin_auth_router
from app.api.admin_panel import router as admin_panel_router
from app.core.security import (
    SESSION_COOKIE_SECURE,
    SESSION_MAX_AGE_SECONDS,
    SESSION_SECRET,
)
from app.database.config import engine
from app.database.migrations import remover_unicidade_global_nome_unidade
from app.services.ramais_importer import importar_ramais_json
from app.services.competency_migrator import migrar_competencias_descricao
from app.services.ramais_service import buscar_ramal, formatar_resposta


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    importar_ramais_json()
    migrar_competencias_descricao()
    remover_unicidade_global_nome_unidade(engine)
    yield


app = FastAPI(
    title="ZEUS",
    description="Sistema de consulta e gerenciamento de contatos institucionais",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="oi_zeus_session",
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=SESSION_COOKIE_SECURE,
)
app.include_router(admin_auth_router)
app.include_router(admin_panel_router)

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)


class Pergunta(BaseModel):
    mensagem: str


@app.get("/")
def inicio():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/chat")
def chat(pergunta: Pergunta):
    resultado = buscar_ramal(pergunta.mensagem)
    return {
        "resposta": formatar_resposta(resultado),
        "dados": resultado,
    }
