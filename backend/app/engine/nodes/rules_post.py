from __future__ import annotations

from app.engine.nodes.base import Turn
from app.rules import base as rules


async def run(turn: Turn) -> str:
    """Devuelve 'pasa' | 'regenerar:<detalle>' | 'bloquear:<detalle>'."""
    st = turn.state
    nombres = turn.sup.get("reglas_post", [])
    turn.emit(
        "reglas_post", "node_start", "Reglas POST (código)", {"reglas": nombres, "intento": st.regeneraciones + 1}
    )
    resultados = []
    for n in nombres:
        r = rules.get(n)
        if not r or r.fase != "post":
            continue
        res = await r.fn(st)
        resultados.append(res)
        turn.emit("reglas_post", "rule", f"{n}: {'ok' if res.ok else res.accion}", res.dict())
    st.reglas_post = [r.dict() for r in resultados]
    bloq = [r for r in resultados if r.accion == "bloquear"]
    regen = [r for r in resultados if r.accion == "regenerar"]
    if bloq:
        turn.emit("reglas_post", "node_end", "bloquear", [r.dict() for r in bloq])
        return "bloquear:" + "; ".join(r.detalle for r in bloq)
    if regen:
        turn.emit("reglas_post", "node_end", "regenerar", [r.dict() for r in regen])
        return "regenerar:" + "; ".join(f"{r.nombre}: {r.detalle}" for r in regen)
    turn.emit("reglas_post", "node_end", "todas pasan")
    return "pasa"
