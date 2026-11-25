from __future__ import annotations

from app.engine.nodes.base import LimitExceeded, Turn, build_messages, call_llm, split_sections
from app.llm.schemas import EpisodeOut, FactsOut
from app.memory import store
from app.models.agent import AgentDef


async def write_history(turn: Turn, *, user: bool = True, assistant: bool = True) -> None:
    st = turn.state
    if user:
        await store.push_turno(st.sesion_id, st.cliente_id, "user", st.mensaje)
    if assistant and st.respuesta:
        await store.push_turno(st.sesion_id, st.cliente_id, "assistant", st.respuesta)


async def run(turn: Turn, *, user_ya_escrito: bool = False) -> None:
    st = turn.state
    turn.emit("extractor", "node_start", "Escribir memoria")
    if st.bloqueo_total:
        turn.emit("extractor", "memory", "bloqueo total: nada se escribe en memoria", {"escrito": []})
        turn.emit("extractor", "node_end", "sin escritura")
        return
    escrito = []
    if not turn.evaluating:
        await write_history(turn, user=not user_ya_escrito)
        escrito.append("historial")
    ext_id = turn.sup.get("extractor_id", "extractor")
    agent = turn.agents.get(ext_id)
    if agent and st.respuesta and st.estado in ("ok", "humano"):
        try:
            hechos = await extraer_hechos(turn, agent)
        except LimitExceeded as exc:
            turn.emit("extractor", "memory", f"extractor omitido: {exc.motivo}", {})
            hechos = []
        for h in hechos:
            if turn.evaluating:
                h["resultado"] = "evaluación"
                continue
            resultado = await store.set_hecho(
                st.cliente_id, h.get("clave", ""), h.get("valor", ""), h.get("fuente", ""), bool(h.get("reemplaza"))
            )
            h["resultado"] = resultado
            if resultado == "guardado":
                escrito.append(f"perfil.{h.get('clave')}")
        st.hechos_nuevos = hechos
    titulo = "Propuesta de memoria para evaluación" if turn.evaluating else f"Guardado: {', '.join(escrito)}"
    turn.emit("extractor", "memory", titulo, {"escrito": escrito, "hechos": st.hechos_nuevos})
    turn.emit("extractor", "node_end", titulo)


async def extraer_hechos(turn: Turn, agent: AgentDef) -> list[dict]:
    secs = split_sections(agent.prompt.system)
    sys_b = secs.get("B", agent.prompt.system)
    msgs = build_messages(turn, agent, system_tpl=sys_b)
    res = await call_llm(
        turn,
        agent,
        "json",
        msgs,
        nodo="extractor",
        titulo="Extraer hechos",
        schema=agent.prompt.salida_schema or FactsOut,
        name="FactsOut",
    )
    hechos = (res.parsed or {}).get("hechos", []) if isinstance(res.parsed, dict) else []
    return [h for h in hechos if isinstance(h, dict)]


async def resumir_episodio(turn: Turn, agent: AgentDef) -> str:
    secs = split_sections(agent.prompt.system)
    sys_c = secs.get(
        "C", 'Resume la sesión en máximo 3 líneas. Solo JSON: {"resumen": "<texto>"}\n[SESIÓN]\n{{historial}}'
    )
    msgs = build_messages(turn, agent, system_tpl=sys_c, user_tpl="Resume la sesión. Responde solo JSON.")
    res = await call_llm(
        turn, agent, "json", msgs, nodo="extractor", titulo="Resumir episodio", schema=EpisodeOut, name="EpisodeOut"
    )
    return str((res.parsed or {}).get("resumen", "")) if isinstance(res.parsed, dict) else ""
