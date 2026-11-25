from __future__ import annotations

import json
import random
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.redis import get_redis
from app.tools.registry import ToolContext, tool


class CrearTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resumen: str = Field(..., min_length=3, max_length=1000)
    prioridad: Literal["baja", "media", "alta"] = "media"


@tool(
    "crear_ticket",
    "Crea un ticket para que un ejecutivo humano atienda el caso. La usa el nodo humano (sin confirmación).",
    escritura=True,
    ejemplo={"resumen": "Cliente reporta problema de salud con un producto", "prioridad": "alta"},
)
async def crear_ticket(args: CrearTicketArgs, ctx: ToolContext) -> dict:
    tid = f"T-{random.randint(10000, 99999)}"
    ticket = {
        "ticket_id": tid,
        "cliente_id": ctx.cliente_id,
        "sesion_id": ctx.sesion_id,
        "run_id": ctx.run_id,
        "resumen": args.resumen,
        "prioridad": args.prioridad,
        "ts": time.time(),
    }
    await get_redis().lpush("negocio:tickets", json.dumps(ticket, ensure_ascii=False))
    return {"ticket_id": tid, "prioridad": args.prioridad}
