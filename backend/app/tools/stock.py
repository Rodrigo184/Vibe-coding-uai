from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.redis import get_redis
from app.tools import data
from app.tools.registry import ToolContext, ToolError, tool

SKU = r"^[A-Z]{3}-\d{3}$"


class ConsultarStockArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str | None = Field(None, pattern=SKU, description="SKU, p. ej. PLT-001")
    skus: list[str] | None = Field(None, max_length=30, description="opcional: varios SKUs a la vez (planner)")
    tienda: Literal["LC", "PR", "VI"]

    @model_validator(mode="after")
    def _uno(self):
        if not self.sku and not self.skus:
            raise ValueError("indica 'sku' (o 'skus')")
        return self


@tool(
    "consultar_stock",
    "Stock y precio actual de un SKU en una tienda (LC, PR o VI). Úsala antes de prometer disponibilidad. Evítala para productos sin SKU.",
    ejemplo={"sku": "PLT-001", "tienda": "LC"},
)
async def consultar_stock(args: ConsultarStockArgs, ctx: ToolContext) -> dict:
    async def uno(sku: str) -> dict:
        p = await data.producto(sku)
        if not p:
            raise ToolError(f"SKU {sku} no existe")
        return {
            "sku": sku,
            "nombre": p["nombre"],
            "tienda": args.tienda,
            "stock": await data.stock(args.tienda, sku),
            "precio": p["precio"],
            "unidad": p["unidad"],
        }

    if args.sku and not args.skus:
        return await uno(args.sku)
    resultados = []
    for s in args.skus or []:
        try:
            resultados.append(await uno(s))
        except ToolError as exc:
            resultados.append({"sku": s, "error": str(exc)})
    return {
        "tienda": args.tienda,
        "resultados": resultados,
        "faltantes": [r["sku"] for r in resultados if r.get("stock", 0) == 0],
        "disponibles": [r["sku"] for r in resultados if r.get("stock", 0) > 0],
    }


class VentasResumenArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tienda: Literal["LC", "PR", "VI"]
    dias: int = Field(7, ge=1, le=90)


@tool(
    "ventas_resumen",
    "Top-10 de SKUs por unidades vendidas en una tienda durante los últimos N días (calculado desde pedidos entregados).",
    ejemplo={"tienda": "LC", "dias": 7},
)
async def ventas_resumen(args: VentasResumenArgs, ctx: ToolContext) -> dict:
    r = get_redis()
    desde = (dt.date.today() - dt.timedelta(days=args.dias)).isoformat()
    unidades: dict[str, int] = {}
    pedidos = 0
    async for key in r.scan_iter(match="negocio:pedidos:*"):
        for pid in await r.lrange(key, 0, -1):
            p = await data.pedido(pid)
            if not p or p["estado"] != "entregado" or p["tienda"] != args.tienda or p["fecha_entrega"] < desde:
                continue
            pedidos += 1
            for it in p["items"]:
                unidades[it["sku"]] = unidades.get(it["sku"], 0) + int(it["cantidad"])
    top = []
    for sku, u in sorted(unidades.items(), key=lambda x: (-x[1], x[0]))[:10]:
        p = await data.producto(sku)
        top.append({"sku": sku, "nombre": p["nombre"] if p else sku, "unidades": u})
    return {"tienda": args.tienda, "dias": args.dias, "pedidos_considerados": pedidos, "top": top}
