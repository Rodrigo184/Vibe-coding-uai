"""Configuración desde variables de entorno (.env). Ningún secreto vive en el código."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PRICES = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o": {"in": 2.50, "out": 10.00},
    "text-embedding-3-small": {"in": 0.02, "out": 0.0},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_judge_model: str = "gpt-4o"
    openai_embed_model: str = "text-embedding-3-small"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "dev"
    max_turn_cost_usd: float = 0.05
    max_turn_seconds: int = 25
    max_llm_calls_per_turn: int = 8
    prices_json: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    cors_origins: str = "*"
    chat_rate_limit_per_min: int = 20
    # Modo demo: si no hay OPENAI_API_KEY se usa un LLM simulado determinístico (llm/mock.py).
    demo_mode_without_key: bool = True

    @property
    def openai_configured(self) -> bool:
        key = self.openai_api_key.strip()
        return bool(key) and not key.startswith("sk-xxx")

    @property
    def use_mock_llm(self) -> bool:
        return not self.openai_configured and self.demo_mode_without_key

    @property
    def prices(self) -> dict[str, dict[str, float]]:
        prices = dict(DEFAULT_PRICES)
        if self.prices_json.strip():
            try:
                prices.update(json.loads(self.prices_json))
            except json.JSONDecodeError:
                pass
        return prices

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key and self.langfuse_host)


@lru_cache
def get_settings() -> Settings:
    return Settings()
