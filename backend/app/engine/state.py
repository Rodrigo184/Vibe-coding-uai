from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class TurnState(BaseModel):
    """Estado único y tipado que comparten todos los nodos del turno (sección 7.1)."""

    run_id: str
    sesion_id: str
    cliente_id: str
    mensaje: str
    canal: str = "app"
    fecha: str
    hora: str
    supervisor_id: str = "supervisor"
    forzar_agente: str | None = None
    version_agentes: int = 0

    perfil: dict[str, Any] = {}
    episodios: list[dict[str, Any]] = []
    historial: list[dict[str, Any]] = []
    tienda: str = "LC"
    cliente_nombre: str = ""

    veredicto_reglas_pre: dict[str, Any] = {}
    reglas_pre: list[dict[str, Any]] = []
    router: dict[str, Any] | None = None
    agente_id: str | None = None
    modo: str = "especialista"  # especialista | planner | humano
    reenrutado: bool = False

    mensajes_llm: list[dict[str, Any]] = []
    tools_llamadas: list[dict[str, Any]] = []
    precios_vistos: dict[str, int] = {}
    precios_api: list[dict[str, Any]] = []
    firmas_tools: list[str] = []

    respuesta: str | None = None
    respuesta_raw: str | None = None
    meta: dict[str, Any] = {}
    accion_pendiente: dict[str, Any] | None = None
    acciones: list[dict[str, Any]] = []

    plan: dict[str, Any] | None = None
    plan_resultados: dict[str, Any] = {}
    replanificaciones: int = 0

    reglas_post: list[dict[str, Any]] = []
    evaluacion: dict[str, Any] | None = None
    regeneraciones: int = 0
    respuesta_esperada: str | None = None

    hechos_nuevos: list[dict[str, Any]] = []
    ticket_id: str | None = None
    bloqueo_total: bool = False
    hora_override: str | None = None

    costo_usd: float = 0
    llamadas_llm: int = 0
    inicio: float = Field(default_factory=time.time)
    estado: str = "ok"
