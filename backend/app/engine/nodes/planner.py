"""Planner–Executor–Verificador (sección 7.4).

1. Planner (chat_json PlanOut) → valida tools y grafo acíclico.
2. Ejecuta pasos por niveles de dependencia (independientes en paralelo con asyncio.gather);
   `{"$paso": n}` / `{"$paso": n, "campo": "a.b"}` / `{"$pasos": [n, m]}` se resuelven con resultados previos.
3. Pasos con requiere_confirmacion o tools de escritura pausan el turno.
4. Verificador (chat_json VerifyOut); si hay fallidos y replanificaciones < 2 → replanifica.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import ValidationError

from app.engine.nodes.base import Turn, build_messages, call_llm, split_sections
from app.engine.nodes.specialist import exec_tool
from app.llm.schemas import PlanOut, VerifyOut
from app.models.agent import AgentDef
from app.tools import registry as tools
from app.tools.describe import describir

MAX_REPLAN = 2


def _prompts(agent: AgentDef) -> tuple[str, str]:
    sys = agent.prompt.system
    if "=== VERIFICADOR" in sys:
        plan_sys, ver = sys.split("=== VERIFICADOR", 1)
        ver = ver.split("\n", 1)[1] if "\n" in ver else ver
        return plan_sys.rstrip(), ver.strip()
    secs = split_sections(sys)
    return secs.get("_", sys), secs.get(
        "VERIFICADOR", "[ROL]\nVerificas la ejecución de un plan.\n[PLAN Y RESULTADOS]\n{{resultados_previos}}"
    )


def validar_plan(plan: dict[str, Any], agent: AgentDef, max_pasos: int) -> tuple[list[list[dict]], list[str]]:
    """Devuelve (niveles, problemas)."""
    problemas: list[str] = []
    pasos = plan.get("pasos") or []
    if not pasos:
        return [], ["el plan no tiene pasos"]
    if len(pasos) > max_pasos:
        problemas.append(f"el plan tiene {len(pasos)} pasos (máximo {max_pasos})")
    ids = [p.get("id") for p in pasos]
    if len(set(ids)) != len(ids):
        problemas.append("ids de pasos repetidos")
    for p in pasos:
        if p.get("tool") != "pedir_aclaracion" and p.get("tool") not in agent.tools:
            problemas.append(f"paso {p.get('id')}: la herramienta '{p.get('tool')}' no está disponible")
        for d in p.get("depende_de") or []:
            if d not in ids:
                problemas.append(f"paso {p.get('id')}: depende de un paso inexistente ({d})")
    if problemas:
        return [], problemas
    niveles: list[list[dict]] = []
    hechos: set[int] = set()
    restantes = list(pasos)
    while restantes:
        nivel = [p for p in restantes if set(p.get("depende_de") or []) <= hechos]
        if not nivel:
            return [], ["el grafo de dependencias tiene un ciclo"]
        niveles.append(nivel)
        hechos |= {p["id"] for p in nivel}
        restantes = [p for p in restantes if p["id"] not in hechos]
    return niveles, []


def _get_path(obj: Any, path: str | None) -> Any:
    if not path:
        return obj
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit():
            obj = obj[int(part)] if int(part) < len(obj) else None
        else:
            return None
    return obj


def resolver_refs(obj: Any, resultados: dict[str, Any]) -> Any:
    if isinstance(obj, dict):
        if "$paso" in obj:
            r = resultados.get(str(obj["$paso"]), {})
            return _get_path(r.get("data"), obj.get("campo"))
        if "$pasos" in obj:
            return [resultados.get(str(n), {}).get("data") for n in obj["$pasos"]]
        return {k: resolver_refs(v, resultados) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolver_refs(x, resultados) for x in obj]
    return obj


async def _planificar(turn: Turn, agent: AgentDef) -> dict[str, Any]:
    st = turn.state
    plan_sys, _ = _prompts(agent)
    previos = (
        "ninguno"
        if not st.plan_resultados
        else json.dumps({"plan": st.plan, "resultados": st.plan_resultados}, ensure_ascii=False, default=str)[:6000]
    )
    msgs = build_messages(turn, agent, system_tpl=plan_sys, resultados_previos=previos)
    res = await call_llm(
        turn,
        agent,
        "json",
        msgs,
        nodo=agent.id,
        titulo="Planificar" if not st.plan_resultados else "Replanificar",
        schema=agent.prompt.salida_schema or PlanOut,
        name="PlanOut",
        strict=False,
    )
    return res.parsed if isinstance(res.parsed, dict) else {}


async def run(turn: Turn, agent: AgentDef) -> str:
    """Devuelve 'ok' | 'pendiente' | 'error'."""
    st = turn.state
    max_pasos = int(agent.constantes.get("max_pasos", 8))
    while True:
        if st.plan is None:
            plan = await _planificar(turn, agent)
            niveles, problemas = validar_plan(plan, agent, max_pasos)
            if problemas:
                turn.emit(agent.id, "error", "plan inválido", {"problemas": problemas, "plan": plan})
                if st.replanificaciones < MAX_REPLAN:
                    st.replanificaciones += 1
                    st.plan_resultados = {"_errores_plan": problemas}
                    continue
                st.respuesta = "No pude armar un plan válido para tu objetivo. ¿Puedes darme más detalles, o prefieres que lo vea una persona?"
                st.respuesta_raw = st.respuesta
                return "error"
            st.plan = plan
            st.plan_resultados = {}
            turn.emit(
                agent.id,
                "decision",
                f"Plan de {len(plan.get('pasos', []))} pasos · {len(niveles)} niveles",
                {**plan, "niveles": [[p["id"] for p in n] for n in niveles]},
            )
        niveles, _ = validar_plan(st.plan, agent, max_pasos)
        primero = (st.plan.get("pasos") or [{}])[0]
        if primero.get("tool") == "pedir_aclaracion":
            st.respuesta = str((primero.get("args") or {}).get("pregunta") or "¿Me das más detalles del objetivo?")
            st.respuesta_raw = st.respuesta
            turn.emit(agent.id, "output", "Pide aclaración", st.respuesta)
            return "ok"
        out = await _ejecutar(turn, agent, niveles)
        if out == "pendiente":
            return "pendiente"
        return await verificar(turn, agent)


async def _ejecutar(turn: Turn, agent: AgentDef, niveles: list[list[dict]]) -> str:
    st = turn.state
    for i, nivel in enumerate(niveles):
        por_hacer = [p for p in nivel if str(p["id"]) not in st.plan_resultados]
        if not por_hacer:
            continue
        lectura = [p for p in por_hacer if not (p.get("requiere_confirmacion") or _escritura(agent, p["tool"]))]
        escritura = [p for p in por_hacer if p not in lectura]
        if lectura:
            turn.emit(
                agent.id,
                "thought",
                f"Nivel {i + 1}: ejecuto pasos {[p['id'] for p in lectura]}"
                + (" en paralelo" if len(lectura) > 1 else ""),
                {"pasos": [p["id"] for p in lectura]},
            )
            resultados = await asyncio.gather(
                *[
                    exec_tool(turn, agent.id, p["tool"], resolver_refs(p.get("args") or {}, st.plan_resultados))
                    for p in lectura
                ]
            )
            for p, r in zip(lectura, resultados, strict=True):
                st.plan_resultados[str(p["id"])] = {"id": p["id"], "tool": p["tool"], **r}
        if escritura:
            p = escritura[0]
            args = resolver_refs(p.get("args") or {}, st.plan_resultados)
            args = {k: v for k, v in args.items() if k != "cliente_id"}
            spec = tools.get(p["tool"])
            if spec is not None:
                try:
                    spec.args_model.model_validate(args)
                except ValidationError as exc:
                    err = tools._fmt_validation(exc)
                    st.plan_resultados[str(p["id"])] = {
                        "id": p["id"],
                        "tool": p["tool"],
                        "ok": False,
                        "data": None,
                        "error": err,
                    }
                    turn.emit(
                        "tools",
                        "tool_result",
                        f"{p['tool']} (paso {p['id']}) → argumentos inválidos",
                        {"ok": False, "error": err},
                    )
                    return "ok"
            descripcion = await describir(p["tool"], args, st.cliente_id)
            st.accion_pendiente = {
                "modo": "planner",
                "agente": agent.id,
                "paso": p["id"],
                "tool": p["tool"],
                "args": args,
                "descripcion": descripcion,
            }
            st.acciones.append({"tool": p["tool"], "args": args, "estado": "pendiente_confirmacion"})
            ok_ids = [k for k, v in st.plan_resultados.items() if v.get("ok")]
            st.respuesta = f"Preparé el plan «{st.plan.get('objetivo', '')}» y ya ejecuté {len(ok_ids)} paso(s). Para terminar necesito tu confirmación: {descripcion}. ¿Lo confirmo?"
            st.respuesta_raw = st.respuesta
            turn.emit(
                "tools",
                "tool_call",
                f"{p['tool']} (paso {p['id']})",
                {"agente": agent.id, "tool": p["tool"], "args": args, "escritura": True, "paso": p["id"]},
            )
            turn.emit(
                agent.id,
                "confirm_required",
                descripcion,
                {"run_id": st.run_id, "tool": p["tool"], "args": args, "descripcion": descripcion, "paso": p["id"]},
            )
            return "pendiente"
    return "ok"


def _escritura(agent: AgentDef, name: str) -> bool:
    t = tools.get(name)
    return bool(t and t.spec.escritura) or name in agent.acciones_escritura


async def verificar(turn: Turn, agent: AgentDef) -> str:
    st = turn.state
    _, ver_sys = _prompts(agent)
    resultados = []
    for r in st.plan_resultados.values():
        data = r.get("data")
        txt = json.dumps(data, ensure_ascii=False, default=str)
        item = {"id": r.get("id"), "tool": r.get("tool"), "ok": r.get("ok"), "error": r.get("error")}
        if isinstance(data, dict):
            item.update(
                {
                    k: data[k]
                    for k in ("pedido_id", "estado", "total", "faltantes", "skus", "advertencias_stock")
                    if k in data
                }
            )
        item["data"] = data if len(txt) <= 1200 else txt[:1200] + "…"
        resultados.append(item)
    previos = json.dumps({"plan": st.plan, "resultados": resultados}, ensure_ascii=False, default=str)
    msgs = build_messages(
        turn,
        agent,
        system_tpl=ver_sys,
        user_tpl="Verifica el plan y sus resultados. Responde solo JSON.",
        resultados_previos=previos,
    )
    res = await call_llm(
        turn, agent, "json", msgs, nodo=agent.id, titulo="Verificador", schema=VerifyOut, name="VerifyOut"
    )
    v = res.parsed if isinstance(res.parsed, dict) else {}
    turn.emit(
        agent.id, "judge", f"Verificador: {len(v.get('pasos_ok', []))} ok · {len(v.get('fallidos', []))} fallidos", v
    )
    if v.get("fallidos") and st.replanificaciones < MAX_REPLAN:
        st.replanificaciones += 1
        turn.emit(agent.id, "decision", f"Replanificación {st.replanificaciones}/{MAX_REPLAN}", v.get("fallidos"))
        st.plan = None
        return await run(turn, agent)
    st.respuesta = v.get("resumen") or "Plan ejecutado."
    st.respuesta_raw = st.respuesta
    st.meta = {"plan": st.plan.get("objetivo") if st.plan else None, "verificador": v}
    turn.emit(agent.id, "output", st.respuesta[:140], {"respuesta": st.respuesta, "verificador": v})
    return "ok"


async def resume(turn: Turn, agent: AgentDef, confirmar: bool) -> str:
    st = turn.state
    p = st.accion_pendiente or {}
    st.accion_pendiente = None
    for a in st.acciones:
        if a["tool"] == p.get("tool") and a["estado"] == "pendiente_confirmacion":
            a["estado"] = "cancelada" if not confirmar else "_reemplazar"
    st.acciones = [a for a in st.acciones if a["estado"] != "_reemplazar"]
    if not confirmar:
        turn.emit(
            "tools", "tool_result", f"{p.get('tool')} → cancelada por el usuario", {"ok": False, "error": "cancelada"}
        )
        return "cancelada"
    r = await exec_tool(turn, agent.id, p["tool"], p["args"], confirmada=True)
    st.plan_resultados[str(p["paso"])] = {"id": p["paso"], "tool": p["tool"], **r}
    niveles, _ = validar_plan(st.plan or {}, agent, int(agent.constantes.get("max_pasos", 8)))
    out = await _ejecutar(turn, agent, niveles)
    if out == "pendiente":
        return "pendiente"
    return await verificar(turn, agent)
