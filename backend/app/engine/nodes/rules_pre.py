from __future__ import annotations

from app.engine.nodes.base import Turn
from app.rules import base as rules
from app.rules import pre


async def run(turn: Turn) -> bool:
    """Ejecuta las reglas PRE del supervisor. Devuelve True si hay bloqueo total (→ humano con respuesta fija)."""
    st = turn.state
    nombres = turn.sup.get("reglas_pre", [])
    turn.emit("reglas_pre", "node_start", "Reglas PRE (código)", {"reglas": nombres})
    resultados = []
    for n in nombres:
        r = rules.get(n)
        if not r or r.fase != "pre":
            turn.emit("reglas_pre", "rule", f"{n}: regla inexistente (se omite)", {"nombre": n, "ok": True})
            continue
        res = await r.fn(st)
        resultados.append(res)
        turn.emit("reglas_pre", "rule", f"{n}: {'ok' if res.ok else res.accion}", res.dict())
    st.reglas_pre = [r.dict() for r in resultados]
    st.veredicto_reglas_pre = pre.veredicto(resultados)
    total = next((r for r in resultados if r.accion == "bloqueo_total"), None)
    turn.emit("reglas_pre", "node_end", "bloqueo total" if total else "veredicto listo", st.veredicto_reglas_pre)
    if total:
        st.bloqueo_total = True
        st.respuesta = total.alternativa
        return True
    return False
