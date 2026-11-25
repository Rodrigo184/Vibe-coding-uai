"""Supervisor del turno (sección 7.5).

Orden fijo: memory_read → rules_pre → router → (especialista | planner | humano) → rules_post →
judge → memory_write → final. Límites globales antes de cada llamada LLM. Cualquier excepción →
evento `error` + estado `error` + respuesta genérica; nunca un 500 a medio stream.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import time
import traceback
import uuid
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.redis import get_json, get_redis, set_json
from app.engine import registry
from app.engine.nodes import human, judge, memory_read, memory_write, planner, router, rules_post, rules_pre, specialist
from app.engine.nodes.base import LimitExceeded, Turn
from app.engine.state import TurnState
from app.engine.tracer import Tracer
from app.models.agent import AgentDef, AgentType
from app.models.run import RunSummary

TZ = ZoneInfo("America/Santiago")
RUN_TTL = 7 * 24 * 3600
PENDIENTE_TTL = 15 * 60

MSG_LIMITE = "Alcancé el límite de procesamiento de este turno ({motivo}). Ya registré tu consulta: ¿puedes reformularla en una frase o prefieres que te derive con una persona?"
MSG_ERROR = "Tuvimos un problema técnico al procesar tu mensaje. Ya quedó registrado; por favor intenta de nuevo en unos segundos o pide hablar con una persona."
MSG_CANCELADA = "Listo, cancelé la acción: no se ejecutó nada ({descripcion}). ¿Te ayudo con algo más?"


class SupervisorNotFound(Exception):
    pass


async def build_turn(
    *,
    cliente_id: str,
    sesion_id: str,
    mensaje: str,
    supervisor_id: str = "supervisor",
    canal: str = "app",
    forzar_agente: str | None = None,
    respuesta_esperada: str | None = None,
    queue: asyncio.Queue | None = None,
    hora_override: str | None = None,
    evaluating: bool = False,
) -> Turn:
    if supervisor_id.startswith("solo:"):
        forzar_agente = supervisor_id.split(":", 1)[1]
        supervisor_id = "supervisor"
    agents = await registry.all_agents()
    sup = agents.get(supervisor_id)
    if not sup or sup.tipo != AgentType.supervisor:
        raise SupervisorNotFound(f"supervisor '{supervisor_id}' no existe")
    now = dt.datetime.now(TZ)
    st = TurnState(
        run_id="r-" + uuid.uuid4().hex[:12],
        sesion_id=sesion_id,
        cliente_id=cliente_id,
        mensaje=mensaje.strip(),
        canal=canal,
        fecha=now.date().isoformat(),
        hora=now.strftime("%H:%M"),
        supervisor_id=supervisor_id,
        forzar_agente=forzar_agente,
        version_agentes=await registry.version(),
        respuesta_esperada=respuesta_esperada,
        hora_override=hora_override,
    )
    s = get_settings()
    return Turn(
        state=st,
        tracer=Tracer(st.run_id, queue),
        supervisor=sup,
        agents=agents,
        max_calls=s.max_llm_calls_per_turn,
        max_cost=s.max_turn_cost_usd,
        max_seconds=s.max_turn_seconds,
        evaluating=evaluating,
    )


# ============================================================================ turno nuevo
async def run_turn(turn: Turn) -> TurnState:
    st = turn.state
    pausado = False
    try:
        await memory_read.run(turn)
        if await rules_pre.run(turn):
            await human.run(turn, "bloqueo total en reglas PRE")
        else:
            elegido = await router.run(turn)
            pausado = await _ejecutar_agente(turn, elegido)
    except LimitExceeded as exc:
        _limite(turn, exc.motivo)
    except Exception as exc:  # nunca un 500 a medio stream
        _error(turn, exc)
    try:
        if pausado:
            if not turn.evaluating:
                await memory_write.write_history(turn)
                await _guardar_pendiente(turn)
        elif st.estado in ("ok", "humano") or st.respuesta:
            await memory_write.run(turn)
    except Exception as exc:
        turn.emit("extractor", "error", f"error escribiendo memoria: {type(exc).__name__}", str(exc)[:300])
    await _finalizar(turn)
    return st


async def _ejecutar_agente(turn: Turn, elegido: str) -> bool:
    """Ejecuta especialista/planner/humano y el post-proceso. Devuelve True si quedó en pausa."""
    st = turn.state
    if elegido == "humano":
        motivo = (st.router or {}).get("motivo") or "derivación del router"
        await human.run(turn, f"router: {motivo}")
        return False
    agent = turn.agents.get(elegido)
    if not agent or not agent.activo:
        await human.run(turn, f"agente '{elegido}' no disponible")
        return False
    st.agente_id = elegido
    st.modo = "planner" if agent.tipo == AgentType.planner else "especialista"
    turn.emit(
        elegido,
        "node_start",
        f"{agent.nombre} ({agent.tipo.value})",
        {"agente": elegido, "tipo": agent.tipo.value, "tools": agent.tools, "version": agent.version},
    )
    out = await (planner.run(turn, agent) if st.modo == "planner" else specialist.run(turn, agent))
    turn.emit(elegido, "node_end", out)
    return await _despues_del_agente(turn, agent, out)


async def _despues_del_agente(turn: Turn, agent: AgentDef, out: str) -> bool:
    st = turn.state
    if out == "pendiente":
        st.estado = "pendiente_confirmacion"
        if st.modo != "planner":
            desc = (st.accion_pendiente or {}).get("descripcion", "")
            st.respuesta = f"Revisé tu solicitud y puedo hacerlo ahora. Para continuar necesito tu confirmación: {desc}. ¿Lo confirmo?"
            st.respuesta_raw = st.respuesta
        return True
    if out.startswith("reenrutar:"):
        sugerido = out.split(":", 1)[1]
        especialistas = turn.sup.get("especialistas", [])
        if not st.reenrutado and sugerido in especialistas and sugerido != agent.id:
            st.reenrutado = True
            st.mensajes_llm, st.firmas_tools = [], []
            turn.emit("router", "decision", f"reenrutado una vez → {sugerido}", {"desde": agent.id, "hacia": sugerido})
            return await _ejecutar_agente(turn, sugerido)
        await human.run(turn, f"{agent.id} declaró fuera de dominio")
        return False
    if out == "cancelada":
        desc = ""
        for a in st.acciones:
            if a.get("estado") == "cancelada":
                desc = f"{a['tool']}"
        st.respuesta = MSG_CANCELADA.format(descripcion=desc or "acción")
        st.respuesta_raw = st.respuesta
        turn.emit(agent.id, "output", "Acción cancelada por el usuario", st.respuesta)
        return False
    if out in ("limite", "error"):
        return False
    return await _post(turn, agent)


async def _post(turn: Turn, agent: AgentDef) -> bool:
    """Reglas POST + evaluador con regeneración (máximo `max_regeneraciones`)."""
    st = turn.state
    max_regen = int(turn.sup.get("max_regeneraciones", 1))
    puede_regenerar = st.modo == "especialista"
    while True:
        r = await rules_post.run(turn)
        if r.startswith("bloquear:"):
            await human.run(turn, "reglas POST: " + r.split(":", 1)[1])
            return False
        if r.startswith("regenerar:"):
            detalle = r.split(":", 1)[1]
            if not puede_regenerar or st.regeneraciones >= max_regen:
                await human.run(turn, "reglas POST: " + detalle)
                return False
            out = await _regenerar(turn, agent, "reglas POST", detalle)
            if out == "ok":
                continue
            return await _despues_del_agente(turn, agent, out)
        v = await judge.run(turn)
        veredicto = v.get("veredicto")
        if veredicto == "publicar":
            return False
        if veredicto == "regenerar" and puede_regenerar and st.regeneraciones < max_regen:
            out = await _regenerar(turn, agent, "evaluador", v.get("feedback") or v.get("evidencia") or "")
            if out == "ok":
                continue
            return await _despues_del_agente(turn, agent, out)
        await human.run(turn, f"evaluador: {veredicto} — {v.get('evidencia', '')}")
        return False


async def _regenerar(turn: Turn, agent: AgentDef, fuente: str, detalle: str) -> str:
    st = turn.state
    st.regeneraciones += 1
    turn.emit(
        agent.id,
        "decision",
        f"Regenerar ({fuente}) {st.regeneraciones}/{turn.sup.get('max_regeneraciones', 1)}",
        detalle,
    )
    st.mensajes_llm.append(
        {
            "role": "user",
            "content": f"[CORRECCIÓN DEL SISTEMA · {fuente}] Tu respuesta anterior no pasó la verificación: {detalle}. Reescribe la respuesta al cliente corrigiendo eso y mantén el formato.",
        }
    )
    turn.emit(agent.id, "node_start", f"{agent.nombre} (regeneración)", {"agente": agent.id})
    out = await specialist.run(turn, agent)
    turn.emit(agent.id, "node_end", out)
    return out


def _limite(turn: Turn, motivo: str) -> None:
    st = turn.state
    st.estado = "limite"
    st.accion_pendiente = None
    st.respuesta = MSG_LIMITE.format(motivo=motivo)
    st.respuesta_raw = st.respuesta
    turn.emit(
        "final",
        "error",
        f"límite alcanzado: {motivo}",
        {"motivo": motivo, "llamadas_llm": st.llamadas_llm, "costo_usd": st.costo_usd},
    )


def _error(turn: Turn, exc: Exception) -> None:
    st = turn.state
    st.estado = "error"
    st.accion_pendiente = None
    st.respuesta = MSG_ERROR
    st.respuesta_raw = st.respuesta
    tb = traceback.format_exception(exc)[-3:]
    turn.emit(
        "final",
        "error",
        f"{type(exc).__name__}: {str(exc)[:200]}",
        {"error": str(exc)[:1000], "traceback": "".join(tb)[-1500:]},
    )


async def _guardar_pendiente(turn: Turn) -> None:
    st = turn.state
    await set_json(
        f"run:{st.run_id}:pendiente",
        {
            "state": st.model_dump(mode="json"),
            "supervisor_id": st.supervisor_id,
            "seq": turn.tracer.seq,
            "t_previo": time.time() - turn.t0,
        },
        ex=PENDIENTE_TTL,
    )


async def _finalizar(turn: Turn, previo: dict[str, Any] | None = None, t_previo: float = 0.0) -> None:
    st = turn.state
    latencia = int((time.time() - turn.t0 + t_previo) * 1000)
    veredicto = (st.evaluacion or {}).get("veredicto") if st.evaluacion else None
    if st.estado == "humano":
        veredicto = veredicto or "humano"
    final = {
        "respuesta": st.respuesta,
        "acciones": st.acciones,
        "agente": st.agente_id or ("humano" if st.estado == "humano" else None),
        "veredicto": veredicto,
        "evaluacion": st.evaluacion,
        "costo_usd": round(st.costo_usd, 6),
        "latencia_ms": latencia,
        "llamadas_llm": st.llamadas_llm,
        "run_id": st.run_id,
        "estado": st.estado,
        "accion_pendiente": st.accion_pendiente,
        "ticket_id": st.ticket_id,
        "hechos_nuevos": st.hechos_nuevos,
        "version_agentes": st.version_agentes,
        "modo_llm": "demo" if get_settings().use_mock_llm else "openai",
    }
    turn.emit(
        "final",
        "final",
        f"{st.estado} · {final['agente'] or '—'} · ${st.costo_usd:.4f} · {latencia} ms",
        final,
        ms=latencia,
        costo_usd=st.costo_usd,
    )
    summary = RunSummary(
        run_id=st.run_id,
        sesion_id=st.sesion_id,
        cliente_id=st.cliente_id,
        mensaje=st.mensaje,
        respuesta=st.respuesta,
        agente=final["agente"],
        veredicto=veredicto,
        acciones=st.acciones,
        costo_usd=round(st.costo_usd, 6),
        latencia_ms=latencia,
        llamadas_llm=st.llamadas_llm,
        estado=st.estado if st.estado in ("ok", "pendiente_confirmacion", "humano", "error", "limite") else "ok",  # type: ignore[arg-type]
        creado=dt.datetime.now(dt.UTC) if not previo else dt.datetime.fromisoformat(previo["summary"]["creado"]),
        version_agentes=st.version_agentes,
        supervisor_id=st.supervisor_id,
    )
    eventos = (previo or {}).get("events", []) + [e.model_dump(mode="json") for e in turn.tracer.events]
    detalle = {
        "router": st.router,
        "reglas_pre": st.reglas_pre,
        "reglas_post": st.reglas_post,
        "evaluacion": st.evaluacion,
        "tools_llamadas": st.tools_llamadas,
        "plan": st.plan,
        "hechos_nuevos": st.hechos_nuevos,
        "regeneraciones": st.regeneraciones,
    }
    try:
        await set_json(
            f"run:{st.run_id}",
            {"summary": summary.model_dump(mode="json"), "events": eventos, "detalle": detalle},
            ex=RUN_TTL,
        )
        await get_redis().zadd("runs:index", {st.run_id: summary.creado.timestamp()})
    except Exception:
        pass
    turn.tracer.close()


# ============================================================================ confirmación
async def confirm(run_id: str, confirmar: bool, queue: asyncio.Queue | None = None) -> TurnState | None:
    raw = await get_redis().getdel(f"run:{run_id}:pendiente")
    pend = json.loads(raw) if raw else None
    previo = await get_json(f"run:{run_id}")
    tracer = Tracer(run_id, queue, seq=(pend or {}).get("seq", len((previo or {}).get("events", []))))
    if not pend:
        tracer.emit(
            "final",
            "error",
            "No hay una acción pendiente para este run (expiró a los 15 minutos o ya fue procesada).",
            {"run_id": run_id},
        )
        tracer.emit(
            "final",
            "final",
            "error",
            {
                "run_id": run_id,
                "estado": "error",
                "respuesta": "Esa acción ya no está disponible para confirmar (expiró o ya fue procesada). ¿Quieres que lo intentemos de nuevo?",
                "acciones": [],
                "costo_usd": 0,
                "latencia_ms": 0,
            },
        )
        tracer.close()
        return None
    st = TurnState.model_validate(pend["state"])
    agents = await registry.all_agents()
    sup = agents.get(pend.get("supervisor_id", "supervisor")) or agents.get("supervisor")
    s = get_settings()
    turn = Turn(
        state=st,
        tracer=tracer,
        supervisor=sup,
        agents=agents,
        max_calls=s.max_llm_calls_per_turn,
        max_cost=s.max_turn_cost_usd,
        max_seconds=s.max_turn_seconds,
    )  # type: ignore[arg-type]
    st.llamadas_llm = 0  # el presupuesto de llamadas se renueva para la continuación (el costo se acumula en el run)
    costo_previo = st.costo_usd
    st.estado = "ok"
    pausado = False
    pendiente = st.accion_pendiente or {}
    agent = agents.get(pendiente.get("agente") or st.agente_id or "")
    turn.emit(
        "tools",
        "decision",
        f"Usuario {'confirmó' if confirmar else 'canceló'}: {pendiente.get('descripcion', '')}",
        {"confirmar": confirmar, **pendiente},
    )
    try:
        if not agent:
            raise RuntimeError("el agente de la acción pendiente ya no existe")
        turn.emit(agent.id, "node_start", f"{agent.nombre} (continuación)", {"agente": agent.id})
        if pendiente.get("modo") == "planner":
            out = await planner.resume(turn, agent, confirmar)
        else:
            out = await specialist.resume(turn, agent, confirmar)
        turn.emit(agent.id, "node_end", out)
        pausado = await _despues_del_agente(turn, agent, out)
    except LimitExceeded as exc:
        _limite(turn, exc.motivo)
    except Exception as exc:
        _error(turn, exc)
    st.costo_usd = max(st.costo_usd, costo_previo)
    try:
        if pausado:
            await memory_write.write_history(turn, user=False)
            await _guardar_pendiente(turn)
        elif st.respuesta:
            await memory_write.run(turn, user_ya_escrito=True)
    except Exception as exc:
        turn.emit("extractor", "error", f"error escribiendo memoria: {type(exc).__name__}", str(exc)[:300])
    await _finalizar(turn, previo=previo, t_previo=float(pend.get("t_previo", 0)))
    return st
