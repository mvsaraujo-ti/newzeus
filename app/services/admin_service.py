import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Auditoria, Contato, Unidade, UsuarioAdmin


def serializar_contato(contato: Contato) -> dict[str, Any]:
    return {
        "id": contato.id,
        "unidade_id": contato.unidade_id,
        "tipo": contato.tipo,
        "valor": contato.valor,
        "descricao": contato.descricao,
        "principal": contato.principal,
        "ativo": contato.ativo,
    }


def serializar_unidade(unidade: Unidade, incluir_contatos: bool = True) -> dict[str, Any]:
    resultado = {
        "id": unidade.id,
        "nome": unidade.nome,
        "categoria": unidade.categoria,
        "comarca": unidade.comarca,
        "descricao": unidade.descricao,
        "ativo": unidade.ativo,
        "competencias": [
            competencia.nome
            for competencia in sorted(unidade.competencias, key=lambda item: item.nome.casefold())
            if competencia.ativo
        ],
        "criado_em": _serializar_data(unidade.criado_em),
        "atualizado_em": _serializar_data(unidade.atualizado_em),
    }
    if incluir_contatos:
        resultado["contatos"] = [
            serializar_contato(contato)
            for contato in sorted(unidade.contatos, key=lambda item: item.id)
        ]
    return resultado


def serializar_usuario(usuario: UsuarioAdmin) -> dict[str, Any]:
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "usuario": usuario.usuario,
        "perfil": usuario.perfil,
        "ativo": usuario.ativo,
        "criado_em": _serializar_data(usuario.criado_em),
        "atualizado_em": _serializar_data(usuario.atualizado_em),
    }


def serializar_auditoria(registro: Auditoria) -> dict[str, Any]:
    try:
        detalhes = json.loads(registro.detalhes)
    except (TypeError, json.JSONDecodeError):
        detalhes = {}
    return {
        "id": registro.id,
        "usuario_id": registro.usuario_id,
        "usuario": registro.usuario_admin.usuario if registro.usuario_admin else None,
        "acao": registro.acao,
        "entidade": registro.entidade,
        "registro_id": registro.registro_id,
        "detalhes": detalhes,
        "data_hora": _serializar_data(registro.data_hora),
    }


def registrar_auditoria(
    session: Session,
    usuario_id: int,
    acao: str,
    entidade: str,
    registro_id: int | None,
    antes: dict[str, Any] | None = None,
    depois: dict[str, Any] | None = None,
) -> Auditoria:
    detalhes = {"antes": antes, "depois": depois}
    registro = Auditoria(
        usuario_id=usuario_id,
        acao=acao,
        entidade=entidade,
        registro_id=registro_id,
        detalhes=json.dumps(detalhes, ensure_ascii=False, sort_keys=True),
    )
    session.add(registro)
    return registro


def buscar_unidade(session: Session, unidade_id: int) -> Unidade | None:
    return session.scalar(
        select(Unidade)
        .options(
            selectinload(Unidade.contatos),
            selectinload(Unidade.competencias),
        )
        .where(Unidade.id == unidade_id)
    )


def snapshot_unidade(unidade: Unidade) -> dict[str, Any]:
    return {
        "nome": unidade.nome,
        "categoria": unidade.categoria,
        "comarca": unidade.comarca,
        "descricao": unidade.descricao,
        "ativo": unidade.ativo,
        "competencias": [
            competencia.nome
            for competencia in sorted(unidade.competencias, key=lambda item: item.nome.casefold())
            if competencia.ativo
        ],
    }


def snapshot_contato(contato: Contato) -> dict[str, Any]:
    return {
        "unidade_id": contato.unidade_id,
        "tipo": contato.tipo,
        "valor": contato.valor,
        "descricao": contato.descricao,
        "principal": contato.principal,
        "ativo": contato.ativo,
    }


def _serializar_data(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None