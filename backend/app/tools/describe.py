"""Descripción legible de una acción de escritura para la tarjeta de confirmación."""

from __future__ import annotations

from typing import Any

from app.core.redis import get_redis
from app.tools import data


def clp(n: Any) -> str:
    try:
        return "$" + f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


async def describir(name: str, args: dict[str, Any], cliente_id: str) -> str:
    try:
        if name == "solicitar_reembolso":
            h = await get_redis().hgetall(f"negocio:cobro:{args.get('cobro_id')}")
            if h:
                return f"Solicitar el reembolso del cobro {args.get('cobro_id')} ({clp(h.get('monto'))}) del pedido {h.get('pedido_id')} — llega al medio de pago original en 3 a 5 días hábiles"
            return f"Solicitar el reembolso del cobro {args.get('cobro_id')}"
        if name == "agregar_item":
            p = await data.producto(str(args.get("sku")))
            cant = int(args.get("cantidad", 1))
            pid = args.get("pedido_id")
            if str(pid).lower() == "actual":
                pid = "a tu próximo pedido"
            else:
                pid = f"al pedido {pid}"
            if p:
                unidad = "kg de " if p["unidad"] == "kg" else "× "
                return f"Agregar {cant} {unidad}{p['nombre']} ({clp(p['precio'] * cant)}) {pid}"
            return f"Agregar {cant} × {args.get('sku')} {pid}"
        if name == "crear_pedido_borrador":
            items = args.get("items") or []
            total = 0
            for it in items if isinstance(items, list) else []:
                p = await data.producto(str(it.get("sku")))
                if p:
                    total += p["precio"] * int(it.get("cantidad", 1))
            tienda = data.TIENDA_NOMBRE.get(str(args.get("tienda")), args.get("tienda"))
            n = len(items) if isinstance(items, list) else 0
            return f"Crear un pedido borrador para el {args.get('fecha_entrega')} en {tienda} con {n} productos (total {clp(total)})"
    except Exception:
        pass
    return f"Ejecutar {name} con {args}"
