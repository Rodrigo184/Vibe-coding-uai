"""Carga de agentes desde Redis con caché en memoria invalidada por `agents:version`."""

from __future__ import annotations

from typing import Any

from app.core.redis import get_json, get_redis, set_json
from app.models.agent import AgentDef

_cache: dict[str, AgentDef] = {}
_cache_version: int | None = None


async def version() -> int:
    v = await get_redis().get("agents:version")
    return int(v) if v else 0


async def bump_version() -> int:
    return int(await get_redis().incr("agents:version"))


async def _refresh() -> None:
    global _cache, _cache_version
    v = await version()
    if _cache_version == v and _cache:
        return
    ids = await get_redis().smembers("agents:index")
    nuevo: dict[str, AgentDef] = {}
    for aid in ids:
        raw = await get_json(f"agent:{aid}")
        if raw:
            try:
                nuevo[aid] = AgentDef.model_validate(raw)
            except Exception:
                continue
    _cache, _cache_version = nuevo, v


def invalidate() -> None:
    global _cache_version
    _cache_version = None


async def all_agents() -> dict[str, AgentDef]:
    await _refresh()
    return dict(_cache)


async def get_agent(aid: str) -> AgentDef | None:
    await _refresh()
    return _cache.get(aid)


async def save_agent(agent: AgentDef) -> int:
    await set_json(f"agent:{agent.id}", agent.model_dump(mode="json"))
    await get_redis().sadd("agents:index", agent.id)
    v = await bump_version()
    invalidate()
    return v


async def delete_agent(aid: str) -> int:
    r = get_redis()
    await r.delete(f"agent:{aid}")
    await r.srem("agents:index", aid)
    v = await bump_version()
    invalidate()
    return v


async def seed_copy(aid: str) -> dict[str, Any] | None:
    return await get_json(f"agents:seed:{aid}")
