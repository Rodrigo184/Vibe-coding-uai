from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

TraceType = Literal[
    "node_start",
    "thought",
    "llm_call",
    "tool_call",
    "tool_result",
    "rule",
    "decision",
    "judge",
    "memory",
    "confirm_required",
    "output",
    "error",
    "node_end",
    "final",
]


class TraceEvent(BaseModel):
    seq: int
    ts: float
    run_id: str
    nodo: str
    tipo: TraceType
    titulo: str
    contenido: str | dict[str, Any] | list[Any]
    tokens_in: int = 0
    tokens_out: int = 0
    costo_usd: float = 0
    ms: int = 0
    modelo: str | None = None


RunEstado = Literal["ok", "pendiente_confirmacion", "humano", "error", "limite"]


class RunSummary(BaseModel):
    run_id: str
    sesion_id: str
    cliente_id: str
    mensaje: str
    respuesta: str | None = None
    agente: str | None = None
    veredicto: str | None = None
    acciones: list[dict[str, Any]] = []
    costo_usd: float = 0
    latencia_ms: int = 0
    llamadas_llm: int = 0
    estado: RunEstado = "ok"
    creado: datetime
    version_agentes: int = 0
    supervisor_id: str = "supervisor"
