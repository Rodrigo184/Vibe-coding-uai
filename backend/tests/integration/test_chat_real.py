"""Integración real: Redis real (REDIS_URL) + OpenAI (OPENAI_API_KEY). `make test-integration`."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
async def real():
    key = os.environ.get("OPENAI_API_KEY_REAL") or os.environ.get("OPENAI_API_KEY_INTEGRATION")
    if not key:
        pytest.skip("define OPENAI_API_KEY_REAL para correr la integración")
    os.environ["OPENAI_API_KEY"] = key
    from app.core import redis as core_redis
    from app.core.config import get_settings
    from app.engine import registry
    from app.llm import client as llm
    from app.seed import seed

    get_settings.cache_clear()
    llm.reset_client()
    core_redis._client = None
    registry.invalidate()
    await seed.seed()
    yield


async def test_cobro_duplicado_real(real):
    from app.engine import pipeline

    turn = await pipeline.build_turn(cliente_id="c42", sesion_id="it-1", mensaje="me cobraron dos veces el pedido 8812")
    st = await pipeline.run_turn(turn)
    assert st.agente_id == "financiero"
    assert any(t["name"] == "consultar_cobros" for t in st.tools_llamadas)
