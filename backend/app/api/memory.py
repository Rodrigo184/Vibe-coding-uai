from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.errors import ApiError
from app.engine import pipeline
from app.engine.nodes.base import LimitExceeded
from app.engine.nodes.memory_write import resumir_episodio
from app.memory import store
from app.tools import data

router = APIRouter(prefix="/memory", tags=["memoria"])


@router.get("")
async def list_clientes() -> list[dict[str, Any]]:
    ids = sorted(set(await data.clientes_ids()) | set(await store.clientes_con_memoria()))
    out = []
    for cid in ids:
        c = await data.cliente(cid)
        out.append(
            {
                "cliente_id": cid,
                "nombre": c["nombre"] if c else cid,
                "tienda": c["tienda"] if c else None,
                "canal": c["canal"] if c else None,
                "en_negocio": bool(c),
            }
        )
    return out


@router.get("/{cliente_id}")
async def get_memory(cliente_id: str) -> dict[str, Any]:
    return {
        "cliente_id": cliente_id,
        "cliente": await data.cliente(cliente_id),
        "perfil": await store.perfil_detalle(cliente_id),
        "episodios": await store.episodios(cliente_id),
        "sesiones": await store.sesiones(cliente_id),
    }


class PerfilIn(BaseModel):
    hechos: dict[str, str]


@router.put("/{cliente_id}/perfil")
async def put_perfil(cliente_id: str, body: PerfilIn) -> dict[str, Any]:
    problemas = await store.reemplazar_perfil(cliente_id, body.hechos)
    return {"ok": not problemas, "descartados": problemas, "perfil": await store.perfil_detalle(cliente_id)}


@router.delete("/{cliente_id}")
async def delete_memory(cliente_id: str) -> dict[str, Any]:
    n = await store.borrar_todo(cliente_id)
    return {"ok": True, "claves_borradas": n}


@router.post("/{cliente_id}/cerrar_sesion/{sesion_id}")
async def cerrar_sesion(cliente_id: str, sesion_id: str) -> dict[str, Any]:
    historial = await store.historial(sesion_id)
    if not historial:
        raise ApiError(404, "empty_session", "la sesión no tiene turnos")
    turn = await pipeline.build_turn(cliente_id=cliente_id, sesion_id=sesion_id, mensaje="(cierre de sesión)")
    turn.state.historial = historial
    ext = turn.agents.get(turn.sup.get("extractor_id", "extractor"))
    if not ext:
        raise ApiError(409, "no_extractor", "el supervisor no tiene extractor configurado")
    try:
        resumen = await resumir_episodio(turn, ext)
    except LimitExceeded as exc:
        raise ApiError(429, "limit", exc.motivo) from exc
    if resumen:
        await store.push_episodio(cliente_id, resumen)
    await store.cerrar_sesion(cliente_id, sesion_id)
    return {"ok": True, "episodio": resumen, "costo_usd": turn.state.costo_usd}
