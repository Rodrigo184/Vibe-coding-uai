"""JSON schemas de salida que consume código (RouterOut, PlanOut, JudgeOut, FactsOut, VerifyOut, EpisodeOut)."""

from app.seed.build_agentes import FACTS_SCHEMA as FactsOut  # noqa: N812
from app.seed.build_agentes import JUDGE_SCHEMA as JudgeOut  # noqa: N812
from app.seed.build_agentes import PLAN_SCHEMA as PlanOut  # noqa: N812
from app.seed.build_agentes import ROUTER_SCHEMA as RouterOut  # noqa: N812

VerifyOut = {
    "type": "object",
    "properties": {
        "pasos_ok": {"type": "array", "items": {"type": "integer"}},
        "fallidos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "motivo": {"type": "string"}},
                "required": ["id", "motivo"],
                "additionalProperties": False,
            },
        },
        "coherente": {"type": "boolean"},
        "resumen": {"type": "string"},
    },
    "required": ["pasos_ok", "fallidos", "coherente", "resumen"],
    "additionalProperties": False,
}

EpisodeOut = {
    "type": "object",
    "properties": {"resumen": {"type": "string"}},
    "required": ["resumen"],
    "additionalProperties": False,
}

__all__ = ["RouterOut", "PlanOut", "JudgeOut", "FactsOut", "VerifyOut", "EpisodeOut"]
