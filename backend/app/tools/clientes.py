from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.tools import data
from app.tools.registry import ToolContext, ToolError, tool


class SinArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


@tool(
    "verificar_edad",
    "Indica si el cliente actual tiene la edad verificada (requisito para comprar alcohol).",
    ejemplo={},
)
async def verificar_edad(args: SinArgs, ctx: ToolContext) -> dict:
    c = await data.cliente(ctx.cliente_id)
    if not c:
        raise ToolError("cliente no encontrado")
    return {"edad_verificada": c["edad_verificada"]}


@tool("cupo_credito", "Cupo disponible en la línea de crédito del cliente actual (CLP).", ejemplo={})
async def cupo_credito(args: SinArgs, ctx: ToolContext) -> dict:
    c = await data.cliente(ctx.cliente_id)
    if not c:
        raise ToolError("cliente no encontrado")
    return {"cupo_disponible": c["cupo_credito"]}
