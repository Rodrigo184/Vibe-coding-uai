from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.errors import ApiError
from app.core.config import get_settings
from app.core.redis import get_redis
from app.engine import pipeline

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    cliente_id: str = Field(..., min_length=1, max_length=40)
    sesion_id: str = Field(..., min_length=1, max_length=60)
    mensaje: str = Field(..., min_length=1, max_length=2000)
    supervisor_id: str = "supervisor"
    canal: str = "app"
    forzar_agente: str | None = None
    hora_override: str | None = Field(
        None, pattern=r"^\d{2}:\d{2}$", description="solo para pruebas de la regla horario_alcohol"
    )


class ConfirmIn(BaseModel):
    run_id: str
    confirmar: bool


async def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "?"
    key = f"ratelimit:chat:{ip}:{int(time.time() // 60)}"
    r = get_redis()
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, 70)
    if n > get_settings().chat_rate_limit_per_min:
        raise ApiError(429, "rate_limited", f"máximo {get_settings().chat_rate_limit_per_min} turnos por minuto")


def _stream(queue: asyncio.Queue, task: asyncio.Task) -> EventSourceResponse:
    async def gen():
        while True:
            ev = await queue.get()
            if ev is None:
                break
            yield {"event": "trace", "data": ev.model_dump_json()}
        await task

    return EventSourceResponse(gen(), ping=10, headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@router.post("")
async def chat(body: ChatIn, request: Request) -> Any:
    await _rate_limit(request)
    queue: asyncio.Queue = asyncio.Queue()
    try:
        turn = await pipeline.build_turn(
            cliente_id=body.cliente_id,
            sesion_id=body.sesion_id,
            mensaje=body.mensaje,
            supervisor_id=body.supervisor_id,
            canal=body.canal,
            forzar_agente=body.forzar_agente,
            queue=queue,
            hora_override=body.hora_override,
        )
    except pipeline.SupervisorNotFound as exc:
        raise ApiError(404, "supervisor_not_found", str(exc)) from exc
    task = asyncio.create_task(pipeline.run_turn(turn))
    return _stream(queue, task)


@router.post("/confirm")
async def confirm(body: ConfirmIn) -> Any:
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(pipeline.confirm(body.run_id, body.confirmar, queue))
    return _stream(queue, task)
