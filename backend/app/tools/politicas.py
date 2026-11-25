"""buscar_politica: similitud de embeddings (text-embedding-3-small, sembrados en `negocio:politica:{id}`)
con respaldo léxico cuando no hay embeddings (modo demo o sin clave)."""

from __future__ import annotations

import json
import math

from pydantic import BaseModel, ConfigDict, Field

from app.core.redis import get_redis
from app.llm import client as llm
from app.tools import data
from app.tools.registry import ToolContext, tool


class BuscarPoliticaArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pregunta: str = Field(..., min_length=3, max_length=400)


def _cos(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=False))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0


SINONIMOS = {
    "devol": ["devol"],
    "cambi": ["cambi"],
    "borre": ["olvid", "borra", "datos"],
    "datos": ["datos", "olvid"],
    "plata": ["reemb"],
    "reemb": ["reemb"],
    "garan": ["garan"],
    "alcoh": ["alcoh"],
    "vino": ["alcoh"],
    "cerve": ["alcoh"],
}


@tool(
    "buscar_politica",
    "Top-3 políticas del supermercado (título + extracto) más relevantes para la pregunta. Úsala para citar la política antes de responder.",
    ejemplo={"pregunta": "¿hasta cuándo puedo devolver un producto?"},
)
async def buscar_politica(args: BuscarPoliticaArgs, ctx: ToolContext) -> list[dict]:
    r = get_redis()
    pols = []
    async for key in r.scan_iter(match="negocio:politica:*"):
        h = await r.hgetall(key)
        if h:
            pols.append({"id": key.split(":", 2)[2], **h})
    qvec = None
    if any(p.get("embedding") for p in pols):
        try:
            emb = await llm.embed([args.pregunta])
            qvec = emb[0] if emb else None
        except Exception:
            qvec = None
    q_tokens = set(data.tokens(args.pregunta))
    for t in list(q_tokens):
        q_tokens.update(SINONIMOS.get(t, []))
    scored = []
    for p in pols:
        if qvec is not None and p.get("embedding"):
            score = _cos(qvec, json.loads(p["embedding"]))
            modo = "embeddings"
        else:
            pt = set(data.tokens(p["titulo"] + " " + p["texto"]))
            tt = set(data.tokens(p["titulo"]))
            score = len(q_tokens & pt) + 2 * len(q_tokens & tt)
            modo = "lexico"
        scored.append((score, p, modo))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [
        {"id": p["id"], "titulo": p["titulo"], "extracto": p["texto"][:260], "score": round(float(s), 3), "modo": modo}
        for s, p, modo in scored[:3]
    ]
