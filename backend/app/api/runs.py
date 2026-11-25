from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.api.errors import not_found
from app.core.redis import get_json, get_redis

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
async def list_runs(
    limit: int = Query(50, ge=1, le=500),
    cliente_id: str | None = None,
    estado: str | None = None,
    agente: str | None = None,
) -> list[dict[str, Any]]:
    r = get_redis()
    ids = await r.zrevrange("runs:index", 0, 999)
    out = []
    for rid in ids:
        run = await get_json(f"run:{rid}")
        if not run:
            await r.zrem("runs:index", rid)
            continue
        s = run["summary"]
        if cliente_id and s["cliente_id"] != cliente_id:
            continue
        if estado and s["estado"] != estado:
            continue
        if agente and s.get("agente") != agente:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


@router.get("/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    run = await get_json(f"run:{run_id}")
    if not run:
        raise not_found(f"el run '{run_id}'")
    run["pendiente"] = await get_json(f"run:{run_id}:pendiente") is not None
    return run


@router.get("/{run_id}/export")
async def export_run(run_id: str) -> JSONResponse:
    run = await get_json(f"run:{run_id}")
    if not run:
        raise not_found(f"el run '{run_id}'")
    return JSONResponse(run, headers={"Content-Disposition": f'attachment; filename="{run_id}.json"'})
