"""Genera `agentes.json` a partir de `prompts_semilla.txt` (Sesion4_Prompts_Agentes.txt).

Los prompts son contenido docente: se copian TEXTUALMENTE desde el .txt. Este script solo
agrega la metadata de la sección 9 del SPEC (tipo, tools, flows, riesgos, schemas…).

Uso:  cd backend && uv run python -m app.seed.build_agentes
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
TXT = HERE / "prompts_semilla.txt"
OUT = HERE / "agentes.json"

SECTION_RE = re.compile(r"^#{6,}\s*(\d+)\s*·\s*(.+?)\s*#{6,}\s*$", re.M)


def parse_txt() -> dict[int, dict]:
    text = TXT.read_text(encoding="utf-8")
    matches = list(SECTION_RE.finditer(text))
    out: dict[int, dict] = {}
    for i, m in enumerate(matches):
        body = text[m.end() : matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        parts = re.split(r"^--- (TOOLS|SYSTEM|USER|VARIABLES|SALIDA ESPERADA) ---[ \t]*", body, flags=re.M)
        sec: dict[str, str] = {}
        for j in range(1, len(parts), 2):
            sec[parts[j]] = parts[j + 1].strip("\n").rstrip()
        variables = []
        for line in sec.get("VARIABLES", "").splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            nombre, rest = line.split(":", 1)
            desc, _, ej = rest.strip().partition(" · ej: ")
            variables.append(
                {"nombre": nombre.strip(), "descripcion": desc.strip(), "ejemplo": ej.strip(), "origen": "estado"}
            )
        out[int(m.group(1))] = {
            "titulo": m.group(2),
            "tools": [t.strip() for t in sec.get("TOOLS", "").split(",") if t.strip() and t.strip() != "—"],
            "system": sec.get("SYSTEM", ""),
            "user": sec.get("USER", ""),
            "variables": variables,
            "salida_esperada": sec.get("SALIDA ESPERADA", ""),
        }
    return out


# --------------------------------------------------------------------------- schemas de salida
ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "agente": {"type": "string"},
        "confianza": {"type": "number", "minimum": 0, "maximum": 1},
        "motivo": {"type": "string"},
        "intenciones_secundarias": {"type": "array", "items": {"type": "string"}},
        "alternativo": {"type": ["string", "null"]},
    },
    "required": ["agente", "confianza", "motivo", "intenciones_secundarias", "alternativo"],
    "additionalProperties": False,
}
FACTS_SCHEMA = {
    "type": "object",
    "properties": {
        "hechos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clave": {"type": "string"},
                    "valor": {"type": "string"},
                    "reemplaza": {"type": "boolean"},
                    "fuente": {"type": "string"},
                },
                "required": ["clave", "valor", "reemplaza", "fuente"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["hechos"],
    "additionalProperties": False,
}
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "precision": {"type": "integer", "minimum": 1, "maximum": 5},
        "consistencia": {"type": "integer", "minimum": 1, "maximum": 5},
        "cumplimiento_reglas": {"type": "integer", "minimum": 1, "maximum": 5},
        "evidencia": {"type": "string"},
        "veredicto": {"type": "string", "enum": ["publicar", "regenerar", "humano"]},
        "feedback": {"type": ["string", "null"]},
    },
    "required": ["precision", "consistencia", "cumplimiento_reglas", "evidencia", "veredicto", "feedback"],
    "additionalProperties": False,
}
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "objetivo": {"type": "string"},
        "pasos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "tool": {"type": "string"},
                    "args": {"type": "object"},
                    "depende_de": {"type": "array", "items": {"type": "integer"}},
                    "requiere_confirmacion": {"type": "boolean"},
                    "criterio_exito": {"type": "string"},
                },
                "required": ["id", "tool", "args", "depende_de", "requiere_confirmacion", "criterio_exito"],
            },
        },
        "notas": {"type": "string"},
    },
    "required": ["objetivo", "pasos", "notas"],
}


# --------------------------------------------------------------------------- flows
def n(id_, label, sub, kind, x, y, promptRef=None):  # noqa: N803
    d = {"id": id_, "label": label, "sub": sub, "kind": kind, "x": x, "y": y}
    if promptRef:
        d["promptRef"] = promptRef
    return d


def e(id_, s, t, label=None, kind=None):
    d = {"id": id_, "source": s, "target": t}
    if label:
        d["label"] = label
    if kind:
        d["kind"] = kind
    return d


SUPERVISOR_FLOW = {
    "nodes": [
        n("memoria", "Memoria", "historial · perfil · episodios", "memory", 40, 200),
        n("reglas_pre", "Reglas PRE", "edad · cupo · horario · tarjetas", "rule", 280, 200),
        n("router", "Router", "clasifica → JSON", "llm", 520, 200, "router"),
        n("especialista", "Especialista", "el elegido por el router", "llm", 780, 80),
        n("planner", "Planner", "plan → ejecutores → verificador", "plan", 780, 220, "planner"),
        n("humano", "Humano", "ticket + respuesta fija", "human", 780, 360),
        n("tools", "Tools", "lectura · escritura con confirmación", "tool", 1040, 80),
        n("reglas_post", "Reglas POST", "precios · formato · terceros", "rule", 1040, 220),
        n("evaluador", "Evaluador", "LLM-as-judge", "judge", 1280, 220, "evaluador"),
        n("extractor", "Extractor", "hechos → perfil", "memory", 1280, 360, "extractor"),
        n("final", "Respuesta", "texto + acciones", "output", 1520, 220),
    ],
    "edges": [
        e("e1", "memoria", "reglas_pre"),
        e("e2", "reglas_pre", "router"),
        e("e3", "reglas_pre", "humano", "bloqueo", "fallback"),
        e("e4", "router", "especialista"),
        e("e5", "router", "planner", "objetivo largo"),
        e("e6", "router", "humano", "< umbral", "fallback"),
        e("e7", "especialista", "tools"),
        e("e8", "tools", "especialista", "observa", "loop"),
        e("e9", "planner", "tools"),
        e("e10", "especialista", "reglas_post"),
        e("e11", "planner", "reglas_post"),
        e("e12", "reglas_post", "evaluador"),
        e("e13", "evaluador", "especialista", "regenerar", "loop"),
        e("e14", "evaluador", "humano", "humano", "fallback"),
        e("e15", "evaluador", "extractor", "publicar"),
        e("e16", "humano", "extractor"),
        e("e17", "extractor", "final"),
    ],
}

ROUTER_FLOW = {
    "nodes": [
        n("in", "Mensaje", "usuario + contexto", "input", 40, 220),
        n("mem", "Memoria", "historial · perfil", "memory", 40, 380),
        n("rt", "Router", "clasifica → JSON", "llm", 320, 220, "router"),
        n("val", "Validar JSON", "schema + confianza ≥ 0,6", "rule", 600, 220),
        n("sp", "Especialista", "el que corresponda", "llm", 880, 120),
        n("hum", "Humano", "confianza baja o fuera de catálogo", "human", 880, 340),
    ],
    "edges": [
        e("e1", "in", "rt"),
        e("e2", "mem", "rt", "lee"),
        e("e3", "rt", "val"),
        e("e4", "val", "sp", "ok"),
        e("e5", "val", "hum", "< 0,6", "fallback"),
    ],
}

REACT_FLOW = {
    "nodes": [
        n("q", "Pregunta", "usuario o app", "input", 40, 200),
        n("th", "Thought", "¿qué sé? ¿qué falta?", "llm", 320, 200, "asistente"),
        n("act", "Action", "tool + argumentos JSON", "tool", 600, 200),
        n("obs", "Observation", "resultado real (o error)", "memory", 600, 380),
        n("fin", "Final answer", "respuesta + evidencia", "output", 320, 380),
    ],
    "edges": [
        e("e1", "q", "th"),
        e("e2", "th", "act", "necesito datos"),
        e("e3", "act", "obs"),
        e("e4", "obs", "th", "repite", "loop"),
        e("e5", "th", "fin", "ya tengo todo"),
    ],
}


def specialist_flow(agent_id: str, nombre: str, tools: list[str], escritura: list[str]) -> dict:
    nodes = [
        n("ctx", "Contexto", "del router + memoria", "input", 40, 220),
        n("sp", nombre, "prompt del dominio", "llm", 320, 220, agent_id),
    ]
    edges = [e("e1", "ctx", "sp")]
    for i, t in enumerate(tools):
        nid = f"t{i + 1}"
        y = 40 + i * 120
        nodes.append(n(nid, t, "escritura · confirma" if t in escritura else "lectura", "tool", 600, y))
        if t in escritura:
            edges.append(e(f"e{nid}", "sp", nid, "solo con confirmación"))
        else:
            edges.append(e(f"e{nid}", "sp", nid))
            edges.append(e(f"e{nid}b", nid, "sp", None, "loop"))
    nodes.append(n("ans", "Respuesta", "con evidencia", "output", 880, 220))
    edges.append(e("eans", "sp", "ans"))
    return {"nodes": nodes, "edges": edges}


VENTAS_FLOW = {
    "nodes": [
        n("in", "Entrada", '"3 vinos con la línea de crédito"', "input", 40, 200),
        n("pre", "Reglas PRE", "edad · cupo · horario (código)", "rule", 300, 200),
        n("llm", "LLM", "redacta con el veredicto", "llm", 580, 200, "ventas"),
        n("post", "Reglas POST", "precios API · formato · terceros", "rule", 860, 200),
        n("out", "Salida", "respuesta verificada", "output", 1140, 200),
        n("blk", "Bloqueo", "respuesta fija + auditoría", "human", 300, 400),
    ],
    "edges": [
        e("e1", "in", "pre"),
        e("e2", "pre", "llm", "pasa (con veredicto)"),
        e("e3", "pre", "blk", "falla", "fallback"),
        e("e4", "llm", "post"),
        e("e5", "post", "out", "ok"),
        e("e6", "post", "llm", "regenera (1 vez)", "loop"),
    ],
}

PLANNER_FLOW = {
    "nodes": [
        n("obj", "Objetivo", "tarea compleja", "input", 40, 220),
        n("pl", "Planner", "plan JSON con dependencias", "plan", 300, 220, "planner"),
        n("ex1", "Executor 1", "historial_pedidos", "tool", 580, 60),
        n("ex2", "Executor 2", "consultar_stock", "tool", 580, 220),
        n("ex3", "Executor 3", "sugerir_sustitutos", "tool", 580, 380),
        n("ex4", "Executor 4", "crear_pedido_borrador", "tool", 580, 540),
        n("ver", "Verificador", "¿cada paso ok? ¿coherente?", "judge", 860, 220),
        n("out", "Resultado", "pedido borrador + resumen", "output", 1120, 220),
    ],
    "edges": [
        e("e1", "obj", "pl"),
        e("e2", "pl", "ex1"),
        e("e3", "pl", "ex2"),
        e("e4", "pl", "ex3"),
        e("e5", "ex1", "ex4", "depende"),
        e("e6", "ex2", "ex4"),
        e("e7", "ex3", "ex4"),
        e("e8", "ex4", "ver"),
        e("e9", "ver", "out", "ok"),
        e("e10", "ver", "pl", "replan", "loop"),
    ],
}

EXTRACTOR_FLOW = {
    "nodes": [
        n("usr", "Usuario", '"lo de siempre para el viernes"', "input", 40, 260),
        n("r1", "Corto plazo", "LIST sesion:{id}:historial", "memory", 300, 60),
        n("r2", "Episódica", "LIST cliente:{id}:episodios", "memory", 300, 200),
        n("r3", "Estructurada", "HASH cliente:{id}:perfil", "memory", 300, 340),
        n("llm", "LLM del agente", "instrucciones + memoria + mensaje", "llm", 600, 200, "extractor"),
        n("ans", "Respuesta", "personalizada", "output", 880, 200),
        n("ext", "Extractor", "¿qué hechos nuevos guardar?", "plan", 600, 420, "extractor"),
        n("w", "Escribir", "RPUSH / HSET / EXPIRE", "memory", 300, 500),
    ],
    "edges": [
        e("e1", "usr", "llm"),
        e("e2", "r1", "llm", "lee"),
        e("e3", "r2", "llm", "lee"),
        e("e4", "r3", "llm", "lee"),
        e("e5", "llm", "ans"),
        e("e6", "llm", "ext", "después", "loop"),
        e("e7", "ext", "w"),
        e("e8", "w", "r3", None, "loop"),
        e("e9", "w", "r1", None, "loop"),
    ],
}

JUDGE_FLOW = {
    "nodes": [
        n("resp", "Respuesta del agente", "+ contexto + tools", "input", 40, 100),
        n("rules", "Reglas del negocio", "prohibiciones · formato", "rule", 40, 240),
        n("ref", "Respuesta esperada", "opcional · dataset", "memory", 40, 380),
        n("judge", "Juez", "rúbrica 1–5 · otro modelo", "judge", 340, 240, "evaluador"),
        n("pub", "Publicar", "todo ≥ 4", "output", 640, 100),
        n("regen", "Regenerar", "feedback al agente", "llm", 640, 240),
        n("hum", "Humano", "cumplimiento ≤ 2", "human", 640, 380),
    ],
    "edges": [
        e("e1", "resp", "judge"),
        e("e2", "rules", "judge"),
        e("e3", "ref", "judge"),
        e("e4", "judge", "pub", "publicar"),
        e("e5", "judge", "regen", "regenerar", "loop"),
        e("e6", "judge", "hum", "humano", "fallback"),
    ],
}

BLOQUE_TOOLS = """- Llama a una herramienta solo cuando necesitas un dato o una acción que no tienes.
- Usa exactamente los nombres y tipos del schema. Evita argumentos adicionales.
- Puedes pedir varias herramientas de lectura en paralelo si son independientes.
- Si un resultado llega con "error", lee el mensaje, corrige los argumentos y reintenta una sola vez; si vuelve a fallar, explícaselo al usuario.
- Para herramientas marcadas "escritura": describe la acción y sus efectos, pide confirmación y espera un "sí" explícito antes de llamarla."""

REGLAS_NEGOCIO = (
    "1. Reembolsos: 3 a 5 días hábiles; prohibido prometer menos. 2. Prohibido mencionar datos de otros clientes. "
    "3. Precios solo desde herramientas. 4. Acciones de escritura solo tras confirmación explícita. "
    "5. Alcohol solo con edad verificada y en horario 09:00–21:00."
)

SPECIALIST_USE = {
    "usar_cuando": [
        "Hay un router delante",
        "El dominio tiene reglas y herramientas propias",
        "Quieres evaluar y versionar cada dominio por separado",
    ],
    "evitar_cuando": [
        "El dominio es tan amplio que necesita 10+ herramientas (divídelo)",
        "Las reglas del dominio son 100 % determinísticas (usa Híbrido)",
    ],
    "riesgos": [
        {
            "riesgo": "Responder fuera de su dominio",
            "guardrail": "Instrucción de devolver 'fuera_de_dominio' al router",
        },
        {"riesgo": "Prometer acciones que no puede ejecutar", "guardrail": "Solo promete lo que una tool confirmó"},
        {
            "riesgo": "Filtrar datos de otros clientes",
            "guardrail": "Tools filtradas por cliente_id en la app, nunca por el prompt",
        },
    ],
    "metricas": [
        "Precisión sobre 50 casos del dominio",
        "Faithfulness (respuesta vs evidencia de tools)",
        "Tasa de 'fuera_de_dominio' correcta",
    ],
}

SPECIALISTS: dict[str, dict[str, Any]] = {
    "analista": {
        "nombre": "Analista",
        "dominio": "Ventas, stock y tendencias por tienda y categoría. Excluye: pedidos individuales, cobros, políticas.",
        "tools": ["ventas_resumen", "consultar_stock", "buscar_producto"],
        "escritura": [],
        "tagline": "ventas, stock y tendencias",
        "ejemplo": "¿qué se vendió más esta semana en Las Condes?",
    },
    "politicas": {
        "nombre": "Políticas",
        "dominio": "Devoluciones, garantías, cambios de pedido, términos y protección de datos, siempre citando la política. Excluye: montos y reembolsos (financiero), stock (asistente).",
        "tools": ["buscar_politica", "estado_pedido"],
        "escritura": [],
        "tagline": "devoluciones, garantías y términos",
        "ejemplo": "¿hasta cuándo puedo devolver un producto?",
    },
    "financiero": {
        "nombre": "Financiero",
        "dominio": "Cobros, reembolsos, facturas y medios de pago. Excluye: estado de entrega, stock, políticas de devolución de productos.",
        "tools": ["consultar_cobros", "estado_pedido", "solicitar_reembolso"],
        "escritura": ["solicitar_reembolso"],
        "tagline": "cobros, reembolsos y facturas",
        "ejemplo": "me cobraron dos veces el pedido 8812",
    },
    "pedidos": {
        "nombre": "Pedidos",
        "dominio": 'Estado, cambios y creación de pedidos, incluido el pedido recurrente ("lo de siempre") reconstruido desde la memoria. Excluye: cobros y reembolsos.',
        "tools": [
            "pedido_actual",
            "historial_pedidos",
            "estado_pedido",
            "consultar_stock",
            "sugerir_sustitutos",
            "buscar_producto",
            "agregar_item",
            "crear_pedido_borrador",
        ],
        "escritura": ["agregar_item", "crear_pedido_borrador"],
        "tagline": "estado, cambios y pedido recurrente",
        "ejemplo": "lo de siempre para el viernes",
    },
}


def base_agent(id_: str, tipo: str, sec: dict, **kw) -> dict:
    now = datetime.now(UTC).isoformat()
    agent = {
        "id": id_,
        "tipo": tipo,
        "nombre": kw.pop("nombre"),
        "tagline": kw.pop("tagline"),
        "color": kw.pop("color"),
        "descripcion": kw.pop("descripcion"),
        "dominio": kw.pop("dominio", None),
        "tools": kw.pop("tools", []),
        "acciones_escritura": kw.pop("acciones_escritura", []),
        "prompt": {
            "system": sec["system"],
            "user": sec["user"],
            "variables": [dict(v) for v in sec["variables"]],
            "salida_esperada": sec["salida_esperada"],
            "salida_schema": kw.pop("salida_schema", None),
        },
        "limits": {
            "max_iters": 5,
            "max_tokens_out": 800,
            "timeout_s": 12,
            "temperature": 0.0,
            "modelo": None,
            **kw.pop("limits", {}),
        },
        "constantes": kw.pop("constantes", {}),
        "activo": True,
        "usar_cuando": kw.pop("usar_cuando", []),
        "evitar_cuando": kw.pop("evitar_cuando", []),
        "riesgos": kw.pop("riesgos", []),
        "metricas": kw.pop("metricas", []),
        "frameworks": kw.pop("frameworks", []),
        "flow": kw.pop("flow"),
        "version": 1,
        "actualizado": now,
    }
    assert not kw, kw
    for v in agent["prompt"]["variables"]:
        if v["nombre"] in agent["constantes"]:
            v["origen"] = "constante"
    return agent


def build() -> list[dict]:
    s = parse_txt()
    agents: list[dict] = []
    agents.append(
        base_agent(
            "supervisor",
            "supervisor",
            s[1],
            nombre="Supervisor",
            tagline="todos los agentes, un solo estado",
            color="ink",
            descripcion="Contenedor de los demás: orden de ejecución, límites globales, política ante fallos y qué agentes participan. Su prompt documenta el contrato; el runtime lo implementa en pipeline.py.",
            constantes={
                "router_id": "router",
                "especialistas": ["asistente", "analista", "politicas", "financiero", "pedidos", "ventas", "planner"],
                "evaluador_id": "evaluador",
                "extractor_id": "extractor",
                "reglas_pre": ["alcohol_requiere_edad", "cupo_credito", "horario_alcohol", "datos_sensibles_entrada"],
                "reglas_post": [
                    "precios_desde_api",
                    "formato_meta",
                    "sin_terceros",
                    "sin_promesas_de_plazo",
                    "longitud_maxima",
                ],
                "umbral_confianza": 0.6,
                "max_regeneraciones": 1,
                "nombre_app": "SuperApp",
                "mensaje_humano": "Gracias por escribirnos. Un ejecutivo revisará tu caso y te responderá por este mismo canal en menos de 2 horas hábiles. Tu número de ticket es {ticket_id}.",
                "bloque_tools": BLOQUE_TOOLS,
            },
            usar_cuando=[
                "Siempre, en la app del proyecto: es el contenedor de los demás",
                "Necesitas límites globales (costo, iteraciones) y trazabilidad por turno",
            ],
            evitar_cuando=["Prototipos de un solo agente: agrega el supervisor cuando aparezca el segundo"],
            riesgos=[
                {
                    "riesgo": "Estado inconsistente entre nodos",
                    "guardrail": "Un solo objeto de estado tipado (TypedDict/Pydantic) con checkpoints en Redis",
                },
                {
                    "riesgo": "Costo por turno fuera de control",
                    "guardrail": "Presupuesto global por turno y por día; corte limpio con mensaje",
                },
                {"riesgo": "Fallos silenciosos", "guardrail": "Cada nodo registra en Langfuse; errores → nodo humano"},
            ],
            metricas=[
                "Costo y latencia p95 por turno",
                "Tasa de turnos completados sin intervención",
                "Cobertura de trazas = 100 %",
            ],
            frameworks=["LangGraph", "OpenAI Agents SDK", "Pipeline propio (este repo)"],
            flow=SUPERVISOR_FLOW,
        )
    )
    agents.append(
        base_agent(
            "router",
            "router",
            s[2],
            nombre="Router",
            tagline="clasifica la intención y deriva al especialista",
            color="ink",
            descripcion="Primer nodo con LLM. Lee mensaje + historial + perfil + canal y decide el especialista con confianza. salida_schema = RouterOut. Nunca responde al usuario.",
            salida_schema=ROUTER_SCHEMA,
            limits={"max_tokens_out": 300},
            usar_cuando=[
                "La app cubre varios dominios (ventas, políticas, cobros, pedidos)",
                "Cada dominio necesita prompts y herramientas distintas",
                "Quieres medir precisión por especialista",
            ],
            evitar_cuando=[
                "Hay un solo dominio: un especialista basta",
                "La clasificación depende de datos que aún no tienes (p. ej. el estado del pedido)",
            ],
            riesgos=[
                {
                    "riesgo": "Clasificación ambigua entre dos especialistas",
                    "guardrail": "Umbral de confianza 0,6 y campo 'alternativo' para reintento",
                },
                {
                    "riesgo": "Mensajes con varias intenciones",
                    "guardrail": "Campo 'intenciones_secundarias' y división en sub-tareas",
                },
                {
                    "riesgo": "Prompt injection en el mensaje",
                    "guardrail": "El router solo clasifica; su salida es JSON validado, nunca texto libre",
                },
            ],
            metricas=[
                "Precisión de enrutamiento sobre 50 mensajes etiquetados",
                "Tasa de derivación a humano",
                "Latencia p95 < 800 ms",
            ],
            flow=ROUTER_FLOW,
        )
    )
    agents.append(
        base_agent(
            "asistente",
            "especialista",
            s[3],
            nombre="Asistente",
            tagline="piensa → actúa → observa, hasta tener la respuesta",
            color="teal",
            descripcion="Especialista de dominio amplio y solo lectura. Muestra el patrón ReAct puro: el runtime ejecuta el loop nativo de tool calling y el prompt pide un Thought breve antes de cada llamada para que la traza sea legible.",
            dominio="Consultas generales de catálogo, stock, sustitutos, alérgenos y políticas (solo lectura). Saludos y preguntas abiertas.",
            tools=[
                "buscar_producto",
                "ficha_producto",
                "consultar_stock",
                "sugerir_sustitutos",
                "pedido_actual",
                "buscar_politica",
            ],
            usar_cuando=[
                "Tareas abiertas que requieren 1 a 4 consultas a herramientas",
                "La secuencia exacta de pasos no se conoce de antemano",
                "Quieres una traza legible por humanos",
            ],
            evitar_cuando=[
                "Tareas de muchos pasos con dependencias (usa Planner–Executor)",
                "Acciones de escritura costosas sin revisión previa",
                "Latencia crítica: cada ciclo es una llamada al modelo",
            ],
            riesgos=[
                {
                    "riesgo": "Loop infinito o repetición de la misma tool",
                    "guardrail": "max_iters y detección de acción repetida",
                },
                {
                    "riesgo": "Alucinar una observación",
                    "guardrail": "La app escribe la observación; el modelo nunca la redacta",
                },
                {"riesgo": "Costo por tarea", "guardrail": "Presupuesto de tokens y timeout por tool"},
            ],
            metricas=["Tasa de éxito en 50 tareas", "Ciclos promedio por tarea", "Costo y latencia por tarea"],
            frameworks=["ReAct (Yao et al.)", "OpenAI tool calling"],
            flow=REACT_FLOW,
        )
    )
    for sid, cfg in SPECIALISTS.items():
        sec = dict(s[4])
        agents.append(
            base_agent(
                sid,
                "especialista",
                sec,
                nombre=cfg["nombre"],
                tagline=cfg["tagline"],
                color="teal",
                descripcion="Misma plantilla de especialista; cambian nombre, dominio, tools y acciones de escritura. El runtime rellena nombre_especialista, descripcion_dominio, tools_json y acciones_escritura desde la definición.",
                dominio=cfg["dominio"],
                tools=cfg["tools"],
                acciones_escritura=cfg["escritura"],
                constantes={"ejemplo": cfg["ejemplo"]},
                flow=specialist_flow(sid, cfg["nombre"], cfg["tools"], cfg["escritura"]),
                **SPECIALIST_USE,
            )
        )
    agents.append(
        base_agent(
            "ventas",
            "hibrido",
            s[5],
            nombre="Ventas",
            tagline="lo determinístico lo decide código; el lenguaje lo pone el modelo",
            color="amber",
            descripcion="Recibe el veredicto de las reglas PRE y los precios reales (precios_api, que el runtime completa con buscar_producto + consultar_stock antes del LLM) y solo redacta y propone alternativas. Las reglas POST verifican la salida.",
            dominio="Intenciones de compra con alcohol, línea de crédito, horario o límites de compra.",
            tools=["buscar_producto", "consultar_stock", "verificar_edad", "cupo_credito", "agregar_item"],
            acciones_escritura=["agregar_item"],
            constantes={"ejemplo": "quiero 3 botellas de vino y pagar con la línea de crédito"},
            usar_cuando=[
                "Hay normas legales o políticas no negociables",
                "El error tiene costo regulatorio o reputacional",
                "Quieres poder cambiar una regla sin tocar un prompt",
            ],
            evitar_cuando=[
                "Las reglas son difusas o cambian por contexto (déjalas en el prompt)",
                "No existe fuente de verdad para la regla (p. ej. edad sin verificación)",
            ],
            riesgos=[
                {
                    "riesgo": "El modelo 'convence' de saltarse la regla",
                    "guardrail": "La regla vive en código y corre fuera del LLM; el modelo solo recibe el resultado",
                },
                {
                    "riesgo": "Reglas desactualizadas",
                    "guardrail": "Reglas versionadas con fecha de vigencia y test por regla",
                },
                {
                    "riesgo": "Experiencia fría al bloquear",
                    "guardrail": "El modelo redacta el bloqueo con empatía y ofrece alternativa",
                },
            ],
            metricas=[
                "0 violaciones de reglas sobre 50 casos adversariales",
                "Tasa de bloqueos pre (sin LLM) = ahorro",
                "Precisión de precios en salida = 100 %",
            ],
            flow=VENTAS_FLOW,
        )
    )
    agents.append(
        base_agent(
            "planner",
            "planner",
            s[6],
            nombre="Planner",
            tagline="un agente planifica, varios ejecutan, uno verifica",
            color="violet",
            descripcion="Para objetivos largos (p. ej. 'prepara el pedido semanal'). salida_schema = PlanOut. El runtime ejecuta los pasos por niveles de dependencia y el verificador usa el bloque [VERIFICADOR] del prompt.",
            dominio="Objetivos largos de varios pasos: armar el pedido semanal o recurrente de un cliente B2B (restaurante) desde su historial y el stock.",
            tools=["historial_pedidos", "consultar_stock", "sugerir_sustitutos", "crear_pedido_borrador"],
            acciones_escritura=["crear_pedido_borrador"],
            salida_schema=PLAN_SCHEMA,
            constantes={"max_pasos": "8", "ejemplo": "prepara el pedido semanal del restaurante"},
            limits={"max_tokens_out": 1200, "timeout_s": 20},
            usar_cuando=[
                "Tareas largas con varios pasos y dependencias",
                "La trazabilidad y la auditoría importan",
                "Ejecutar es caro y conviene revisar el plan antes",
            ],
            evitar_cuando=[
                "Preguntas simples de 1–2 pasos (ReAct basta)",
                "El plan cambia con cada observación (usa ReAct o un loop supervisado)",
            ],
            riesgos=[
                {
                    "riesgo": "Plan incompleto o con pasos imposibles",
                    "guardrail": "Validar que cada tool exista y que el grafo de dependencias sea acíclico",
                },
                {
                    "riesgo": "Ejecutar pasos de escritura sin revisión",
                    "guardrail": "Pasos marcados requiere_confirmacion:true se pausan",
                },
                {"riesgo": "Replanificación infinita", "guardrail": "Máximo 2 replanificaciones por objetivo"},
            ],
            metricas=[
                "Tasa de planes completados sin replanificar",
                "Pasos ejecutados vs planificados",
                "Tiempo total por objetivo",
            ],
            frameworks=["Plan-and-Execute", "LLMCompiler"],
            flow=PLANNER_FLOW,
        )
    )
    agents.append(
        base_agent(
            "extractor",
            "memoria",
            s[7],
            nombre="Extractor de memoria",
            tagline="leer antes de razonar, escribir después de responder",
            color="violet",
            descripcion="Dos modos: hechos (después de cada turno; FactsOut) y episodio (al cerrar la sesión). La parte A del prompt se inyecta como bloque [MEMORIA DISPONIBLE] en el system de todo especialista.",
            salida_schema=FACTS_SCHEMA,
            limits={"max_tokens_out": 400},
            usar_cuando=[
                "El usuario vuelve y espera continuidad ('lo de siempre')",
                "Hay preferencias y restricciones que cambian la respuesta",
                "Las tareas largas deben sobrevivir reinicios",
            ],
            evitar_cuando=[
                "Interacciones anónimas de una sola vez",
                "Datos sensibles sin consentimiento ni política de borrado",
            ],
            riesgos=[
                {
                    "riesgo": "Guardar datos sensibles o secretos",
                    "guardrail": "Lista de categorías prohibidas en el extractor + revisión",
                },
                {
                    "riesgo": "Memoria contradictoria o vieja",
                    "guardrail": "Cada hecho con fecha y fuente; el más reciente gana; TTL en episodios",
                },
                {
                    "riesgo": "Contexto demasiado largo",
                    "guardrail": "Historial recortado a N turnos; episodios resumidos",
                },
            ],
            metricas=[
                "Tasa de aciertos de 'lo de siempre' (pedido recurrente correcto)",
                "Hechos guardados por sesión (debe ser bajo)",
                "Tokens de contexto por turno",
            ],
            flow=EXTRACTOR_FLOW,
        )
    )
    agents.append(
        base_agent(
            "evaluador",
            "evaluador",
            s[8],
            nombre="Evaluador",
            tagline="un segundo modelo califica y decide si se publica",
            color="red",
            descripcion="Corre en cada turno (gate) y en make eval (métricas). Usa OPENAI_JUDGE_MODEL, temperatura 0, salida_schema = JudgeOut. reglas_negocio es una constante editable.",
            salida_schema=JUDGE_SCHEMA,
            constantes={"reglas_negocio": REGLAS_NEGOCIO},
            limits={"max_tokens_out": 400},
            usar_cuando=[
                "El error cuesta dinero o reputación",
                "Quieres un gate automático antes de publicar",
                "Necesitas métricas comparables entre versiones de prompts",
            ],
            evitar_cuando=[
                "Latencia crítica y bajo riesgo (evalúa offline)",
                "No tienes rúbrica ni ejemplos: primero escríbelos",
            ],
            riesgos=[
                {
                    "riesgo": "El juez comparte sesgos con el agente",
                    "guardrail": "Modelo distinto, temperatura 0, rúbrica con ejemplos de cada nivel",
                },
                {"riesgo": "Juez demasiado permisivo", "guardrail": "Calibrar con 30 casos evaluados a mano cada mes"},
                {"riesgo": "Loop de regeneración", "guardrail": "Máximo 1 reintento; luego humano"},
            ],
            metricas=[
                "Acuerdo juez–humano (kappa) sobre muestra mensual",
                "Precisión, consistencia y cumplimiento promedio por versión",
                "Tasa de regeneraciones y derivaciones",
            ],
            frameworks=["LLM-as-judge", "G-Eval"],
            flow=JUDGE_FLOW,
        )
    )
    return agents


def main() -> None:
    agents = build()
    OUT.write_text(json.dumps(agents, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(agents)} agentes → {OUT}")


if __name__ == "__main__":
    main()
