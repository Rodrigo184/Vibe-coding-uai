from __future__ import annotations

import json

from app.engine.nodes.base import Turn
from app.tools import registry as tools


async def run(turn: Turn, motivo: str) -> None:
    """Deriva a una persona: crea ticket (sin confirmación) y responde con el texto fijo del supervisor."""
    st = turn.state
    turn.emit("humano", "node_start", "Derivar a humano", {"motivo": motivo})
    if st.bloqueo_total:
        # bloqueo por datos sensibles: respuesta fija, sin ticket con el contenido del mensaje
        turn.emit("humano", "output", "Respuesta fija por bloqueo total", st.respuesta)
        st.estado = "humano"
        turn.emit("humano", "node_end", "bloqueo total")
        return
    if turn.evaluating:
        st.respuesta = "La evaluación detectó que la consulta requiere atención humana."
        st.respuesta_raw = st.respuesta
        st.estado = "humano"
        turn.emit("humano", "output", st.respuesta)
        turn.emit("humano", "node_end", "Derivación evaluada")
        return
    resumen = f"[{st.agente_id or 'router'}] {motivo}. Cliente {st.cliente_id}, sesión {st.sesion_id}. Mensaje: {st.mensaje[:300]}"
    if st.respuesta:
        resumen += f" | Respuesta retenida: {st.respuesta[:300]}"
    prioridad = (
        "alta" if any(w in st.mensaje.lower() for w in ("salud", "intoxic", "alerg", "amenaz", "legal")) else "media"
    )
    ctx = tools.ToolContext(cliente_id=st.cliente_id, sesion_id=st.sesion_id, run_id=st.run_id)
    turn.emit(
        "tools",
        "tool_call",
        "crear_ticket (nodo humano, sin confirmación)",
        {"tool": "crear_ticket", "args": {"resumen": resumen[:200], "prioridad": prioridad}},
    )
    res = await tools.run_tool("crear_ticket", {"resumen": resumen[:1000], "prioridad": prioridad}, ctx)
    turn.emit("tools", "tool_result", f"crear_ticket → {'ok' if res.ok else 'error'}", res.model_dump())
    st.tools_llamadas.append(
        {
            "name": "crear_ticket",
            "args": {"prioridad": prioridad},
            "result": res.model_dump(),
            "escritura": True,
            "confirmada": False,
            "agente": "humano",
        }
    )
    st.ticket_id = (res.data or {}).get("ticket_id") if res.ok else None
    st.acciones.append(
        {"tool": "crear_ticket", "args": {"prioridad": prioridad}, "estado": "ejecutada", "ticket_id": st.ticket_id}
    )
    plantilla = turn.sup.get("mensaje_humano") or "Un ejecutivo revisará tu caso. Ticket {ticket_id}."
    try:
        st.respuesta = plantilla.format(ticket_id=st.ticket_id or "pendiente")
    except (KeyError, IndexError):
        st.respuesta = plantilla
    st.respuesta_raw = st.respuesta
    st.estado = "humano"
    turn.emit(
        "humano",
        "output",
        st.respuesta[:140],
        json.loads(json.dumps({"respuesta": st.respuesta, "ticket_id": st.ticket_id})),
    )
    turn.emit("humano", "node_end", st.ticket_id or "sin ticket")
