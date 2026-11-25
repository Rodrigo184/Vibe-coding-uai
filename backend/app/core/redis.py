"""Cliente Redis asíncrono + helpers JSON.

Se guarda JSON como string (SET/GET) para funcionar con o sin el módulo RedisJSON;
`detect_modules()` informa qué módulos existen (para /api/health).
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

_client: Any = None
_modules: dict[str, bool] = {"json": False, "search": False}


def get_redis() -> Any:
    global _client
    if _client is None:
        _client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


def set_redis(client: Any) -> None:
    """Inyecta un cliente (fakeredis en tests)."""
    global _client
    _client = client


async def detect_modules() -> dict[str, bool]:
    r = get_redis()
    try:
        mods = await r.execute_command("MODULE", "LIST")
        names: set[str] = set()
        for m in mods or []:
            if isinstance(m, dict):
                names.add(str(m.get("name", "")).lower())
            elif isinstance(m, list | tuple):
                for i, v in enumerate(m):
                    if str(v) == "name" and i + 1 < len(m):
                        names.add(str(m[i + 1]).lower())
        _modules["json"] = "rejson" in names or "rejson" in {n.replace("-", "") for n in names}
        _modules["search"] = "search" in names or "ft" in names
    except Exception:
        _modules["json"] = False
        _modules["search"] = False
    return dict(_modules)


def modules() -> dict[str, bool]:
    return dict(_modules)


async def get_json(key: str, default: Any = None) -> Any:
    raw = await get_redis().get(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


async def set_json(key: str, value: Any, ex: int | None = None) -> None:
    await get_redis().set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ex)


async def ping() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False
