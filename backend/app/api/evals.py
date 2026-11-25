from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.errors import ApiError, not_found
from app.core.redis import get_json, get_redis, set_json
from app.evals import runner
from app.models.eval import EvalCase

router = APIRouter(prefix="/evals", tags=["evaluación"])


@router.get("/dataset")
async def get_dataset() -> list[dict[str, Any]]:
    return await get_json("eval:dataset", [])


@router.put("/dataset")
async def put_dataset(body: list[EvalCase]) -> dict[str, Any]:
    ids = [c.id for c in body]
    if len(ids) != len(set(ids)):
        raise ApiError(422, "duplicate_ids", "hay ids de casos repetidos")
    await set_json("eval:dataset", [c.model_dump() for c in body])
    return {"ok": True, "casos": len(body)}


@router.post("/dataset/cases", status_code=201)
async def add_case(body: EvalCase) -> dict[str, Any]:
    ds = await get_json("eval:dataset", [])
    if any(c["id"] == body.id for c in ds):
        raise ApiError(409, "duplicate_id", f"ya existe el caso '{body.id}'")
    ds.append(body.model_dump())
    await set_json("eval:dataset", ds)
    return {"ok": True, "casos": len(ds)}


class RunIn(BaseModel):
    ids: list[str] | None = None
    repeticiones: int = Field(1, ge=1, le=5)


@router.post("/run")
async def run_eval(body: RunIn) -> EventSourceResponse:
    async def gen():
        async for ev in runner.run_eval(body.ids, body.repeticiones):
            yield {"event": "eval", "data": json.dumps(ev, ensure_ascii=False, default=str)}

    return EventSourceResponse(gen(), ping=10, headers={"X-Accel-Buffering": "no"})


@router.get("/reports")
async def list_reports() -> list[dict[str, Any]]:
    r = get_redis()
    out = []
    for rid in await r.zrevrange("eval:reports:index", 0, 49):
        rep = await get_json(f"eval:report:{rid}")
        if rep:
            out.append(
                {
                    k: rep[k]
                    for k in ("id", "creado", "version_agentes", "repeticiones", "casos", "metricas", "modo_llm")
                    if k in rep
                }
            )
    return out


@router.get("/reports/{rid}")
async def get_report(rid: str) -> dict[str, Any]:
    rep = await get_json(f"eval:report:{rid}")
    if not rep:
        raise not_found(f"el reporte '{rid}'")
    return rep
