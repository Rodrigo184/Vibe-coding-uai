"""Contexto del turno, llamada LLM con límites globales y construcción de variables/prompts."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.engine import templates
from app.engine.state import TurnState
from app.engine.tracer import Tracer
from app.llm import client as llm
from app.models.agent import AgentDef
from app.tools import registry as tool_registry


class LimitExceeded(Exception):
    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


@dataclass
class Turn:
    state: TurnState
    tracer: Tracer
    supervisor: AgentDef
    agents: dict[str, AgentDef]
    max_calls: int
    max_cost: float
    max_seconds: float
    t0: float = field(default_factory=time.time)
    evaluating: bool = False

    @property
    def sup(self) -> dict[str, Any]:
        return self.supervisor.constantes

    def emit(self, nodo: str, tipo: str, titulo: str, contenido: Any = "", **kw: Any):
        return self.tracer.emit(nodo, tipo, titulo, contenido, **kw)


def check_limits(turn: Turn) -> None:
    st = turn.state
    if st.llamadas_llm >= turn.max_calls:
        raise LimitExceeded(f"máximo de {turn.max_calls} llamadas a modelos por turno")
    if st.costo_usd >= turn.max_cost:
        raise LimitExceeded(f"presupuesto de {turn.max_cost} USD por turno")
    if time.time() - turn.t0 > turn.max_seconds:
        raise LimitExceeded(f"timeout de {turn.max_seconds:.0f} s por turno")


def _preview_messages(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        d: dict[str, Any] = {"role": m["role"], "content": (m.get("content") or "")[:2000]}
        if m.get("tool_calls"):
            d["tool_calls"] = [
                {"name": c["function"]["name"], "arguments": c["function"]["arguments"][:500]} for c in m["tool_calls"]
            ]
        if m.get("tool_call_id"):
            d["tool_call_id"] = m["tool_call_id"]
        out.append(d)
    return out


async def call_llm(
    turn: Turn,
    agent: AgentDef,
    kind: str,
    messages: list[dict],
    *,
    nodo: str,
    titulo: str,
    model: str | None = None,
    **kw: Any,
) -> llm.LLMResult:
    check_limits(turn)
    lim = agent.limits
    model = model or lim.modelo or get_settings().openai_model
    common: dict[str, Any] = {
        "model": model,
        "temperature": lim.temperature,
        "max_tokens": lim.max_tokens_out,
        "timeout": float(lim.timeout_s),
    }
    if kind == "json":
        res = await llm.chat_json(messages, **common, **kw)
    elif kind == "tools":
        res = await llm.chat_tools(messages, **common, **kw)
    else:
        res = await llm.chat(messages, **common)
    st = turn.state
    st.llamadas_llm += 1
    st.costo_usd = round(st.costo_usd + res.costo_usd, 6)
    respuesta: Any = res.parsed if res.parsed is not None else (res.content or "")
    if res.tool_calls:
        respuesta = {
            "content": res.content,
            "tool_calls": [{"name": c.name, "arguments": c.args()} for c in res.tool_calls],
        }
    turn.emit(
        nodo,
        "llm_call",
        titulo,
        {"agente": agent.id, "messages": _preview_messages(messages), "respuesta": respuesta, "demo": res.demo},
        tokens_in=res.tokens_in,
        tokens_out=res.tokens_out,
        costo_usd=res.costo_usd,
        ms=res.ms,
        modelo=res.modelo,
    )
    return res


# ----------------------------------------------------------------------------- variables de estado
def historial_txt(historial: list[dict]) -> str:
    if not historial:
        return "(sin turnos previos)"
    return "\n".join(f"{t.get('rol', '?')}: {t.get('texto', '')}" for t in historial[-10:])


def lista_especialistas(turn: Turn) -> str:
    lines = []
    for aid in turn.sup.get("especialistas", []):
        a = turn.agents.get(aid)
        if not a or not a.activo:
            continue
        dominio = a.dominio or a.descripcion
        ejemplo = a.constantes.get("ejemplo") or (a.usar_cuando[0] if a.usar_cuando else "")
        lines.append(f'{aid} — {dominio} — "{ejemplo}"')
    lines.append(
        'humano — temas sensibles (salud, legal, amenazas), datos de otros clientes o nada encaja — "necesito hablar con alguien"'
    )
    return "\n".join(lines)


def state_vars(turn: Turn, agent: AgentDef | None = None, **extra: Any) -> dict[str, Any]:
    st = turn.state
    s = get_settings()
    router = st.router or {}
    ep = list(reversed(st.episodios))[:3]
    agent_tools = agent.tools if agent else []
    escritura = agent.acciones_escritura if agent else []
    v: dict[str, Any] = {
        "nombre_app": turn.sup.get("nombre_app", "SuperApp"),
        "fecha": st.fecha,
        "hora": st.hora,
        "canal": st.canal,
        "mensaje": st.mensaje,
        "solicitud": st.mensaje,
        "historial": historial_txt(st.historial),
        "perfil": json.dumps(st.perfil, ensure_ascii=False),
        "episodios": json.dumps([e.get("resumen", e) if isinstance(e, dict) else e for e in ep], ensure_ascii=False),
        "tienda": st.tienda,
        "tools_json": json.dumps(tool_registry.tools_json(agent_tools, escritura), ensure_ascii=False),
        "lista_especialistas": lista_especialistas(turn),
        "motivo": router.get("motivo", "—"),
        "intenciones_secundarias": json.dumps(router.get("intenciones_secundarias", []), ensure_ascii=False),
        "veredicto_reglas": json.dumps(st.veredicto_reglas_pre, ensure_ascii=False),
        "precios_api": json.dumps(st.precios_api, ensure_ascii=False),
        "acciones_escritura": ", ".join(escritura) or "ninguna",
        "max_iters": agent.limits.max_iters if agent else 5,
        "max_pasos": 8,
        "nombre_especialista": agent.nombre if agent else "",
        "descripcion_dominio": (agent.dominio or agent.descripcion) if agent else "",
        "respuesta": st.respuesta or "",
        "contexto": "",
        "tools_resultados": "",
        "respuesta_esperada": st.respuesta_esperada or "ninguna",
        "reglas_negocio": "",
        "objetivo": st.mensaje,
        "cliente": f"{st.cliente_id} · {st.cliente_nombre}".strip(" ·"),
        "resultados_previos": "ninguno",
        "cliente_id": st.cliente_id,
        "sesion_id": st.sesion_id,
        "max_llamadas": s.max_llm_calls_per_turn,
        "max_costo_usd": s.max_turn_cost_usd,
        "timeout_s": s.max_turn_seconds,
    }
    if agent:
        for k, val in agent.constantes.items():
            if isinstance(val, str | int | float):
                v[k] = val
    v.update(extra)
    return v


# ----------------------------------------------------------------------------- secciones del prompt
SECCION_RE = re.compile(r"^=== (.+?) ===\s*$", re.M)


def split_sections(system: str) -> dict[str, str]:
    """Divide un system con bloques `=== A · … ===`. Clave = primera letra/palabra del título."""
    parts = SECCION_RE.split(system)
    if len(parts) == 1:
        return {"_": system}
    out: dict[str, str] = {}
    if parts[0].strip():
        out["_"] = parts[0].strip("\n")
    for i in range(1, len(parts), 2):
        key = parts[i].split("·")[0].strip().split()[0].upper()
        out[key] = parts[i + 1].strip("\n")
    return out


def inject_tools_block(system: str, bloque: str) -> str:
    if not bloque or "[CÓMO USAR LAS HERRAMIENTAS]" in system:
        return system
    m = re.search(r"\[HERRAMIENTAS[^\]]*\]\n.*?(?=\n\[[^\]]+\]\n|\Z)", system, re.S)
    if not m:
        return system
    return system[: m.end()] + "\n\n[CÓMO USAR LAS HERRAMIENTAS]\n" + bloque + system[m.end() :]


def memory_block(turn: Turn) -> str:
    """Parte A del prompt del extractor ([MEMORIA DISPONIBLE] + [CÓMO USAR LA MEMORIA]) para especialistas."""
    ext = turn.agents.get(turn.sup.get("extractor_id", "extractor"))
    if not ext:
        return ""
    a = split_sections(ext.prompt.system).get("A", "")
    m = re.search(r"\[MEMORIA DISPONIBLE\].*?(?=\n\[REGLAS\]|\Z)", a, re.S)
    if not m:
        return ""
    try:
        return templates.render(m.group(0), state_vars(turn, ext)).strip()
    except templates.TemplateError:
        return ""


def build_messages(
    turn: Turn,
    agent: AgentDef,
    system_tpl: str | None = None,
    user_tpl: str | None = None,
    *,
    with_memory: bool = False,
    **extra: Any,
) -> list[dict]:
    vars_ = state_vars(turn, agent, **extra)
    system = templates.render(system_tpl if system_tpl is not None else agent.prompt.system, vars_)
    if agent.tools:
        system = inject_tools_block(system, turn.sup.get("bloque_tools", ""))
    if with_memory:
        mb = memory_block(turn)
        if mb:
            system = system.rstrip() + "\n\n" + mb
    user = templates.render(user_tpl if user_tpl is not None else agent.prompt.user, vars_)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


META_RE = re.compile(r"<meta>(.*?)</meta>", re.S)


def separar_meta(texto: str) -> tuple[str, dict[str, Any]]:
    texto = texto or ""
    meta: dict[str, Any] = {}
    m = META_RE.search(texto)
    if m:
        try:
            meta = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            meta = {"_invalido": m.group(1).strip()[:300]}
    limpio = META_RE.sub("", texto)
    lineas = [ln for ln in limpio.splitlines() if not re.match(r"^\s*(Thought|Action|Observation)\s*:", ln)]
    limpio = "\n".join(lineas).strip()
    limpio = re.sub(r"^\s*Final Answer\s*:\s*", "", limpio)
    return limpio.strip(), meta
