from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.redis import detect_modules, ping
from app.engine import registry
from app.rules import base as rules
from app.seed import seed as seeder

router = APIRouter(tags=["sistema"])


@router.get("/health")
async def health() -> dict[str, Any]:
    s = get_settings()
    redis_ok = await ping()
    mods = await detect_modules() if redis_ok else {"json": False, "search": False}
    return {
        "ok": redis_ok,
        "redis": redis_ok,
        "openai": s.openai_configured,
        "modo_llm": "openai" if s.openai_configured else ("demo" if s.use_mock_llm else "sin_llm"),
        "modulos": mods,
        "agents_version": await registry.version() if redis_ok else None,
        "app_env": s.app_env,
    }


class SeedIn(BaseModel):
    que: list[str] = ["negocio", "agentes", "dataset"]


@router.post("/seed")
async def reseed(body: SeedIn) -> dict[str, Any]:
    out = await seeder.seed(body.que)
    registry.invalidate()
    return {"ok": True, **out}


@router.get("/config")
async def config() -> dict[str, Any]:
    s = get_settings()
    modelos = []
    for m in [
        s.openai_model,
        s.openai_judge_model,
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-5-mini",
        "gpt-5",
    ]:
        if m not in modelos:
            modelos.append(m)
    return {
        "modelo": s.openai_model,
        "modelo_juez": s.openai_judge_model,
        "modelo_embeddings": s.openai_embed_model,
        "modelos": modelos,
        "limites": {
            "max_turn_cost_usd": s.max_turn_cost_usd,
            "max_turn_seconds": s.max_turn_seconds,
            "max_llm_calls_per_turn": s.max_llm_calls_per_turn,
            "chat_rate_limit_per_min": s.chat_rate_limit_per_min,
        },
        "precios": s.prices,
        "openai_configurado": s.openai_configured,
        "modo_llm": "openai" if s.openai_configured else ("demo" if s.use_mock_llm else "sin_llm"),
        "langfuse": s.langfuse_enabled,
    }


@router.get("/rules")
async def list_rules() -> list[dict[str, str]]:
    return rules.catalogo()
