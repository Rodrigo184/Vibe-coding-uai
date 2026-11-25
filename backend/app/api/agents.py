from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ValidationError

from app.api.errors import ApiError, not_found
from app.engine import registry, templates
from app.models.agent import AgentDef, AgentSummary, AgentType
from app.tools import registry as tool_registry

router = APIRouter(prefix="/agents", tags=["agentes"])

ESTADO_VARS = {
    "nombre_app",
    "fecha",
    "hora",
    "canal",
    "mensaje",
    "solicitud",
    "historial",
    "perfil",
    "episodios",
    "tienda",
    "tools_json",
    "lista_especialistas",
    "motivo",
    "intenciones_secundarias",
    "veredicto_reglas",
    "precios_api",
    "acciones_escritura",
    "max_iters",
    "max_pasos",
    "nombre_especialista",
    "descripcion_dominio",
    "respuesta",
    "contexto",
    "tools_resultados",
    "respuesta_esperada",
    "reglas_negocio",
    "objetivo",
    "cliente",
    "resultados_previos",
    "cliente_id",
    "sesion_id",
    "max_llamadas",
    "max_costo_usd",
    "timeout_s",
}


def _schema_problemas(schema: Any) -> list[str]:
    if schema is None:
        return []
    if not isinstance(schema, dict):
        return ["salida_schema debe ser un objeto JSON"]
    p = []
    if schema.get("type") != "object":
        p.append("salida_schema: 'type' debe ser 'object'")
    props = schema.get("properties")
    if not isinstance(props, dict) or not props:
        p.append("salida_schema: falta 'properties' (objeto no vacío)")
        return p
    req = schema.get("required", [])
    if not isinstance(req, list):
        p.append("salida_schema: 'required' debe ser una lista")
    else:
        faltan = [r for r in req if r not in props]
        if faltan:
            p.append(f"salida_schema: 'required' menciona propiedades inexistentes: {', '.join(faltan)}")
    for k, v in props.items():
        if not isinstance(v, dict) or not ({"type", "enum", "anyOf", "$ref"} & set(v)):
            p.append(f"salida_schema: la propiedad '{k}' necesita 'type'")
    return p


async def validar(agent: AgentDef, creando: bool = False) -> list[dict[str, str]]:
    problemas: list[dict[str, str]] = []

    def add(nivel: str, campo: str, msg: str) -> None:
        problemas.append({"nivel": nivel, "campo": campo, "mensaje": msg})

    agents = await registry.all_agents()
    if creando and agent.id in agents:
        add("error", "id", f"ya existe un agente con id '{agent.id}'")
    tools_ok = {t.name for t in tool_registry.specs()}
    for t in agent.tools:
        if t not in tools_ok:
            add("error", "tools", f"la herramienta '{t}' no existe en el registro")
    for t in agent.acciones_escritura:
        if t not in agent.tools:
            add("error", "acciones_escritura", f"'{t}' exige confirmación pero no está en las tools del agente")
    usadas = templates.extraer_variables(agent.prompt.system) | templates.extraer_variables(agent.prompt.user)
    declaradas = {v.nombre for v in agent.prompt.variables}
    for nombre in sorted(usadas - declaradas):
        add("error", "prompt", f"variable no declarada: {{{{{nombre}}}}}")
    for nombre in sorted(declaradas - usadas):
        add("aviso", "variables", f"variable declarada pero no usada en el prompt: {nombre}")
    for v in agent.prompt.variables:
        if v.origen == "estado" and v.nombre not in ESTADO_VARS:
            add(
                "aviso",
                "variables",
                f"'{v.nombre}' tiene origen 'estado' pero el runtime no la provee; usa origen 'constante' o 'usuario'",
            )
        if v.origen == "constante" and v.nombre not in agent.constantes:
            add("error", "constantes", f"falta el valor de la constante '{v.nombre}'")
    for campo, texto in (("prompt.system", agent.prompt.system), ("prompt.user", agent.prompt.user)):
        if templates.tiene_no_aislado(texto):
            add(
                "error",
                campo,
                'contiene la palabra "NO" en mayúsculas aislada; usa "Evita", "Prohibido", "Solo" o "Nunca"',
            )
        try:
            templates.render_safe(texto, {})
        except Exception as exc:  # pragma: no cover
            add("error", campo, f"plantilla inválida: {exc}")
    for msg in _schema_problemas(agent.prompt.salida_schema):
        add("error", "salida_schema", msg)
    if agent.tipo in (AgentType.router, AgentType.evaluador, AgentType.memoria) and not agent.prompt.salida_schema:
        add("aviso", "salida_schema", f"un agente tipo {agent.tipo.value} debería declarar salida_schema")
    if agent.tipo == AgentType.supervisor:
        c = agent.constantes
        for k in ("router_id", "evaluador_id", "extractor_id"):
            if c.get(k) and c[k] not in agents:
                add("error", f"constantes.{k}", f"'{c[k]}' no existe")
        for e in c.get("especialistas", []):
            if e not in agents and e != agent.id:
                add("error", "constantes.especialistas", f"'{e}' no existe")
        from app.rules import base as rules

        for fase in ("pre", "post"):
            for rn in c.get(f"reglas_{fase}", []):
                r = rules.get(rn)
                if not r or r.fase != fase:
                    add("error", f"constantes.reglas_{fase}", f"regla '{rn}' no existe en fase {fase}")
    return problemas


def _parse(body: dict[str, Any]) -> AgentDef:
    try:
        return AgentDef.model_validate(body)
    except ValidationError as exc:
        msgs = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()[:6])
        raise ApiError(422, "invalid_agent", msgs) from exc


@router.get("", response_model=list[AgentSummary])
async def list_agents() -> list[AgentSummary]:
    agents = await registry.all_agents()
    orden = {t.value: i for i, t in enumerate(AgentType)}
    out = [AgentSummary(**a.model_dump(include=set(AgentSummary.model_fields))) for a in agents.values()]
    return sorted(out, key=lambda a: (0 if a.tipo == AgentType.supervisor else 1, orden.get(a.tipo.value, 9), a.id))


@router.get("/{aid}")
async def get_agent(aid: str) -> dict[str, Any]:
    a = await registry.get_agent(aid)
    if not a:
        raise not_found(f"el agente '{aid}'")
    return {**a.model_dump(mode="json"), "tiene_semilla": bool(await registry.seed_copy(aid))}


@router.post("", status_code=201)
async def create_agent(body: dict[str, Any]) -> dict[str, Any]:
    body = {**body, "version": 1, "actualizado": dt.datetime.now(dt.UTC).isoformat()}
    agent = _parse(body)
    errores = [p for p in await validar(agent, creando=True) if p["nivel"] == "error"]
    if errores:
        raise ApiError(422, "validation_failed", " · ".join(p["mensaje"] for p in errores))
    v = await registry.save_agent(agent)
    return {"agent": agent.model_dump(mode="json"), "agents_version": v}


@router.put("/{aid}")
async def update_agent(aid: str, body: dict[str, Any]) -> dict[str, Any]:
    actual = await registry.get_agent(aid)
    if not actual:
        raise not_found(f"el agente '{aid}'")
    body = {**body, "id": aid, "version": actual.version + 1, "actualizado": dt.datetime.now(dt.UTC).isoformat()}
    agent = _parse(body)
    errores = [p for p in await validar(agent) if p["nivel"] == "error"]
    if errores:
        raise ApiError(422, "validation_failed", " · ".join(p["mensaje"] for p in errores))
    v = await registry.save_agent(agent)
    return {
        "agent": agent.model_dump(mode="json"),
        "agents_version": v,
        "mensaje": f"versión {actual.version} → {agent.version}; los próximos turnos usan la nueva versión",
    }


@router.delete("/{aid}")
async def delete_agent(aid: str) -> dict[str, Any]:
    if not await registry.get_agent(aid):
        raise not_found(f"el agente '{aid}'")
    for a in (await registry.all_agents()).values():
        if a.tipo == AgentType.supervisor and a.id != aid:
            c = a.constantes
            refs = [c.get("router_id"), c.get("evaluador_id"), c.get("extractor_id"), *c.get("especialistas", [])]
            if aid in refs:
                raise ApiError(
                    409, "in_use", f"el supervisor '{a.id}' referencia a '{aid}'; quítalo de su configuración primero"
                )
    v = await registry.delete_agent(aid)
    return {"ok": True, "agents_version": v}


@router.post("/{aid}/restore")
async def restore_agent(aid: str) -> dict[str, Any]:
    seed = await registry.seed_copy(aid)
    if not seed:
        raise ApiError(404, "no_seed", f"'{aid}' no tiene copia de semilla")
    actual = await registry.get_agent(aid)
    seed = {
        **seed,
        "version": (actual.version + 1) if actual else 1,
        "actualizado": dt.datetime.now(dt.UTC).isoformat(),
    }
    agent = AgentDef.model_validate(seed)
    v = await registry.save_agent(agent)
    return {"agent": agent.model_dump(mode="json"), "agents_version": v}


@router.post("/validate")
async def validate_agent(body: dict[str, Any]) -> dict[str, Any]:
    creando = bool(body.pop("_creando", False))
    try:
        agent = AgentDef.model_validate(
            {**body, "actualizado": body.get("actualizado") or dt.datetime.now(dt.UTC).isoformat()}
        )
    except ValidationError as exc:
        return {
            "ok": False,
            "problemas": [
                {"nivel": "error", "campo": ".".join(str(x) for x in e["loc"]), "mensaje": e["msg"]}
                for e in exc.errors()
            ],
        }
    problemas = await validar(agent, creando=creando)
    return {"ok": not any(p["nivel"] == "error" for p in problemas), "problemas": problemas}


class RenderIn(BaseModel):
    variables: dict[str, Any] = {}
    agent: dict[str, Any] | None = None  # opcional: renderizar el borrador del editor sin guardar


@router.post("/{aid}/render")
async def render_agent(aid: str, body: RenderIn) -> dict[str, Any]:
    if body.agent:
        agent = AgentDef.model_validate({**body.agent, "actualizado": dt.datetime.now(dt.UTC).isoformat()})
    else:
        a = await registry.get_agent(aid)
        if not a:
            raise not_found(f"el agente '{aid}'")
        agent = a
    vals: dict[str, Any] = {v.nombre: v.ejemplo for v in agent.prompt.variables}
    vals.update({k: v for k, v in agent.constantes.items() if isinstance(v, str | int | float)})
    vals.update(body.variables)
    system, f1 = templates.render_safe(agent.prompt.system, vals)
    user, f2 = templates.render_safe(agent.prompt.user, vals)
    return {"system": system, "user": user, "faltantes": sorted(set(f1 + f2)), "variables": vals}
