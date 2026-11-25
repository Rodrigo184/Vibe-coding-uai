"""Acceso a los datos del negocio en Redis (claves `negocio:*`, sección 5.3)."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from app.core.redis import get_json, get_redis, set_json
from app.tools.registry import ToolError

TIENDAS = ("LC", "PR", "VI")
TIENDA_NOMBRE = {"LC": "Las Condes", "PR": "Providencia", "VI": "Vitacura"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def tokens(s: str) -> list[str]:
    return [w[:5] for w in re.findall(r"[a-z0-9]{3,}", norm(s))]


async def producto(sku: str) -> dict[str, Any] | None:
    h = await get_redis().hgetall(f"negocio:producto:{sku}")
    if not h:
        return None
    return {
        "sku": sku,
        "nombre": h.get("nombre"),
        "categoria": h.get("categoria"),
        "unidad": h.get("unidad"),
        "precio": int(h.get("precio", 0)),
        "contiene_alcohol": h.get("contiene_alcohol") == "true",
        "alergenos": json.loads(h.get("alergenos") or "[]"),
        "temporada": h.get("temporada"),
    }


async def productos() -> list[dict[str, Any]]:
    skus = sorted(await get_redis().smembers("negocio:productos:index"))
    out = []
    for s in skus:
        p = await producto(s)
        if p:
            out.append(p)
    return out


async def stock(tienda: str, sku: str) -> int:
    v = await get_redis().get(f"negocio:stock:{tienda}:{sku}")
    return int(v) if v is not None else 0


async def cliente(cid: str) -> dict[str, Any] | None:
    h = await get_redis().hgetall(f"negocio:cliente:{cid}")
    if not h:
        return None
    return {
        "id": cid,
        "nombre": h.get("nombre"),
        "tienda": h.get("tienda"),
        "canal": h.get("canal"),
        "edad_verificada": h.get("edad_verificada") == "true",
        "cupo_credito": int(h.get("cupo_credito", 0)),
    }


async def clientes_ids() -> list[str]:
    ids = []
    async for k in get_redis().scan_iter(match="negocio:cliente:*"):
        ids.append(k.split(":", 2)[2])
    return sorted(ids)


async def pedido(pid: str) -> dict[str, Any] | None:
    return await get_json(f"negocio:pedido:{pid}")


async def pedido_del_cliente(pid: str, cliente_id: str) -> dict[str, Any]:
    p = await pedido(pid)
    if not p or p.get("cliente_id") != cliente_id:
        raise ToolError(f"pedido {pid} no encontrado")
    return p


async def guardar_pedido(p: dict[str, Any]) -> None:
    await set_json(f"negocio:pedido:{p['pedido_id']}", p)


async def pedidos_cliente(cliente_id: str) -> list[dict[str, Any]]:
    ids = await get_redis().lrange(f"negocio:pedidos:{cliente_id}", 0, -1)
    out = []
    for pid in ids:
        p = await pedido(pid)
        if p:
            out.append(p)
    return out


def pedido_publico(p: dict[str, Any]) -> dict[str, Any]:
    """Vista del pedido para el modelo (sin cliente_id)."""
    return {k: v for k, v in p.items() if k not in ("cliente_id", "dedup")}
