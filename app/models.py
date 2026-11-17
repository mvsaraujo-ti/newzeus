from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Unidade(Base):
    __tablename__ = "unidades"
    __table_args__ = (
        CheckConstraint("length(trim(nome)) > 0", name="ck_unidades_nome_nao_vazio"),
        CheckConstraint(
            "length(trim(categoria)) > 0",
            name="ck_unidades_categoria_nao_vazia",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    categoria: Mapped[str] = mapped_column(String(100), nullable=False)
    comarca: Mapped[str | None] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(Text)
    endereco: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(254))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=agora_utc
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=agora_utc, onupdate=agora_utc
    )

    contatos: Mapped[list["Contato"]] = relationship(
        back_populates="unidade",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    competencias: Mapped[list["CompetenciaUnidade"]] = relationship(
        back_populates="unidade",
        cascade="all, delete-orphan",
        order_by="CompetenciaUnidade.nome",
    )


class Contato(Base):
    __tablename__ = "contatos"
    __table_args__ = (
        UniqueConstraint(
            "unidade_id",
            "tipo",
            "valor",
            name="uq_contatos_unidade_tipo_valor",
        ),
        CheckConstraint("length(trim(tipo)) > 0", name="ck_contatos_tipo_nao_vazio"),
        CheckConstraint("length(trim(valor)) > 0", name="ck_contatos_valor_nao_vazio"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unidade_id: Mapped[int] = mapped_column(
        ForeignKey("unidades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    valor: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(255))
    principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    unidade: Mapped[Unidade] = relationship(back_populates="contatos")


class CompetenciaUnidade(Base):
    __tablename__ = "competencias_unidade"
    __table_args__ = (
        UniqueConstraint(
            "unidade_id",
            "nome",
            name="uq_competencia_unidade_nome",
        ),
        CheckConstraint("length(trim(nome)) > 0", name="ck_competencia_nome_nao_vazio"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unidade_id: Mapped[int] = mapped_column(
        ForeignKey("unidades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=agora_utc
    )

    unidade: Mapped[Unidade] = relationship(back_populates="competencias")


class UsuarioAdmin(Base):
    __tablename__ = "usuarios_admin"
    __table_args__ = (
        CheckConstraint("length(trim(nome)) > 0", name="ck_usuario_admin_nome"),
        CheckConstraint("length(trim(usuario)) > 0", name="ck_usuario_admin_usuario"),
        CheckConstraint(
            "perfil IN ('administrador', 'operador')",
            name="ck_usuario_admin_perfil",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    usuario: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[str] = mapped_column(String(30), nullable=False, default="operador")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=agora_utc
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=agora_utc, onupdate=agora_utc
    )

    sessoes: Mapped[list["SessaoAdmin"]] = relationship(
        back_populates="usuario_admin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    auditorias: Mapped[list["Auditoria"]] = relationship(back_populates="usuario_admin")


class SessaoAdmin(Base):
    __tablename__ = "sessoes_admin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios_admin.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=agora_utc
    )

    usuario_admin: Mapped[UsuarioAdmin] = relationship(back_populates="sessoes")


class Auditoria(Base):
    __tablename__ = "auditorias"
    __table_args__ = (
        CheckConstraint("length(trim(acao)) > 0", name="ck_auditoria_acao"),
        CheckConstraint("length(trim(entidade)) > 0", name="ck_auditoria_entidade"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios_admin.id", ondelete="SET NULL"), nullable=True, index=True
    )
    acao: Mapped[str] = mapped_column(String(60), nullable=False)
    entidade: Mapped[str] = mapped_column(String(60), nullable=False)
    registro_id: Mapped[int | None] = mapped_column(Integer)
    detalhes: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    data_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=agora_utc, index=True
    )

    usuario_admin: Mapped[UsuarioAdmin | None] = relationship(
        back_populates="auditorias"
    )