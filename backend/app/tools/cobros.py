from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.redis import get_redis
from app.tools import data
from app.tools.registry import ToolContext, ToolError, tool


class ConsultarCobrosArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pedido_id: str = Field(..., min_length=2, max_length=20)


@tool(
    "consultar_cobros",
    "Cobros asociados a un pedido del cliente: id, monto, fecha y estado (aprobado, duplicado, reembolsado).",
    ejemplo={"pedido_id": "8812"},
)
async def consultar_cobros(args: ConsultarCobrosArgs, ctx: ToolContext) -> list[dict]:
    await data.pedido_del_cliente(args.pedido_id.strip(), ctx.cliente_id)
    r = get_redis()
    out = []
    for cid in await r.lrange(f"negocio:cobros:{args.pedido_id.strip()}", 0, -1):
        h = await r.hgetall(f"negocio:cobro:{cid}")
        if h:
            out.append({"cobro_id": cid, "monto": int(h["monto"]), "fecha": h["fecha"], "estado": h["estado"]})
    return out


class SolicitarReembolsoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cobro_id: str = Field(..., min_length=1, max_length=20)
    motivo: str = Field(..., min_length=3, max_length=200)


@tool(
    "solicitar_reembolso",
    "Solicita el reembolso de un cobro del cliente al medio de pago original (plazo 3-5 días hábiles). Acción de escritura.",
    escritura=True,
    ejemplo={"cobro_id": "c2", "motivo": "cobro duplicado"},
)
async def solicitar_reembolso(args: SolicitarReembolsoArgs, ctx: ToolContext) -> dict:
    r = get_redis()
    h = await r.hgetall(f"negocio:cobro:{args.cobro_id}")
    if not h:
        raise ToolError(f"cobro {args.cobro_id} no encontrado")
    await data.pedido_del_cliente(h["pedido_id"], ctx.cliente_id)  # aislamiento por cliente
    if h["estado"] == "reembolsado":
        raise ToolError(f"el cobro {args.cobro_id} ya fue reembolsado")
    await r.hset(f"negocio:cobro:{args.cobro_id}", mapping={"estado": "reembolsado", "motivo_reembolso": args.motivo})
    return {
        "cobro_id": args.cobro_id,
        "pedido_id": h["pedido_id"],
        "monto": int(h["monto"]),
        "estado": "reembolsado",
        "plazo": "3-5 días hábiles",
    }
