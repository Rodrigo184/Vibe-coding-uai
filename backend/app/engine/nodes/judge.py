from __future__ import annotations

import json

from app.core.config import get_settings
from app.engine.nodes.base import Turn, build_messages, call_llm, historial_txt
from app.llm.schemas import JudgeOut


def tools_resultados(turn: Turn) -> str:
    if not turn.state.tools_llamadas:
        return "(ninguna herramienta llamada)"
    items = []
    for t in turn.state.tools_llamadas[-10:]:
        r = t.get("result") or {}
        items.append(
            {
                "tool": t["name"],
                "args": t["args"],
                "ok": r.get("ok"),
                "data": r.get("data"),
                "error": r.get("error"),
                "escritura": t.get("escritura"),
                "confirmada": t.get("confirmada"),
            }
        )
    return json.dumps(items, ensure_ascii=False, default=str)[:6000]


async def run(turn: Turn) -> dict:
    st = turn.state
    eid = turn.sup.get("evaluador_id", "evaluador")
    agent = turn.agents.get(eid)
    turn.emit("evaluador", "node_start", "Evaluador (LLM-as-judge)", {"agente": eid})
    if not agent:
        v = {
            "veredicto": "publicar",
            "evidencia": "evaluador no configurado",
            "precision": 0,
            "consistencia": 0,
            "cumplimiento_reglas": 0,
            "feedback": None,
        }
        turn.emit("evaluador", "judge", "sin evaluador → publicar", v)
        turn.emit("evaluador", "node_end", "publicar")
        return v
    contexto = f"Cliente: {st.cliente_id}\nPerfil: {json.dumps(st.perfil, ensure_ascii=False)}\nHistorial:\n{historial_txt(st.historial)}\nMensaje actual: {st.mensaje}\nAgente: {st.agente_id}\nAcciones: {json.dumps(st.acciones, ensure_ascii=False)}\nReglas PRE: {json.dumps(st.veredicto_reglas_pre, ensure_ascii=False)}"
    msgs = build_messages(
        turn, agent, contexto=contexto, tools_resultados=tools_resultados(turn), respuesta=st.respuesta or ""
    )
    model = agent.limits.modelo or get_settings().openai_judge_model
    res = await call_llm(
        turn,
        agent,
        "json",
        msgs,
        nodo="evaluador",
        titulo="Calificar respuesta",
        model=model,
        schema=agent.prompt.salida_schema or JudgeOut,
        name="JudgeOut",
    )
    v = res.parsed if isinstance(res.parsed, dict) else {}
    v.setdefault("veredicto", "publicar")
    st.evaluacion = v
    turn.emit(
        "evaluador",
        "judge",
        f"{v.get('veredicto')} · P{v.get('precision')} C{v.get('consistencia')} R{v.get('cumplimiento_reglas')}",
        v,
    )
    turn.emit("evaluador", "node_end", str(v.get("veredicto")))
    return v
