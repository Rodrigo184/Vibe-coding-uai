from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "")
os.environ["OPENAI_API_KEY"] = ""  # tests unitarios: siempre LLM simulado (o mockeado por test)
os.environ.setdefault("DEMO_MODE_WITHOUT_KEY", "true")


@pytest.fixture
async def redis():
    import fakeredis

    from app.core import redis as core_redis
    from app.core.config import get_settings
    from app.engine import registry

    get_settings.cache_clear()
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    core_redis.set_redis(client)
    registry.invalidate()
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture
async def seeded(redis):
    from app.seed import seed

    await seed.reset()
    return redis


async def run_chat(cliente_id: str, mensaje: str, sesion_id: str = "s-test", **kw):
    from app.engine import pipeline

    turn = await pipeline.build_turn(cliente_id=cliente_id, sesion_id=sesion_id, mensaje=mensaje, **kw)
    st = await pipeline.run_turn(turn)
    return st, turn.tracer.events
