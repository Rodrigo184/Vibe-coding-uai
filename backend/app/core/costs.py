"""Cálculo de costo por tokens y modelo (USD por millón de tokens, desde PRICES_JSON)."""

from __future__ import annotations

from app.core.config import get_settings


def model_price(model: str) -> dict[str, float]:
    prices = get_settings().prices
    if model in prices:
        return prices[model]
    # coincidencia por prefijo (p. ej. "gpt-4o-mini-2024-07-18")
    for name in sorted(prices, key=len, reverse=True):
        if model.startswith(name):
            return prices[name]
    return {"in": 0.0, "out": 0.0}


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    p = model_price(model)
    return round((tokens_in * p.get("in", 0.0) + tokens_out * p.get("out", 0.0)) / 1_000_000, 6)
