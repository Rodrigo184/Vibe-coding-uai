"""Tracer: emite TraceEvent a una cola asyncio (SSE), los acumula y los guarda con el run en Redis.
Langfuse opcional: si LANGFUSE_* está configurado y el paquete `langfuse` está instalado, se envía
cada evento como span; si no, se ignora en silencio."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from app.core.config import get_settings
from app.models.run import TraceEvent

MAX_TXT = 2000


def truncar(obj: Any, n: int = MAX_TXT) -> Any:
    if isinstance(obj, str):
        return obj if len(obj) <= n else obj[:n] + f"… [+{len(obj) - n} caracteres]"
    if isinstance(obj, dict):
        return {k: truncar(v, n) for k, v in obj.items()}
    if isinstance(obj, list):
        return [truncar(x, n) for x in obj]
    return obj


class Tracer:
    def __init__(self, run_id: str, queue: asyncio.Queue | None = None, seq: int = 0):
        self.run_id = run_id
        self.queue = queue
        self.seq = seq
        self.events: list[TraceEvent] = []
        self._langfuse = None
        s = get_settings()
        if s.langfuse_enabled:
            try:  # pragma: no cover - opcional
                from langfuse import Langfuse  # type: ignore

                self._langfuse = Langfuse(
                    public_key=s.langfuse_public_key, secret_key=s.langfuse_secret_key, host=s.langfuse_host
                )
            except Exception:
                self._langfuse = None

    def emit(self, nodo: str, tipo: Any, titulo: str, contenido: Any = "", **metrics: Any) -> TraceEvent:
        self.seq += 1
        if not isinstance(contenido, str | dict | list):
            contenido = json.loads(json.dumps(contenido, default=str))
        ev = TraceEvent(
            seq=self.seq,
            ts=time.time(),
            run_id=self.run_id,
            nodo=nodo,
            tipo=tipo,
            titulo=titulo,
            contenido=truncar(contenido, 6000),
            **metrics,
        )  # type: ignore[arg-type]
        self.events.append(ev)
        if self.queue is not None:
            self.queue.put_nowait(ev)
        if self._langfuse is not None:  # pragma: no cover
            try:
                self._langfuse.event(trace_id=self.run_id, name=f"{nodo}.{tipo}", input=titulo, output=ev.contenido)
            except Exception:
                pass
        return ev

    def close(self) -> None:
        if self.queue is not None:
            self.queue.put_nowait(None)
