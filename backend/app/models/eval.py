from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class EvalCase(BaseModel):
    id: str
    etiqueta: Literal["normal", "borde", "adversarial"] = "normal"
    cliente_id: str = "c42"
    sesion_nueva: bool = True
    mensaje: str
    agente_esperado: str | list[str] | None = None
    tools_esperadas: list[str] = []
    respuesta_esperada: str = ""
    reglas_a_verificar: list[str] = []
    debe_pedir_confirmacion: bool = False


class EvalResult(BaseModel):
    case_id: str
    repeticion: int = 0
    etiqueta: str = "normal"
    mensaje: str = ""
    agente_esperado: str | list[str] | None = None
    agente: str | None = None
    tools_esperadas: list[str] = []
    tools: list[str] = []
    respuesta: str | None = None
    veredicto: str | None = None
    juez: dict[str, Any] | None = None
    reglas_post: list[dict[str, Any]] = []
    pidio_confirmacion: bool = False
    debe_pedir_confirmacion: bool = False
    derivado_humano: bool = False
    estado: str = "ok"
    costo_usd: float = 0
    latencia_ms: int = 0
    llamadas_llm: int = 0
    run_id: str | None = None
    ok_enrutamiento: bool = False
    ok_tools: bool | None = None
    ok_reglas: bool = True
    ok_confirmacion: bool = True


class EvalReport(BaseModel):
    id: str
    creado: str
    version_agentes: int
    repeticiones: int
    casos: int
    metricas: dict[str, Any]
    por_regla: dict[str, float] = {}
    resultados: list[EvalResult] = []
    modo_llm: str = "openai"
