from __future__ import annotations

from app.engine.nodes.base import Turn, build_messages, call_llm
from app.llm.schemas import RouterOut


async def run(turn: Turn) -> str:
    """Devuelve el id del agente elegido o 'humano'."""
    st = turn.state
    especialistas = [a for a in turn.sup.get("especialistas", []) if a in turn.agents and turn.agents[a].activo]

    if st.forzar_agente:
        turn.emit("router", "node_start", "Router (fijado)", {"forzado": st.forzar_agente})
        st.router = {
            "agente": st.forzar_agente,
            "confianza": 1.0,
            "motivo": "Agente fijado para prueba",
            "intenciones_secundarias": [],
            "alternativo": None,
        }
        turn.emit("router", "decision", f"→ {st.forzar_agente} (fijado)", st.router)
        turn.emit("router", "node_end", st.forzar_agente)
        return st.forzar_agente

    rid = turn.sup.get("router_id", "router")
    agent = turn.agents.get(rid)
    turn.emit("router", "node_start", "Router", {"agente": rid, "especialistas": especialistas})
    if not agent:
        turn.emit("router", "error", f"router '{rid}' no existe; derivo a humano")
        turn.emit("router", "node_end", "humano")
        return "humano"
    msgs = build_messages(turn, agent)
    schema = agent.prompt.salida_schema or RouterOut
    res = await call_llm(
        turn, agent, "json", msgs, nodo="router", titulo="Clasificar intención", schema=schema, name="RouterOut"
    )
    out = res.parsed if isinstance(res.parsed, dict) else {}
    st.router = out
    elegido = str(out.get("agente", "humano"))
    conf = float(out.get("confianza") or 0)
    umbral = float(turn.sup.get("umbral_confianza", 0.6))
    motivo_ajuste = None
    if elegido != "humano" and elegido not in especialistas:
        alt = out.get("alternativo")
        if alt in especialistas:
            motivo_ajuste = f"'{elegido}' no está en el catálogo; uso el alternativo '{alt}'"
            elegido = alt
        else:
            motivo_ajuste = f"'{elegido}' no está en el catálogo → humano"
            elegido = "humano"
    if elegido != "humano" and conf < umbral:
        motivo_ajuste = f"confianza {conf:.2f} < umbral {umbral} → humano"
        elegido = "humano"
    titulo = f"→ {elegido} ({conf:.2f})" + (f" · {motivo_ajuste}" if motivo_ajuste else "")
    turn.emit("router", "decision", titulo, {**out, "elegido": elegido, "ajuste": motivo_ajuste})
    turn.emit("router", "node_end", elegido)
    return elegido
