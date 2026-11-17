from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.admin_auth import get_current_admin, require_profile
from app.database.config import get_db
from app.models import (
    Auditoria,
    CompetenciaUnidade,
    Contato,
    SessaoAdmin,
    Unidade,
    UsuarioAdmin,
)
from app.schemas import (
    ContatoCreate,
    ContatoPatch,
    UnidadeCreate,
    UnidadePatch,
    UnidadeStatus,
    UsuarioCreate,
    UsuarioPatch,
)
from app.services.admin_service import (
    buscar_unidade,
    registrar_auditoria,
    serializar_auditoria,
    serializar_contato,
    serializar_unidade,
    serializar_usuario,
    snapshot_contato,
    snapshot_unidade,
)
from app.services.auth_service import hash_senha, validar_usuario
from app.services.text_normalizer import normalizar_texto


router = APIRouter(prefix="/admin/api", tags=["admin-panel"])
Admin = Annotated[UsuarioAdmin, Depends(get_current_admin)]
Administrador = Annotated[UsuarioAdmin, Depends(require_profile("administrador"))]
Database = Annotated[Session, Depends(get_db)]


def _buscar_ou_404(session: Session, unidade_id: int) -> Unidade:
    unidade = buscar_unidade(session, unidade_id)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada.")
    return unidade


def _verificar_nome_unidade(
    session: Session,
    nome: str,
    comarca: str | None,
    unidade_id: int | None = None,
) -> None:
    nome_normalizado = normalizar_texto(nome)
    comarca_normalizada = normalizar_texto(comarca or "")
    nomes = session.execute(
        select(Unidade.id, Unidade.nome, Unidade.comarca)
    ).all()
    if any(
        atual_id != unidade_id
        and normalizar_texto(atual_nome) == nome_normalizado
        and normalizar_texto(atual_comarca or "") == comarca_normalizada
        for atual_id, atual_nome, atual_comarca in nomes
    ):
        raise HTTPException(
            status_code=409,
            detail="Já existe uma unidade com esse nome.",
        )


def _salvar_transacao(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as erro:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A alteração conflita com um registro já cadastrado.",
        ) from erro


def _flush_transacao(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as erro:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A alteração conflita com um registro já cadastrado.",
        ) from erro


def _contato_por_id(session: Session, contato_id: int) -> Contato:
    contato = session.get(Contato, contato_id)
    if contato is None:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    return contato


def _atualizar_competencias(
    session: Session,
    unidade: Unidade,
    nomes: list[str],
    usuario_id: int,
) -> None:
    desejadas = {normalizar_texto(nome): nome for nome in nomes}
    existentes = list(unidade.competencias)
    por_nome = {normalizar_texto(item.nome): item for item in existentes}

    for competencia in existentes:
        chave = normalizar_texto(competencia.nome)
        deve_estar_ativa = chave in desejadas
        if competencia.ativo == deve_estar_ativa:
            continue
        antes = {"nome": competencia.nome, "ativo": competencia.ativo}
        competencia.ativo = deve_estar_ativa
        _flush_transacao(session)
        registrar_auditoria(
            session,
            usuario_id,
            "edicao" if deve_estar_ativa else "exclusao_logica",
            "competencia",
            competencia.id,
            antes=antes,
            depois={"nome": competencia.nome, "ativo": competencia.ativo},
        )

    for chave, nome in desejadas.items():
        if chave in por_nome:
            continue
        competencia = CompetenciaUnidade(
            unidade_id=unidade.id,
            nome=nome,
            ativo=True,
        )
        session.add(competencia)
        unidade.competencias.append(competencia)
        _flush_transacao(session)
        registrar_auditoria(
            session,
            usuario_id,
            "cadastro",
            "competencia",
            competencia.id,
            depois={"nome": competencia.nome, "ativo": True},
        )


@router.get("/dashboard")
def dashboard(request: Request, session: Database, _usuario: Admin):
    total_unidades = session.scalar(select(func.count()).select_from(Unidade)) or 0
    unidades_ativas = session.scalar(
        select(func.count()).select_from(Unidade).where(Unidade.ativo.is_(True))
    ) or 0
    total_contatos = session.scalar(select(func.count()).select_from(Contato)) or 0
    contatos_ativos = session.scalar(
        select(func.count()).select_from(Contato).where(Contato.ativo.is_(True))
    ) or 0
    categorias = session.scalars(
        select(Unidade.categoria).distinct().order_by(Unidade.categoria)
    ).all()
    comarcas = session.scalars(
        select(Unidade.comarca)
        .where(Unidade.comarca.is_not(None), Unidade.comarca != "")
        .distinct()
        .order_by(Unidade.comarca)
    ).all()
    distribuicao_categorias = session.execute(
        select(Unidade.categoria, func.count(Unidade.id))
        .group_by(Unidade.categoria)
        .order_by(func.count(Unidade.id).desc(), Unidade.categoria)
    ).all()
    distribuicao_comarcas = session.execute(
        select(Unidade.comarca, func.count(Unidade.id))
        .where(Unidade.comarca.is_not(None), Unidade.comarca != "")
        .group_by(Unidade.comarca)
        .order_by(func.count(Unidade.id).desc(), Unidade.comarca)
    ).all()
    recentes = []
    if _usuario.perfil == "administrador":
        recentes = session.scalars(
            select(Auditoria)
            .options(joinedload(Auditoria.usuario_admin))
            .order_by(Auditoria.data_hora.desc(), Auditoria.id.desc())
            .limit(8)
        ).all()
    return {
        "versao": request.app.version,
        "total_unidades": total_unidades,
        "unidades_ativas": unidades_ativas,
        "unidades_inativas": total_unidades - unidades_ativas,
        "total_contatos": total_contatos,
        "contatos_ativos": contatos_ativos,
        "total_categorias": len(categorias),
        "total_comarcas": len(comarcas),
        "categorias": categorias,
        "comarcas": comarcas,
        "distribuicao_categorias": [
            {"nome": nome, "unidades": quantidade}
            for nome, quantidade in distribuicao_categorias
        ],
        "distribuicao_comarcas": [
            {"nome": nome, "unidades": quantidade}
            for nome, quantidade in distribuicao_comarcas
        ],
        "alteracoes_recentes": [serializar_auditoria(item) for item in recentes],
        "consultas_registradas": None,
    }


@router.get("/units")
def listar_unidades(
    session: Database,
    _usuario: Admin,
    busca: Annotated[str | None, Query(max_length=100)] = None,
    categoria: Annotated[str | None, Query(max_length=100)] = None,
    comarca: Annotated[str | None, Query(max_length=120)] = None,
    ativo: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    consulta = select(Unidade).options(
        selectinload(Unidade.contatos),
        selectinload(Unidade.competencias),
    )
    if busca:
        consulta = consulta.where(Unidade.nome.ilike(f"%{busca.strip()}%"))
    if categoria:
        consulta = consulta.where(Unidade.categoria == categoria.strip())
    if comarca:
        consulta = consulta.where(Unidade.comarca == comarca.strip())
    if ativo is not None:
        consulta = consulta.where(Unidade.ativo.is_(ativo))
    unidades = session.scalars(
        consulta.order_by(Unidade.nome).limit(limit).offset(offset)
    ).all()
    return [serializar_unidade(unidade) for unidade in unidades]


@router.get("/units/{unidade_id}")
def obter_unidade(unidade_id: int, session: Database, _usuario: Admin):
    return serializar_unidade(_buscar_ou_404(session, unidade_id))


@router.post("/units", status_code=201)
def cadastrar_unidade(
    dados: UnidadeCreate,
    session: Database,
    usuario: Admin,
):
    _verificar_nome_unidade(session, dados.nome, dados.comarca)
    unidade = Unidade(
        **dados.model_dump(exclude={"contatos", "competencias"}),
    )
    session.add(unidade)
    try:
        _flush_transacao(session)
        for item in dados.contatos:
            contato = Contato(unidade_id=unidade.id, **item.model_dump())
            session.add(contato)
            _flush_transacao(session)
            registrar_auditoria(
                session,
                usuario.id,
                "cadastro",
                "contato",
                contato.id,
                depois=snapshot_contato(contato),
            )
        for nome in dados.competencias:
            competencia = CompetenciaUnidade(
                unidade_id=unidade.id,
                nome=nome,
                ativo=True,
            )
            session.add(competencia)
            _flush_transacao(session)
            registrar_auditoria(
                session,
                usuario.id,
                "cadastro",
                "competencia",
                competencia.id,
                depois={"nome": competencia.nome, "ativo": True},
            )
        registrar_auditoria(
            session,
            usuario.id,
            "cadastro",
            "unidade",
            unidade.id,
            depois=snapshot_unidade(unidade),
        )
        _salvar_transacao(session)
    except HTTPException:
        session.rollback()
        raise
    return serializar_unidade(unidade)


@router.patch("/units/{unidade_id}")
def editar_unidade(
    unidade_id: int,
    dados: UnidadePatch,
    session: Database,
    usuario: Admin,
):
    unidade = _buscar_ou_404(session, unidade_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    competencias = alteracoes.pop("competencias", None)
    competencias_informadas = "competencias" in dados.model_fields_set
    if not alteracoes:
        if not competencias_informadas:
            raise HTTPException(status_code=422, detail="Informe ao menos um campo.")
    if "nome" in alteracoes or "comarca" in alteracoes:
        _verificar_nome_unidade(
            session,
            alteracoes.get("nome", unidade.nome),
            alteracoes.get("comarca", unidade.comarca),
            unidade_id,
        )
    antes = snapshot_unidade(unidade)
    competencias_atuais = {
        normalizar_texto(item.nome)
        for item in unidade.competencias
        if item.ativo
    }
    competencias_novas = {
        normalizar_texto(nome) for nome in (competencias or [])
    }
    scalar_inalterado = all(
        getattr(unidade, campo) == valor for campo, valor in alteracoes.items()
    )
    competencias_inalteradas = (
        not competencias_informadas or competencias_atuais == competencias_novas
    )
    if scalar_inalterado and competencias_inalteradas:
        return serializar_unidade(unidade)
    for campo, valor in alteracoes.items():
        setattr(unidade, campo, valor)
    _flush_transacao(session)
    if competencias_informadas:
        _atualizar_competencias(session, unidade, competencias or [], usuario.id)
    registrar_auditoria(
        session,
        usuario.id,
        "edicao",
        "unidade",
        unidade.id,
        antes=antes,
        depois=snapshot_unidade(unidade),
    )
    _salvar_transacao(session)
    return serializar_unidade(unidade)


@router.patch("/units/{unidade_id}/status")
def alterar_status_unidade(
    unidade_id: int,
    dados: UnidadeStatus,
    session: Database,
    usuario: Administrador,
):
    unidade = _buscar_ou_404(session, unidade_id)
    if unidade.ativo == dados.ativo:
        return serializar_unidade(unidade)
    antes = snapshot_unidade(unidade)
    unidade.ativo = dados.ativo
    _flush_transacao(session)
    registrar_auditoria(
        session,
        usuario.id,
        "reativacao" if dados.ativo else "desativacao",
        "unidade",
        unidade.id,
        antes=antes,
        depois=snapshot_unidade(unidade),
    )
    _salvar_transacao(session)
    return serializar_unidade(unidade)


@router.post("/units/{unidade_id}/contacts", status_code=201)
def cadastrar_contato(
    unidade_id: int,
    dados: ContatoCreate,
    session: Database,
    usuario: Admin,
):
    _buscar_ou_404(session, unidade_id)
    contato = Contato(unidade_id=unidade_id, **dados.model_dump())
    session.add(contato)
    _flush_transacao(session)
    registrar_auditoria(
        session,
        usuario.id,
        "cadastro",
        "contato",
        contato.id,
        depois=snapshot_contato(contato),
    )
    _salvar_transacao(session)
    return serializar_contato(contato)


@router.patch("/contacts/{contato_id}")
def editar_contato(
    contato_id: int,
    dados: ContatoPatch,
    session: Database,
    usuario: Admin,
):
    contato = _contato_por_id(session, contato_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    if not alteracoes:
        raise HTTPException(status_code=422, detail="Informe ao menos um campo.")
    antes = snapshot_contato(contato)

    if alteracoes.get("principal") is True:
        outros = session.scalars(
            select(Contato).where(
                Contato.unidade_id == contato.unidade_id,
                Contato.id != contato.id,
                Contato.principal.is_(True),
            )
        ).all()
        for outro in outros:
            anterior = snapshot_contato(outro)
            outro.principal = False
            _flush_transacao(session)
            registrar_auditoria(
                session,
                usuario.id,
                "edicao",
                "contato",
                outro.id,
                antes=anterior,
                depois=snapshot_contato(outro),
            )

    for campo, valor in alteracoes.items():
        setattr(contato, campo, valor)
    _flush_transacao(session)
    depois = snapshot_contato(contato)
    if antes != depois:
        registrar_auditoria(
            session,
            usuario.id,
            "edicao",
            "contato",
            contato.id,
            antes=antes,
            depois=depois,
        )
    _salvar_transacao(session)
    return serializar_contato(contato)


@router.delete("/contacts/{contato_id}")
def excluir_contato_logicamente(
    contato_id: int,
    session: Database,
    usuario: Admin,
):
    contato = _contato_por_id(session, contato_id)
    if not contato.ativo:
        return {"id": contato.id, "ativo": False}
    antes = snapshot_contato(contato)
    contato.ativo = False
    _flush_transacao(session)
    registrar_auditoria(
        session,
        usuario.id,
        "exclusao_logica",
        "contato",
        contato.id,
        antes=antes,
        depois=snapshot_contato(contato),
    )
    _salvar_transacao(session)
    return {"id": contato.id, "ativo": False}


@router.get("/audit")
def listar_auditoria(
    session: Database,
    _usuario: Administrador,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    registros = session.scalars(
        select(Auditoria)
        .options(joinedload(Auditoria.usuario_admin))
        .order_by(Auditoria.data_hora.desc(), Auditoria.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [serializar_auditoria(item) for item in registros]


@router.get("/users")
def listar_usuarios(session: Database, _usuario: Administrador):
    usuarios = session.scalars(
        select(UsuarioAdmin).order_by(UsuarioAdmin.nome)
    ).all()
    return [serializar_usuario(usuario) for usuario in usuarios]


@router.post("/users", status_code=201)
def cadastrar_usuario(
    dados: UsuarioCreate,
    session: Database,
    usuario: Administrador,
):
    nome_usuario = validar_usuario(dados.usuario)
    existentes = session.scalars(select(UsuarioAdmin.usuario)).all()
    if any(atual.casefold() == nome_usuario for atual in existentes):
        raise HTTPException(status_code=409, detail="Esse nome de usuário já existe.")

    novo = UsuarioAdmin(
        nome=dados.nome,
        usuario=nome_usuario,
        senha_hash=hash_senha(dados.senha),
        perfil=dados.perfil,
        ativo=True,
    )
    session.add(novo)
    _flush_transacao(session)
    registrar_auditoria(
        session,
        usuario.id,
        "cadastro",
        "usuario",
        novo.id,
        depois={
            "nome": novo.nome,
            "usuario": novo.usuario,
            "perfil": novo.perfil,
            "ativo": novo.ativo,
        },
    )
    _salvar_transacao(session)
    return serializar_usuario(novo)


@router.patch("/users/{usuario_id}")
def editar_usuario(
    usuario_id: int,
    dados: UsuarioPatch,
    session: Database,
    usuario_atual: Administrador,
):
    alvo = session.get(UsuarioAdmin, usuario_id)
    if alvo is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    alteracoes = dados.model_dump(exclude_unset=True)
    if not alteracoes:
        raise HTTPException(status_code=422, detail="Informe ao menos um campo.")

    if alvo.id == usuario_atual.id and (
        alteracoes.get("ativo") is False
        or alteracoes.get("perfil") == "operador"
    ):
        raise HTTPException(
            status_code=409,
            detail="Não é permitido desativar ou rebaixar o usuário autenticado.",
        )

    novo_perfil = alteracoes.get("perfil", alvo.perfil)
    novo_estado = alteracoes.get("ativo", alvo.ativo)
    removendo_admin_ativo = (
        alvo.perfil == "administrador"
        and alvo.ativo
        and (novo_perfil != "administrador" or not novo_estado)
    )
    if removendo_admin_ativo:
        outros_administradores = session.scalar(
            select(func.count())
            .select_from(UsuarioAdmin)
            .where(
                UsuarioAdmin.perfil == "administrador",
                UsuarioAdmin.ativo.is_(True),
                UsuarioAdmin.id != alvo.id,
            )
        ) or 0
        if outros_administradores == 0:
            raise HTTPException(
                status_code=409,
                detail="O sistema precisa manter ao menos um administrador ativo.",
            )

    antes = {
        "nome": alvo.nome,
        "usuario": alvo.usuario,
        "perfil": alvo.perfil,
        "ativo": alvo.ativo,
    }
    senha_alterada = "senha" in alteracoes
    if senha_alterada:
        alteracoes["senha_hash"] = hash_senha(alteracoes.pop("senha"))
    for campo, valor in alteracoes.items():
        setattr(alvo, campo, valor)

    if senha_alterada or (antes["ativo"] and not alvo.ativo):
        session.query(SessaoAdmin).filter(
            SessaoAdmin.usuario_id == alvo.id
        ).delete(synchronize_session=False)

    _flush_transacao(session)
    depois = {
        "nome": alvo.nome,
        "usuario": alvo.usuario,
        "perfil": alvo.perfil,
        "ativo": alvo.ativo,
    }
    if senha_alterada:
        depois["senha_alterada"] = True
    if antes == {
        "nome": alvo.nome,
        "usuario": alvo.usuario,
        "perfil": alvo.perfil,
        "ativo": alvo.ativo,
    } and not senha_alterada:
        return serializar_usuario(alvo)
    registrar_auditoria(
        session,
        usuario_atual.id,
        "edicao",
        "usuario",
        alvo.id,
        antes=antes,
        depois=depois,
    )
    _salvar_transacao(session)
    return serializar_usuario(alvo)