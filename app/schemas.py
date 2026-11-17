from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TipoContato = Literal[
    "ramal",
    "telefone_fixo",
    "whatsapp",
    "email",
    "telefone_alternativo",
    "outro",
]
PerfilAdmin = Literal["administrador", "operador"]
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class SchemaAdmin(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ContatoCreate(SchemaAdmin):
    tipo: TipoContato
    valor: str = Field(min_length=1, max_length=100)
    descricao: str | None = Field(default=None, max_length=255)
    principal: bool = False
    ativo: bool = True

    @field_validator("valor")
    @classmethod
    def validar_valor(cls, valor: str, info):
        if not valor.strip():
            raise ValueError("O valor do contato não pode ficar vazio.")
        if info.data.get("tipo") == "email" and not _EMAIL_PATTERN.fullmatch(valor.strip()):
            raise ValueError("Informe um endereço de e-mail válido.")
        return valor.strip()


class ContatoPatch(SchemaAdmin):
    tipo: TipoContato | None = None
    valor: str | None = Field(default=None, min_length=1, max_length=100)
    descricao: str | None = Field(default=None, max_length=255)
    principal: bool | None = None
    ativo: bool | None = None

    @field_validator("valor")
    @classmethod
    def validar_valor(cls, valor: str | None):
        if valor is not None and not valor.strip():
            raise ValueError("O valor do contato não pode ficar vazio.")
        return valor.strip() if valor is not None else valor

    @model_validator(mode="after")
    def validar_email(self):
        if (
            self.tipo == "email"
            and self.valor is not None
            and not _EMAIL_PATTERN.fullmatch(self.valor)
        ):
            raise ValueError("Informe um endereço de e-mail válido.")
        return self


class UnidadeCreate(SchemaAdmin):
    nome: str = Field(min_length=1, max_length=200)
    categoria: str = Field(min_length=1, max_length=100)
    comarca: str | None = Field(default=None, max_length=120)
    descricao: str | None = Field(default=None, max_length=4000)
    contatos: list[ContatoCreate] = Field(default_factory=list, max_length=100)
    competencias: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("nome", "categoria")
    @classmethod
    def validar_obrigatorios(cls, valor: str):
        if not valor.strip():
            raise ValueError("Este campo não pode ficar vazio.")
        return valor.strip()

    @field_validator("comarca", "descricao")
    @classmethod
    def normalizar_opcionais(cls, valor: str | None):
        return valor.strip() or None if valor is not None else None

    @field_validator("competencias")
    @classmethod
    def validar_competencias(cls, valores: list[str]):
        unicas = {}
        for valor in valores:
            nome = valor.strip()
            if not nome or len(nome) > 255:
                raise ValueError("Cada competência deve ter de 1 a 255 caracteres.")
            unicas.setdefault(nome.casefold(), nome)
        return list(unicas.values())


class UnidadePatch(SchemaAdmin):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    comarca: str | None = Field(default=None, max_length=120)
    descricao: str | None = Field(default=None, max_length=4000)
    competencias: list[str] | None = Field(default=None, max_length=100)

    @field_validator("nome", "categoria")
    @classmethod
    def validar_obrigatorios(cls, valor: str | None):
        if valor is not None and not valor.strip():
            raise ValueError("Este campo não pode ficar vazio.")
        return valor.strip() if valor is not None else valor

    @field_validator("comarca", "descricao")
    @classmethod
    def normalizar_opcionais(cls, valor: str | None):
        return valor.strip() or None if valor is not None else None

    @field_validator("competencias")
    @classmethod
    def validar_competencias(cls, valores: list[str] | None):
        if valores is None:
            return valores
        unicas = {}
        for valor in valores:
            nome = valor.strip()
            if not nome or len(nome) > 255:
                raise ValueError("Cada competência deve ter de 1 a 255 caracteres.")
            unicas.setdefault(nome.casefold(), nome)
        return list(unicas.values())


class UnidadeStatus(SchemaAdmin):
    ativo: bool


class UsuarioCreate(SchemaAdmin):
    nome: str = Field(min_length=1, max_length=160)
    usuario: str = Field(min_length=3, max_length=80)
    senha: str = Field(min_length=12, max_length=1024)
    perfil: PerfilAdmin

    @field_validator("nome", "usuario")
    @classmethod
    def validar_texto(cls, valor: str):
        if not valor.strip():
            raise ValueError("Este campo não pode ficar vazio.")
        return valor.strip()


class UsuarioPatch(SchemaAdmin):
    nome: str | None = Field(default=None, min_length=1, max_length=160)
    senha: str | None = Field(default=None, min_length=12, max_length=1024)
    perfil: PerfilAdmin | None = None
    ativo: bool | None = None

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor: str | None):
        if valor is not None and not valor.strip():
            raise ValueError("O nome não pode ficar vazio.")
        return valor.strip() if valor is not None else valor