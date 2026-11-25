"""Especialista / híbrido: loop ReAct con tool calling nativo (sección 7.4).

Las tools de lectura se ejecutan; las de escritura pausan el turno (confirm_required) y la acción
queda pendiente hasta POST /api/chat/confirm. Los resultados de tools vuelven al modelo como
mensajes `tool` (datos), nunca concatenados al system.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.engine.nodes.base import Turn, build_messages, call_llm, separar_meta
from app.models.agent import AgentDef, AgentType
from app.tools import data
from app.tools import registry as tools
from app.tools.describe import describir

FUERA_RE = re.compile(r"\{\s*\"fuera_de_dominio\"\s*:\s*true.*?\}", re.S)


def _registrar_precios(turn: Turn, result: Any) -> None:
    def walk(o: Any) -> None:
        if isinstance(o, dict):
            if "sku" in o and isinstance(o.get("precio"), int | float):
                turn.state.precios_vistos[str(o["sku"])] = int(o["precio"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(result)


async def exec_tool(
    turn: Turn, agent_id: str, name: str, args: dict[str, Any], *, confirmada: bool = False, origen: str = "modelo"
) -> dict[str, Any]:
    st = turn.state
    ctx = tools.ToolContext(cliente_id=st.cliente_id, sesion_id=st.sesion_id, run_id=st.run_id)
    spec = tools.get(name)
    escritura = bool(spec and spec.spec.escritura)
    turn.emit(
        "tools",
        "tool_call",
        f"{name}({_args_txt(args)})",
        {"agente": agent_id, "tool": name, "args": args, "escritura": escritura, "origen": origen},
    )
    res = await tools.run_tool(name, args, ctx)
    rec = {
        "name": name,
        "args": args,
        "result": res.model_dump(),
        "ms": res.ms,
        "escritura": escritura,
        "confirmada": confirmada,
        "agente": agent_id,
    }
    st.tools_llamadas.append(rec)
    if res.ok:
        _registrar_precios(turn, res.data)
    if (escritura or confirmada) and res.ok:
        st.acciones.append({"tool": name, "args": args, "estado": "ejecutada"})
    turn.emit("tools", "tool_result", f"{name} → {'ok' if res.ok else 'error'}", res.model_dump(), ms=res.ms)
    return res.model_dump()


def _args_txt(args: dict[str, Any]) -> str:
    s = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items())
    return s if len(s) < 90 else s[:87] + "…"


def _es_escritura(agent: AgentDef, name: str) -> bool:
    spec = tools.get(name)
    return bool(spec and spec.spec.escritura) or name in agent.acciones_escritura


async def prefetch_hibrido(turn: Turn, agent: AgentDef) -> None:
    """Híbrido: el runtime completa precios_api con buscar_producto + consultar_stock ANTES del LLM."""
    st = turn.state
    msg = data.norm(st.mensaje)
    palabras = {"vino": "cabernet", "vinos": "cabernet", "cerveza": "cerveza", "cervezas": "cerveza", "pisco": "pisco"}
    for p in await data.productos():
        w = data.norm(p["nombre"]).split()[0]
        palabras.setdefault(w, w)
        if w.endswith("s"):
            palabras.setdefault(w[:-1], w)
    vistos: set[str] = set()
    for w, q in palabras.items():
        if not re.search(r"\b" + re.escape(w) + r"\b", msg) or q in vistos:
            continue
        vistos.add(q)
        r = await exec_tool(turn, agent.id, "buscar_producto", {"q": q}, origen="runtime")
        if not r["ok"] or not r["data"]:
            continue
        prod = r["data"][0]
        s = await exec_tool(
            turn, agent.id, "consultar_stock", {"sku": prod["sku"], "tienda": st.tienda}, origen="runtime"
        )
        if s["ok"]:
            d = s["data"]
            st.precios_api.append(
                {
                    "sku": d["sku"],
                    "nombre": d["nombre"],
                    "precio": d["precio"],
                    "stock": d["stock"],
                    "tienda": d["tienda"],
                }
            )
        if len(vistos) >= 3:
            break


async def run(turn: Turn, agent: AgentDef) -> str:
    """Devuelve 'ok' | 'pendiente' | 'limite' | 'reenrutar:<id>'."""
    st = turn.state
    nodo = agent.id
    if not st.mensajes_llm:
        if agent.tipo == AgentType.hibrido:
            await prefetch_hibrido(turn, agent)
        st.mensajes_llm = build_messages(turn, agent, with_memory=True)
    oa_tools = tools.openai_tools(agent.tools)
    for _ in range(agent.limits.max_iters):
        res = await call_llm(
            turn,
            agent,
            "tools",
            st.mensajes_llm,
            nodo=nodo,
            titulo=f"{agent.nombre} · ciclo",
            tools=oa_tools,
            ctx={"tienda": st.tienda, "cliente_id": st.cliente_id},
        )
        st.mensajes_llm.append(res.assistant_message())
        if res.tool_calls:
            if res.content and res.content.strip():
                turn.emit(nodo, "thought", res.content.strip()[:300], res.content)
            pendientes = list(res.tool_calls)
            while pendientes:
                call = pendientes.pop(0)
                out = await _procesar_call(turn, agent, call.id, call.name, call.args())
                if out == "pendiente":
                    st.accion_pendiente["restantes"] = [
                        {"id": c.id, "name": c.name, "args": c.args()} for c in pendientes
                    ]
                    return "pendiente"
                if out == "repetida":
                    for c in pendientes:
                        st.mensajes_llm.append(
                            {
                                "role": "tool",
                                "tool_call_id": c.id,
                                "content": json.dumps({"ok": False, "error": "omitida"}),
                            }
                        )
                    st.respuesta = "Detuve la búsqueda porque estaba repitiendo la misma consulta sin avanzar. ¿Me das más detalles, o prefieres que te derive con una persona?"
                    st.respuesta_raw = st.respuesta
                    turn.emit(nodo, "output", "Corte por acción repetida", st.respuesta)
                    return "ok"
            continue
        content = res.content or ""
        m = FUERA_RE.search(content)
        if m and len(content.strip()) < 200:
            try:
                fd = json.loads(m.group(0))
                sugerido = str(fd.get("sugerido") or "")
            except json.JSONDecodeError:
                sugerido = ""
            turn.emit(
                nodo,
                "decision",
                f"fuera de dominio → {sugerido or '?'}",
                {"fuera_de_dominio": True, "sugerido": sugerido},
            )
            return f"reenrutar:{sugerido}"
        texto, meta = separar_meta(content)
        st.respuesta, st.respuesta_raw, st.meta = texto, content, meta
        turn.emit(nodo, "output", texto[:140], {"respuesta": texto, "meta": meta})
        return "ok"
    st.respuesta = "Alcancé el límite de pasos para esta consulta sin una respuesta completa. Puedo derivarte con una persona o puedes darme más detalles."
    st.respuesta_raw = st.respuesta
    st.estado = "limite"
    turn.emit(nodo, "error", f"max_iters={agent.limits.max_iters} alcanzado", st.respuesta)
    return "limite"


async def _procesar_call(turn: Turn, agent: AgentDef, call_id: str, name: str, args: dict[str, Any]) -> str:
    st = turn.state
    args = {k: v for k, v in args.items() if k != "cliente_id"}  # nunca confiar en un cliente_id del modelo
    firma = name + json.dumps(args, sort_keys=True, ensure_ascii=False)
    if firma in st.firmas_tools:
        turn.emit("tools", "error", f"acción repetida: {name}", {"tool": name, "args": args})
        st.mensajes_llm.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps({"ok": False, "error": "acción repetida: mismo nombre y argumentos"}),
            }
        )
        return "repetida"
    st.firmas_tools.append(firma)
    if name not in agent.tools:
        err = {
            "ok": False,
            "error": f"la herramienta '{name}' no está permitida para este agente; usa: {', '.join(agent.tools)}",
        }
        turn.emit("tools", "tool_result", f"{name} → no permitida", err)
        st.mensajes_llm.append(
            {"role": "tool", "tool_call_id": call_id, "content": json.dumps(err, ensure_ascii=False)}
        )
        return "ok"
    if _es_escritura(agent, name):
        spec = tools.get(name)
        try:
            spec.args_model.model_validate(args) if spec else None  # type: ignore[union-attr]
        except Exception as exc:
            from pydantic import ValidationError

            msg = tools._fmt_validation(exc) if isinstance(exc, ValidationError) else str(exc)
            err = {"ok": False, "error": msg}
            turn.emit("tools", "tool_result", f"{name} → argumentos inválidos", err)
            st.mensajes_llm.append(
                {"role": "tool", "tool_call_id": call_id, "content": json.dumps(err, ensure_ascii=False)}
            )
            return "ok"
        descripcion = await describir(name, args, st.cliente_id)
        st.accion_pendiente = {
            "modo": "especialista",
            "agente": agent.id,
            "tool_call_id": call_id,
            "tool": name,
            "args": args,
            "descripcion": descripcion,
        }
        st.acciones.append({"tool": name, "args": args, "estado": "pendiente_confirmacion"})
        turn.emit(
            "tools",
            "tool_call",
            f"{name}({_args_txt(args)})",
            {"agente": agent.id, "tool": name, "args": args, "escritura": True, "origen": "modelo"},
        )
        turn.emit(
            agent.id,
            "confirm_required",
            descripcion,
            {"run_id": st.run_id, "tool": name, "args": args, "descripcion": descripcion},
        )
        return "pendiente"
    result = await exec_tool(turn, agent.id, name, args)
    st.mensajes_llm.append(
        {"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False, default=str)}
    )
    return "ok"


async def resume(turn: Turn, agent: AgentDef, confirmar: bool) -> str:
    """Continúa tras /chat/confirm: ejecuta (o cancela) la acción y sigue el loop."""
    st = turn.state
    p = st.accion_pendiente or {}
    st.accion_pendiente = None
    for a in st.acciones:
        if a["tool"] == p.get("tool") and a["args"] == p.get("args") and a["estado"] == "pendiente_confirmacion":
            a["estado"] = "ejecutada" if confirmar else "cancelada"
    if confirmar:
        st.acciones = [
            a
            for a in st.acciones
            if not (a["tool"] == p.get("tool") and a["args"] == p.get("args") and a["estado"] == "ejecutada")
        ]
        result = await exec_tool(turn, agent.id, p["tool"], p["args"], confirmada=True)
    else:
        result = {"ok": False, "error": "el usuario canceló la acción; no se ejecutó"}
        turn.emit("tools", "tool_result", f"{p.get('tool')} → cancelada por el usuario", result)
    st.mensajes_llm.append(
        {
            "role": "tool",
            "tool_call_id": p.get("tool_call_id"),
            "content": json.dumps(result, ensure_ascii=False, default=str),
        }
    )
    restantes = p.get("restantes") or []
    while restantes:
        c = restantes.pop(0)
        out = await _procesar_call(turn, agent, c["id"], c["name"], c["args"])
        if out == "pendiente" and st.accion_pendiente is not None:
            st.accion_pendiente["restantes"] = restantes
            return "pendiente"
    if not confirmar:
        return "cancelada"
    return await run(turn, agent)
