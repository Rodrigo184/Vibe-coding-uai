from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.redis import get_json, get_redis, set_json
from app.tools import data
from app.tools.registry import ToolContext, ToolError, tool

SKU = r"^[A-Z]{3}-\d{3}$"
ABIERTOS = ("borrador", "confirmado", "preparando")


class SinArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


@tool(
    "pedido_actual",
    "Próximo pedido no entregado del cliente (borrador, confirmado o en preparación), o null si no hay.",
    ejemplo={},
)
async def pedido_actual(args: SinArgs, ctx: ToolContext) -> dict | None:
    abiertos = [p for p in await data.pedidos_cliente(ctx.cliente_id) if p["estado"] in ABIERTOS]
    if not abiertos:
        return None
    abiertos.sort(key=lambda p: (p["fecha_entrega"], p["pedido_id"]))
    return data.pedido_publico(abiertos[0])


class HistorialArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int = Field(8, ge=1, le=20, description="cantidad de pedidos")
    excluir: list[str] = Field(
        default_factory=list, description="opcional: palabras o categorías a excluir del promedio (p. ej. 'pan')"
    )


@tool(
    "historial_pedidos",
    "Últimos n pedidos del cliente con ítems y totales, más 'promedio_items' (cantidad promedio por SKU en pedidos entregados, redondeada hacia arriba) y la lista 'skus'.",
    ejemplo={"n": 8},
)
async def historial_pedidos(args: HistorialArgs, ctx: ToolContext) -> dict:
    todos = await data.pedidos_cliente(ctx.cliente_id)
    todos.sort(key=lambda p: p["fecha_entrega"])
    ultimos = todos[-args.n :]
    entregados = [p for p in ultimos if p["estado"] == "entregado"]
    excl = [data.norm(x) for x in args.excluir]
    suma: dict[str, int] = {}
    apariciones: dict[str, int] = {}
    nombres: dict[str, str] = {}
    for p in entregados:
        for it in p["items"]:
            prod = await data.producto(it["sku"])
            nombre = prod["nombre"] if prod else it["sku"]
            texto = data.norm(f"{nombre} {prod['categoria'] if prod else ''} {it['sku']}")
            if any(e and e in texto for e in excl):
                continue
            nombres[it["sku"]] = nombre
            suma[it["sku"]] = suma.get(it["sku"], 0) + int(it["cantidad"])
            apariciones[it["sku"]] = apariciones.get(it["sku"], 0) + 1
    minimo = max(1, math.ceil(len(entregados) / 2))
    promedio = [
        {"sku": s, "nombre": nombres[s], "cantidad": math.ceil(suma[s] / max(1, len(entregados)))}
        for s in sorted(suma)
        if apariciones[s] >= minimo
    ]
    pedidos = []
    for p in ultimos:
        items = []
        for it in p["items"]:
            prod = await data.producto(it["sku"])
            items.append({**it, "nombre": prod["nombre"] if prod else it["sku"]})
        pedidos.append({**data.pedido_publico(p), "items": items})
    return {
        "pedidos": pedidos,
        "promedio_items": promedio,
        "skus": [x["sku"] for x in promedio],
        "excluidos": args.excluir,
    }


class EstadoPedidoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pedido_id: str = Field(..., min_length=2, max_length=20)


@tool(
    "estado_pedido",
    "Estado, tienda y fecha de entrega de un pedido del cliente (solo si le pertenece).",
    ejemplo={"pedido_id": "P-9120"},
)
async def estado_pedido(args: EstadoPedidoArgs, ctx: ToolContext) -> dict:
    p = await data.pedido_del_cliente(args.pedido_id.strip(), ctx.cliente_id)
    return {
        "pedido_id": p["pedido_id"],
        "estado": p["estado"],
        "tienda": p["tienda"],
        "fecha_entrega": p["fecha_entrega"],
        "total": p["total"],
        "items": len(p["items"]),
    }


class ItemArg(BaseModel):
    model_config = ConfigDict(
        extra="ignore"
    )  # tolera campos informativos (p. ej. 'nombre') que llegan por referencia $paso
    sku: str = Field(..., pattern=SKU)
    cantidad: int = Field(..., ge=1, le=500)


class CrearBorradorArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ItemArg] = Field(..., min_length=1, max_length=40)
    fecha_entrega: str = Field(..., description="fecha ISO AAAA-MM-DD")
    tienda: Literal["LC", "PR", "VI"]

    @field_validator("fecha_entrega")
    @classmethod
    def _fecha(cls, v: str) -> str:
        try:
            d = dt.date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("fecha_entrega debe ser AAAA-MM-DD") from exc
        if d < dt.date.today():
            raise ValueError("fecha_entrega no puede estar en el pasado")
        return v


@tool(
    "crear_pedido_borrador",
    "Crea un pedido en estado 'borrador' con los ítems indicados; el total se calcula con los precios del catálogo. Informa ítems sin stock suficiente.",
    escritura=True,
    ejemplo={"items": [{"sku": "PLT-001", "cantidad": 2}], "fecha_entrega": "2026-11-20", "tienda": "LC"},
)
async def crear_pedido_borrador(args: CrearBorradorArgs, ctx: ToolContext) -> dict:
    items_norm = sorted((i.sku, i.cantidad) for i in args.items)
    h = hashlib.sha1(json.dumps([ctx.cliente_id, args.fecha_entrega, args.tienda, items_norm]).encode()).hexdigest()[
        :16
    ]
    r = get_redis()
    dedup_key = f"negocio:dedup:borrador:{h}"
    previo = await r.get(dedup_key)
    if previo:
        p = await data.pedido(previo)
        if p:
            return {**data.pedido_publico(p), "deduplicado": True}
    items, advertencias = [], []
    for sku, cant in items_norm:
        prod = await data.producto(sku)
        if not prod:
            raise ToolError(f"SKU {sku} no existe")
        st = await data.stock(args.tienda, sku)
        if st < cant:
            advertencias.append({"sku": sku, "pedido": cant, "stock": st})
        items.append({"sku": sku, "nombre": prod["nombre"], "cantidad": cant, "precio": prod["precio"]})
    pid = f"B-{random.randint(1000, 9999)}"
    while await r.exists(f"negocio:pedido:{pid}"):
        pid = f"B-{random.randint(1000, 9999)}"
    pedido = {
        "pedido_id": pid,
        "cliente_id": ctx.cliente_id,
        "fecha_entrega": args.fecha_entrega,
        "tienda": args.tienda,
        "items": items,
        "estado": "borrador",
        "total": sum(i["precio"] * i["cantidad"] for i in items),
        "creado_por_run": ctx.run_id,
    }
    await data.guardar_pedido(pedido)
    await r.rpush(f"negocio:pedidos:{ctx.cliente_id}", pid)
    await r.set(dedup_key, pid, ex=600)
    return {**data.pedido_publico(pedido), "advertencias_stock": advertencias}


class AgregarItemArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pedido_id: str = Field(..., description="id del pedido, o 'actual' para el próximo pedido abierto del cliente")
    sku: str = Field(..., pattern=SKU)
    cantidad: int = Field(..., ge=1, le=500)
    idempotency_key: str = Field(
        ..., min_length=4, max_length=80, description="clave única de la operación (evita duplicar)"
    )


@tool(
    "agregar_item",
    "Agrega un SKU a un pedido abierto del cliente (verifica stock de la tienda del pedido). Idempotente por idempotency_key.",
    escritura=True,
    ejemplo={"pedido_id": "P-9120", "sku": "PLT-001", "cantidad": 2, "idempotency_key": "P-9120-PLT-001-2"},
)
async def agregar_item(args: AgregarItemArgs, ctx: ToolContext) -> dict:
    idem_key = f"negocio:idem:{ctx.cliente_id}:{args.idempotency_key}"
    previo = await get_json(idem_key)
    if previo:
        return {**previo, "idempotente": True}
    if args.pedido_id.lower() == "actual":
        actual = await pedido_actual(SinArgs(), ctx)
        if not actual:
            raise ToolError("el cliente no tiene un pedido abierto; crea un borrador primero")
        pid = actual["pedido_id"]
    else:
        pid = args.pedido_id
    p = await data.pedido_del_cliente(pid, ctx.cliente_id)
    if p["estado"] not in ABIERTOS:
        raise ToolError(f"el pedido {pid} está {p['estado']} y ya no admite cambios")
    prod = await data.producto(args.sku)
    if not prod:
        raise ToolError(f"SKU {args.sku} no existe")
    ya = sum(int(i["cantidad"]) for i in p["items"] if i["sku"] == args.sku)
    st = await data.stock(p["tienda"], args.sku)
    if ya + args.cantidad > st:
        raise ToolError(f"stock insuficiente: hay {st} {prod['unidad']} de {prod['nombre']} en {p['tienda']}")
    for it in p["items"]:
        if it["sku"] == args.sku:
            it["cantidad"] = int(it["cantidad"]) + args.cantidad
            break
    else:
        p["items"].append({"sku": args.sku, "cantidad": args.cantidad, "precio": prod["precio"]})
    p["total"] = sum(int(i["precio"]) * int(i["cantidad"]) for i in p["items"])
    await data.guardar_pedido(p)
    out = {
        **data.pedido_publico(p),
        "agregado": {
            "sku": args.sku,
            "nombre": prod["nombre"],
            "cantidad": args.cantidad,
            "precio": prod["precio"],
            "subtotal": prod["precio"] * args.cantidad,
        },
    }
    await set_json(idem_key, out, ex=86400)
    return out
