from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentType(StrEnum):
    router = "router"
    especialista = "especialista"
    planner = "planner"
    memoria = "memoria"
    hibrido = "hibrido"
    evaluador = "evaluador"
    supervisor = "supervisor"


class Variable(BaseModel):
    nombre: str
    descripcion: str = ""
    ejemplo: str = ""
    origen: Literal["estado", "usuario", "constante"] = "estado"


class PromptTemplate(BaseModel):
    system: str
    user: str
    variables: list[Variable] = []
    salida_esperada: str = ""
    salida_schema: dict[str, Any] | None = None


class Limits(BaseModel):
    max_iters: int = Field(5, ge=1, le=20)
    max_tokens_out: int = Field(800, ge=16, le=8000)
    timeout_s: int = Field(12, ge=1, le=120)
    temperature: float = Field(0.0, ge=0, le=2)
    modelo: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


class AgentDef(BaseModel):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_\-]{1,40}$")
    tipo: AgentType
    nombre: str
    tagline: str = ""
    color: str = "teal"
    descripcion: str = ""
    dominio: str | None = None
    tools: list[str] = []
    acciones_escritura: list[str] = []
    prompt: PromptTemplate
    limits: Limits = Limits()
    constantes: dict[str, Any] = {}
    activo: bool = True
    usar_cuando: list[str] = []
    evitar_cuando: list[str] = []
    riesgos: list[dict[str, Any]] = []
    metricas: list[str] = []
    frameworks: list[str] = []
    flow: dict[str, Any] = {"nodes": [], "edges": []}
    version: int = 1
    actualizado: datetime = Field(default_factory=_now)


class AgentSummary(BaseModel):
    id: str
    tipo: AgentType
    nombre: str
    tagline: str
    color: str
    activo: bool
    version: int
    tools: list[str]
    actualizado: datetime
