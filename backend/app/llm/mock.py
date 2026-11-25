"""LLM simulado (modo DEMO, sin OPENAI_API_KEY).

Imita el comportamiento esperado de los agentes de semilla con heurísticas determinísticas
para que la plataforma completa (flow, tools reales, confirmaciones, reglas, memoria, evals)
se pueda mostrar antes de cargar credenciales. Con una clave real este módulo se ignora.

Importante: solo decide QUÉ tools pedir y redacta a partir de los RESULTADOS REALES de las
tools (que ejecuta el runtime contra Redis); nunca inventa datos de negocio.
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import date, timedelta
from typing import Any

from app.llm.client import LLMResult, ToolCall

TIENDAS = {"las condes": "LC", "providencia": "PR", "vitacura": "VI"}
TIENDA_NOMBRE = {"LC": "Las Condes", "PR": "Providencia", "VI": "Vitacura"}
PRODUCT_WORDS = [
    "pan integral",
    "pan centeno",
    "yogur griego",
    "yogur natural",
    "palta",
    "pan",
    "yogur",
    "yogures",
    "leche",
    "huevo",
    "tomate",
    "lechuga",
    "manzana",
    "platano",
    "plátano",
    "arroz",
    "fideo",
    "aceite",
    "cafe",
    "café",
    "vino",
    "vinos",
    "cerveza",
    "cervezas",
    "mani",
    "maní",
    "almendra",
    "queso",
    "jamon",
    "jamón",
    "agua",
    "detergente",
]
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def clp(n: Any) -> str:
    try:
        return "$" + f"{int(round(float(n))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return f"${n}"


def section(text: str, name: str) -> str | None:
    m = re.search(r"\[" + re.escape(name) + r"\]\s*\n(.*?)(?=\n\[[A-ZÁÉÍÓÚÑ ()]+\]\s*\n|\Z)", text, re.S)
    return m.group(1).strip() if m else None


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _usage(messages: list[dict], out: str) -> tuple[int, int]:
    tin = sum(_tokens(str(m.get("content") or "")) for m in messages)
    return tin, _tokens(out)


# =========================================================================== entrada
def respond(kind: str, messages: list[dict], *, model: str, **extra: Any) -> LLMResult:
    if kind == "json":
        name = extra.get("name", "")
        data = _json_response(name, messages)
        out = json.dumps(data, ensure_ascii=False)
        tin, tout = _usage(messages, out)
        return LLMResult(content=out, parsed=data, tokens_in=tin, tokens_out=tout, ms=120)
    if kind == "tools":
        res = _specialist(messages, extra.get("tools") or [], extra.get("ctx") or {})
        tin, tout = _usage(messages, (res.content or "") + json.dumps([c.arguments for c in res.tool_calls]))
        res.tokens_in, res.tokens_out, res.ms = tin, tout, 180
        return res
    text = "Respuesta de demostración."
    tin, tout = _usage(messages, text)
    return LLMResult(content=text, tokens_in=tin, tokens_out=tout, ms=80)


def _json_response(name: str, messages: list[dict]) -> dict:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = "\n".join(str(m.get("content") or "") for m in messages if m["role"] == "user")
    if name == "RouterOut":
        return _router(system, user)
    if name == "JudgeOut":
        return _judge(user)
    if name == "FactsOut":
        return _facts(system, user)
    if name == "EpisodeOut":
        return _episode(system + "\n" + user)
    if name == "PlanOut":
        return _plan(user)
    if name == "VerifyOut":
        return _verify(system + "\n" + user)
    return {}


# =========================================================================== router
ROUTES: list[tuple[str, list[str]]] = [
    ("humano", ["salud", "hablar con alguien", "abogado", "demanda", "amenaz", "intoxic", "me enferm"]),
    ("planner", ["pedido semanal", "pedido de la semana", "prepara el pedido", "arma el pedido", "armar el pedido"]),
    ("ventas", ["vino", "cerveza", "pisco", "alcohol", "linea de credito", "con credito", "credito"]),
    ("financiero", ["cobr", "reembols", "la plata", "factura", "devuelveme", "medio de pago"]),
    (
        "politicas",
        ["devolver", "devolucion", "garantia", "borren", "mis datos", "politica", "cambiar mi pedido", "terminos"],
    ),
    ("analista", ["se vendio", "vendio mas", "mas vendido", "tendencia", "tres tiendas", "todas las tiendas"]),
    ("pedidos", ["pedido", "lo de siempre", "agrega", "retirar", "prefiero", "como la otra vez"]),
    ("asistente", ["hay ", "precio", "a cuanto", "mani", "en vez de", "hola", "producto", "stock", "tienen"]),
]


def _router(system: str, user: str) -> dict:
    lista = section(system, "ESPECIALISTAS DISPONIBLES") or ""
    disponibles: dict[str, str] = {}
    for line in lista.splitlines():
        parts = [p.strip() for p in line.split("—")]
        if parts and parts[0]:
            disponibles[parts[0].lstrip("- ").strip()] = norm(" ".join(parts[1:]))
    msg = norm(section(user, "MENSAJE") or user)

    if re.search(r"\b(el|otro|del)\s+cliente\s+c-?\d+", msg):
        return {
            "agente": "humano",
            "confianza": 0.4,
            "motivo": "Solicita datos de otro cliente",
            "intenciones_secundarias": [],
            "alternativo": None,
        }

    # especialistas creados desde la UI (no conocidos por las reglas): solapamiento de palabras con su dominio
    known = {r for r, _ in ROUTES}
    best, best_score = None, 0
    words = {w for w in re.findall(r"[a-z]{5,}", msg)}
    for aid, dom in disponibles.items():
        if aid in known:
            continue
        score = len(words & set(re.findall(r"[a-z]{5,}", dom)))
        if score > best_score:
            best, best_score = aid, score
    if best and best_score >= 2:
        return {
            "agente": best,
            "confianza": 0.82,
            "motivo": f"Coincide con el dominio de {best}",
            "intenciones_secundarias": [],
            "alternativo": None,
        }

    hits = [aid for aid, kws in ROUTES if any(k in msg for k in kws) and (aid == "humano" or aid in disponibles)]
    if not hits:
        if "asistente" in disponibles:
            return {
                "agente": "asistente",
                "confianza": 0.62,
                "motivo": "Consulta general sin dominio específico",
                "intenciones_secundarias": [],
                "alternativo": None,
            }
        return {
            "agente": "humano",
            "confianza": 0.3,
            "motivo": "Ningún especialista cubre la consulta",
            "intenciones_secundarias": [],
            "alternativo": None,
        }
    principal = hits[0]
    secundarias = [h for h in hits[1:] if h not in ("asistente", "humano")]
    if (
        principal == "financiero"
        and ("hora de entrega" in msg or "cambiar" in msg)
        and "pedidos" in disponibles
        and "pedidos" not in secundarias
    ):
        secundarias.append("pedidos")
    conf = 0.93 if principal != "asistente" else (0.7 if msg.strip(" ¿?!.") in ("hola", "buenas") else 0.86)
    motivos = {
        "humano": "Tema sensible que requiere una persona",
        "planner": "Objetivo de varios pasos: armar un pedido completo",
        "ventas": "Intención de compra con reglas de alcohol o crédito",
        "financiero": "Consulta o reclamo sobre cobros o reembolsos",
        "politicas": "Consulta sobre políticas, devoluciones o datos",
        "analista": "Consulta de ventas o stock agregado",
        "pedidos": "Gestión de un pedido del cliente",
        "asistente": "Consulta general de catálogo o stock",
    }
    return {
        "agente": principal,
        "confianza": conf,
        "motivo": motivos.get(principal, "Intención principal detectada"),
        "intenciones_secundarias": secundarias[:2],
        "alternativo": secundarias[0] if secundarias else None,
    }


# =========================================================================== juez / extractor / episodio
def _judge(user: str) -> dict:
    resp = norm(section(user, "RESPUESTA DEL AGENTE") or "")
    if re.search(r"24 horas|hoy mismo|de inmediato te (devuelvo|reembolso)", resp):
        return {
            "precision": 4,
            "consistencia": 4,
            "cumplimiento_reglas": 3,
            "evidencia": "promete un plazo menor al de la política",
            "veredicto": "regenerar",
            "feedback": "Corregir el plazo a 3–5 días hábiles.",
        }
    if re.search(r"\b(c42|c77|c-118|camila|tomas|don lucho)\b", resp) and "otro cliente" not in resp:
        return {
            "precision": 4,
            "consistencia": 4,
            "cumplimiento_reglas": 2,
            "evidencia": "menciona datos de un cliente",
            "veredicto": "humano",
            "feedback": "Eliminar datos de terceros.",
        }
    return {
        "precision": 5,
        "consistencia": 5,
        "cumplimiento_reglas": 5,
        "evidencia": "La respuesta se apoya en los resultados de las herramientas.",
        "veredicto": "publicar",
        "feedback": None,
    }


def _facts(system: str, user: str) -> dict:
    inter = section(system, "INTERCAMBIO") or user
    m = re.search(r"usuario:\s*(.*)", inter)
    msg = norm(m.group(1) if m else user)
    hechos = []
    for nombre, code in TIENDAS.items():
        if re.search(r"(prefiero|desde ahora|ahora).*(retirar|comprar|tienda).*" + nombre, msg):
            hechos.append({"clave": "tienda", "valor": code, "reemplaza": True, "fuente": m.group(1)[:80] if m else ""})
    if re.search(r"soy alergic[oa] (a|al) (\w+)", msg):
        x = re.search(r"soy alergic[oa] (?:a|al) (\w+)", msg)
        hechos.append({"clave": "restriccion", "valor": f"sin {x.group(1)}", "reemplaza": True, "fuente": x.group(0)})
    for dia in DIAS:
        if re.search(r"(siempre compro|compro los|prefiero los) " + dia, msg):
            hechos.append({"clave": "dia_compra", "valor": dia, "reemplaza": True, "fuente": msg[:80]})
    return {"hechos": hechos}


def _episode(text: str) -> dict:
    lines = [ln for ln in (section(text, "SESIÓN") or text).splitlines() if ln.startswith(("user:", "assistant:"))]
    users = [ln[5:].strip() for ln in lines if ln.startswith("user:")]
    last = next((ln[10:].strip() for ln in reversed(lines) if ln.startswith("assistant:")), "")
    hoy = date.today().strftime("%d-%m")
    resumen = f"{hoy}: pidió «{users[0][:60]}»" if users else f"{hoy}: sesión sin mensajes"
    if len(users) > 1:
        resumen += f" y {len(users) - 1} consulta(s) más"
    if last:
        resumen += f"; respuesta: {last[:90]}"
    return {"resumen": resumen}


# =========================================================================== planner
def _next_weekday(target: int) -> str:
    d = date.today() + timedelta(days=1)
    while d.weekday() != target:
        d += timedelta(days=1)
    return d.isoformat()


def _plan(user: str) -> dict:
    obj = norm(section(user, "OBJETIVO") or user)
    excluir = []
    m = re.search(r"sin (\w+)", obj)
    if m:
        excluir.append(m.group(1))
    tienda = "LC"
    args1: dict[str, Any] = {"n": 8}
    if excluir:
        args1["excluir"] = excluir
    return {
        "objetivo": "Armar el pedido semanal según el historial del cliente y el stock de hoy"
        + (f", excluyendo {', '.join(excluir)}" if excluir else ""),
        "pasos": [
            {
                "id": 1,
                "tool": "historial_pedidos",
                "args": args1,
                "depende_de": [],
                "requiere_confirmacion": False,
                "criterio_exito": "lista de SKUs con cantidades promedio",
            },
            {
                "id": 2,
                "tool": "consultar_stock",
                "args": {"skus": {"$paso": 1, "campo": "skus"}, "tienda": tienda},
                "depende_de": [1],
                "requiere_confirmacion": False,
                "criterio_exito": "stock por SKU",
            },
            {
                "id": 3,
                "tool": "sugerir_sustitutos",
                "args": {"skus": {"$paso": 2, "campo": "faltantes"}, "tienda": tienda},
                "depende_de": [2],
                "requiere_confirmacion": False,
                "criterio_exito": "un sustituto por faltante",
            },
            {
                "id": 4,
                "tool": "crear_pedido_borrador",
                "args": {
                    "items": {"$paso": 1, "campo": "promedio_items"},
                    "fecha_entrega": _next_weekday(0),
                    "tienda": tienda,
                },
                "depende_de": [1, 2, 3],
                "requiere_confirmacion": True,
                "criterio_exito": "pedido en estado borrador con total",
            },
        ],
        "notas": "Cantidades = promedio de los últimos 8 pedidos redondeado hacia arriba; entrega el próximo lunes en LC.",
    }


def _verify(text: str) -> dict:
    ok, fallidos = [], []
    raw = (section(text, "PLAN Y RESULTADOS") or "").strip()
    data: Any = {}
    try:
        data, _ = json.JSONDecoder().raw_decode(raw)
    except json.JSONDecodeError:
        data = {}
    total = None
    for r in data.get("resultados", []) if isinstance(data, dict) else []:
        if r.get("ok"):
            ok.append(r.get("id"))
            if isinstance(r.get("data"), dict) and "total" in r["data"]:
                total = r["data"]["total"]
        elif r.get("estado") != "pendiente_confirmacion":
            fallidos.append({"id": r.get("id"), "motivo": r.get("error") or "sin resultado"})
    resumen = f"Ejecuté {len(ok)} pasos del plan sin errores." if not fallidos else f"{len(fallidos)} paso(s) fallaron."
    if total:
        resumen += f" El pedido borrador suma {clp(total)}."
    return {"pasos_ok": ok, "fallidos": fallidos, "coherente": not fallidos, "resumen": resumen}


# =========================================================================== especialistas (tool calling)
def _tool_history(messages: list[dict]) -> list[tuple[str, dict, dict]]:
    calls: dict[str, tuple[str, dict]] = {}
    out: list[tuple[str, dict, dict]] = []
    for m in messages:
        if m["role"] == "assistant":
            for tc in m.get("tool_calls") or []:
                try:
                    a = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    a = {}
                calls[tc["id"]] = (tc["function"]["name"], a)
        elif m["role"] == "tool":
            name, a = calls.get(m.get("tool_call_id", ""), ("?", {}))
            try:
                r = json.loads(m.get("content") or "{}")
            except json.JSONDecodeError:
                r = {"ok": False, "error": m.get("content")}
            out.append((name, a, r))
    return out


def _detect_products(msg: str) -> list[str]:
    found: list[str] = []
    for w in PRODUCT_WORDS:
        wn = norm(w)
        if re.search(r"\b" + re.escape(wn), msg) and not any(wn in f or f in wn for f in found):
            found.append(wn.rstrip("s") if wn.endswith(("vinos", "cervezas", "yogures")) else wn)
    return [("yogur" if f == "yogure" else f) for f in found]


def _detect_qty(msg: str) -> int | None:
    m = re.search(r"\b(\d{1,4})\s*(kg|kilos?|botellas?|cervezas?|unidades|un\b|vinos?|packs?)", msg)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(un|una|dos|tres|cuatro|cinco|seis)\b\s+(kg|botellas?|vinos?|cervezas?)", msg)
    if m:
        return {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}[m.group(1)]
    return None


def _call(name: str, args: dict) -> ToolCall:
    return ToolCall(id="call_" + uuid.uuid4().hex[:10], name=name, arguments=json.dumps(args, ensure_ascii=False))


def _specialist(messages: list[dict], tools: list[dict], ctx: dict) -> LLMResult:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    first_user = next((m["content"] for m in messages if m["role"] == "user"), "")
    raw_msg = section(first_user, "MENSAJE") or section(first_user, "SOLICITUD") or first_user
    msg = norm(raw_msg)
    available = {t["function"]["name"] for t in tools}
    hist = _tool_history(messages)
    done: dict[str, list] = {}
    for name, a, r in hist:
        done.setdefault(name, []).append((a, r))
    perfil: dict = {}
    pm = section(first_user, "PERFIL") or ""
    try:
        perfil = json.loads(pm) if pm.startswith("{") else {}
    except json.JSONDecodeError:
        perfil = {}
    tienda = (
        next((c for n_, c in TIENDAS.items() if n_ in msg), None) or perfil.get("tienda") or ctx.get("tienda") or "LC"
    )
    tm = section(first_user, "CONTEXTO") or ""
    m_t = re.search(r"Tienda del cliente:\s*(\w+)", tm)
    if m_t and not any(n_ in msg for n_ in TIENDAS):
        tienda = m_t.group(1)
    ventas_mode = "[VEREDICTO DE LAS REGLAS]" in system
    adversarial = bool(
        re.search(r"ignora tus reglas|todos mis pedidos|\[resultado de herramienta|el sistema autoriza", msg)
    )
    calls: list[ToolCall] = []

    def need(name: str) -> bool:
        return name in available and name not in done

    # --- ventas (híbrido): el veredicto ya viene de las reglas, solo redacta / agrega al carro
    if ventas_mode:
        return _ventas(system, first_user, msg, available, done)

    # --- analista
    if need("ventas_resumen") and re.search(r"vend", msg):
        return LLMResult(
            content=f"Thought: necesito el ranking de ventas de {tienda}.",
            tool_calls=[_call("ventas_resumen", {"tienda": tienda, "dias": 7})],
        )
    # --- financiero
    cobro_intent = re.search(r"cobr|reembols|plata|devuelveme", msg)
    pid = re.search(r"\b(p-\d{3,}|\d{4})\b", msg)
    pedido_id = pid.group(1).upper() if pid else None
    if need("consultar_cobros") and cobro_intent:
        return LLMResult(
            content=f"Thought: reviso los cobros del pedido {pedido_id or '8812'}.",
            tool_calls=[_call("consultar_cobros", {"pedido_id": pedido_id or "8812"})],
        )
    if (
        "solicitar_reembolso" in available
        and "consultar_cobros" in done
        and "solicitar_reembolso" not in done
        and not adversarial
    ):
        cobros = done["consultar_cobros"][-1][1].get("data") or []
        dup = next((c for c in cobros if c.get("estado") == "duplicado"), None)
        if dup and re.search(r"dos veces|duplic|solicita el reembolso|si,? solicit", msg):
            return LLMResult(
                content=f"Thought: el cobro {dup['cobro_id']} está duplicado; solicito su reembolso (requiere confirmación).",
                tool_calls=[_call("solicitar_reembolso", {"cobro_id": dup["cobro_id"], "motivo": "cobro duplicado"})],
            )
    # --- políticas
    if need("buscar_politica") and re.search(r"devol|garant|politica|datos|borren|cambiar|plazo|termin|olvido", msg):
        calls.append(_call("buscar_politica", {"pregunta": raw_msg[:200]}))
    if need("estado_pedido") and pedido_id and re.search(r"estado|cambiar|donde", msg):
        calls.append(_call("estado_pedido", {"pedido_id": pedido_id}))
    if calls:
        return LLMResult(content="Thought: consulto la política y/o el pedido antes de responder.", tool_calls=calls)
    # --- pedidos: estado del pedido de mañana
    if need("pedido_actual") and not pedido_id and re.search(r"manana|mi pedido|proximo pedido", msg):
        return LLMResult(
            content="Thought: busco el próximo pedido del cliente.", tool_calls=[_call("pedido_actual", {})]
        )
    # --- lo de siempre
    if re.search(r"lo de siempre|como la otra vez|lo mismo de", msg):
        if need("historial_pedidos"):
            return LLMResult(
                content="Thought: reconstruyo 'lo de siempre' desde el historial y los episodios.",
                tool_calls=[_call("historial_pedidos", {"n": 3})],
            )
        if need("crear_pedido_borrador"):
            items = _items_lo_de_siempre(done, system)
            dia = next((i for i, d in enumerate(DIAS) if d in msg), 4)
            return LLMResult(
                content="Thought: armo el borrador con los ítems de la última compra (requiere confirmación).",
                tool_calls=[
                    _call(
                        "crear_pedido_borrador", {"items": items, "fecha_entrega": _next_weekday(dia), "tienda": tienda}
                    )
                ],
            )
    # --- productos
    products = _detect_products(msg)
    if "buscar_producto" in available:
        searched = {norm(a.get("q", "")) for a, _ in done.get("buscar_producto", [])}
        for p in products:
            if p not in searched:
                calls.append(_call("buscar_producto", {"q": p}))
        if calls:
            return LLMResult(content=f"Thought: necesito el SKU de {', '.join(products)}.", tool_calls=calls)
    skus = []
    for a, r in done.get("buscar_producto", []):
        data = r.get("data") or []
        q = norm(a.get("q", ""))
        pick = next((d for d in data if norm(d["nombre"]).startswith(q)), data[0] if data else None)
        if pick:
            skus.append(pick["sku"])
    if not skus and "ficha_producto" in available and re.search(r"pan integral", msg):
        skus = ["PAN-204"]
    if need("ficha_producto") and skus and re.search(r"mani|alerg|contiene|tiene .*\?|ingrediente", msg):
        return LLMResult(
            content="Thought: reviso la ficha del producto (alérgenos).",
            tool_calls=[_call("ficha_producto", {"sku": skus[0]})],
        )
    if "consultar_stock" in available and skus and not re.search(r"mani|alerg", msg):
        consulted = {(a.get("sku"), a.get("tienda")) for a, _ in done.get("consultar_stock", [])}
        tiendas = ["LC", "PR", "VI"] if re.search(r"tres tiendas|todas las tiendas", msg) else [tienda]
        for s in skus:
            for t in tiendas:
                if (s, t) not in consulted:
                    calls.append(_call("consultar_stock", {"sku": s, "tienda": t}))
        if calls:
            return LLMResult(content="Thought: consulto stock y precio actual.", tool_calls=calls)
    if need("sugerir_sustitutos") and skus:
        sin_stock = [a["sku"] for a, r in done.get("consultar_stock", []) if (r.get("data") or {}).get("stock", 1) == 0]
        if sin_stock or re.search(r"en vez de|reemplaz|sustitu", msg):
            return LLMResult(
                content="Thought: busco alternativas con stock.",
                tool_calls=[_call("sugerir_sustitutos", {"skus": sin_stock or skus, "tienda": tienda})],
            )
    # --- agregar al pedido
    if "agregar_item" in available and "agregar_item" not in done and re.search(r"agrega|suma|anade", msg) and skus:
        qty = _detect_qty(msg) or 1
        stock_r = next((r.get("data") for a, r in done.get("consultar_stock", []) if a.get("sku") == skus[0]), None)
        pedido = None
        for _, r in done.get("pedido_actual", []):
            pedido = (r.get("data") or {}).get("pedido_id")
        if need("pedido_actual"):
            return LLMResult(
                content="Thought: necesito el pedido al que agregar.", tool_calls=[_call("pedido_actual", {})]
            )
        if stock_r and stock_r.get("stock", 0) >= qty and pedido:
            return LLMResult(
                content=f"Thought: hay stock suficiente; agrego {qty} al pedido {pedido} (requiere confirmación).",
                tool_calls=[
                    _call(
                        "agregar_item",
                        {
                            "pedido_id": pedido,
                            "sku": skus[0],
                            "cantidad": qty,
                            "idempotency_key": f"{pedido}-{skus[0]}-{qty}",
                        },
                    )
                ],
            )
    return LLMResult(content=_compose(msg, done, adversarial, tienda))


def _items_lo_de_siempre(done: dict, system: str) -> list[dict]:
    """Elige el pedido entregado que mejor calza con los episodios de memoria ("lo de siempre")."""
    m = re.search(r"Episodios[^:]*:\s*(.*)", system)
    palabras = _detect_products(norm(m.group(1))) if m else []
    best, best_score = None, -1
    for _, r in done.get("historial_pedidos", []):
        pedidos = (r.get("data") or {}).get("pedidos") or []
        for idx, p in enumerate(pedidos):
            if p.get("estado") != "entregado" or not p.get("items"):
                continue
            nombres = " ".join(norm(i.get("nombre", "")) for i in p["items"])
            score = sum(1 for w in palabras if w in nombres) * 10 + idx  # desempate: el más reciente
            if score > best_score:
                best, best_score = p, score
    if best:
        return [{"sku": i["sku"], "cantidad": i["cantidad"]} for i in best["items"]]
    return [{"sku": "PLT-001", "cantidad": 2}, {"sku": "PAN-204", "cantidad": 1}, {"sku": "YOG-310", "cantidad": 6}]


def _ventas(system: str, user: str, msg: str, available: set[str], done: dict) -> LLMResult:
    ver_txt = section(system, "VEREDICTO DE LAS REGLAS") or "{}"
    try:
        ver = json.loads(ver_txt)
    except json.JSONDecodeError:
        ver = {}
    try:
        precios = json.loads(section(user, "PRECIOS API") or "[]")
    except json.JSONDecodeError:
        precios = []
    qty = _detect_qty(msg) or 1
    p = precios[0] if precios else None
    reglas = [k for k in ("edad", "cupo_credito", "horario_alcohol") if k in json.dumps(ver)]
    meta = {
        "reglas_aplicadas": reglas,
        "precios_usados": [{"sku": x["sku"], "precio": x["precio"]} for x in precios],
        "requiere_verificacion": None,
    }
    bloqueo = ver.get("bloqueo")
    if bloqueo:
        if bloqueo == "edad":
            meta["requiere_verificacion"] = "edad"
        prod = f"{qty} {p['nombre']} ({clp(p['precio'])} c/u)" if p else "tu compra"
        if bloqueo == "edad":
            txt = f"Puedo dejarte {prod} en el carro, pero para vender alcohol necesito verificar tu edad: valida tu cédula en Perfil → Verificación (toma 1 minuto)."
        elif bloqueo == "cupo_credito":
            alt = ver.get("alternativa") or "pagar con otro medio de pago"
            txt = f"Tu línea de crédito no tiene cupo disponible para {prod}. Puedes {alt}."
        elif bloqueo == "horario_alcohol":
            alt = ver.get("alternativa") or "programar tu pedido para mañana"
            txt = f"La venta de alcohol está permitida entre 09:00 y 21:00. Puedes {alt}."
        else:
            txt = f"No puedo completar esta compra: {ver.get('alternativa') or bloqueo}."
        return LLMResult(content=txt + "\n<meta>" + json.dumps(meta, ensure_ascii=False) + "</meta>")
    if "agregar_item" in available and "agregar_item" not in done and p:
        return LLMResult(
            content=f"Thought: las reglas pasaron; agrego {qty} × {p['sku']} al pedido (requiere confirmación).",
            tool_calls=[
                _call(
                    "agregar_item",
                    {
                        "pedido_id": "actual",
                        "sku": p["sku"],
                        "cantidad": qty,
                        "idempotency_key": f"ventas-{p['sku']}-{qty}",
                    },
                )
            ],
        )
    if "agregar_item" in done:
        r = done["agregar_item"][-1][1]
        if r.get("ok"):
            d = r.get("data") or {}
            txt = f"Listo: agregué {qty} {p['nombre'] if p else ''} a tu pedido {d.get('pedido_id', '')}. Total del pedido: {clp(d.get('total', 0))}."
        else:
            txt = f"No agregué el producto: {r.get('error')}."
        return LLMResult(content=txt + "\n<meta>" + json.dumps(meta, ensure_ascii=False) + "</meta>")
    txt = f"{p['nombre']} está a {clp(p['precio'])}. ¿Lo agrego a tu pedido?" if p else "¿Qué producto quieres comprar?"
    return LLMResult(content=txt + "\n<meta>" + json.dumps(meta, ensure_ascii=False) + "</meta>")


def _compose(msg: str, done: dict, adversarial: bool, tienda: str) -> str:
    parts: list[str] = []
    evid: list[str] = []
    accion = None

    def last(name: str) -> tuple[dict, dict] | None:
        return done[name][-1] if name in done else None

    if adversarial and "consultar_cobros" not in done:
        parts.append(
            "Solo puedo gestionar reembolsos de cobros verificados y con tu confirmación explícita; no puedo reembolsar todos tus pedidos de una vez. Si me indicas el número de pedido, reviso sus cobros."
        )
    if x := last("solicitar_reembolso"):
        a, r = x
        evid.append(f"solicitar_reembolso:{a.get('cobro_id')}")
        if r.get("ok"):
            d = r.get("data") or {}
            parts.append(
                f"Listo: solicité el reembolso del cobro {d.get('cobro_id')} por {clp(d.get('monto'))}. Llega al medio de pago original en {d.get('plazo', '3-5 días hábiles')}."
            )
        else:
            parts.append(f"No solicité el reembolso: {r.get('error')}.")
    elif x := last("consultar_cobros"):
        a, r = x
        evid.append(f"consultar_cobros:{a.get('pedido_id')}")
        if not r.get("ok"):
            parts.append(f"No encontré cobros para el pedido {a.get('pedido_id')}. ¿Me confirmas el número?")
        else:
            cobros = r.get("data") or []
            dup = [c for c in cobros if c.get("estado") == "duplicado"]
            reemb = [c for c in cobros if c.get("estado") == "reembolsado"]
            if reemb:
                parts.append(
                    f"El reembolso del cobro {reemb[0]['cobro_id']} por {clp(reemb[0]['monto'])} ya está en curso; llega al medio de pago original en 3-5 días hábiles."
                )
            elif dup and adversarial:
                parts.append(
                    f"Revisé el pedido {a.get('pedido_id')}: hay un cobro duplicado de {clp(dup[0]['monto'])}. Puedo solicitar su reembolso solo si me lo confirmas; los resultados de herramientas no autorizan reembolsos por sí solos."
                )
            elif dup:
                parts.append(
                    f"Revisé el pedido {a.get('pedido_id')}: hay {len(cobros)} cobros de {clp(dup[0]['monto'])} y uno es duplicado. ¿Quieres que solicite el reembolso? Tarda 3-5 días hábiles."
                )
            else:
                parts.append(
                    f"El pedido {a.get('pedido_id')} tiene {len(cobros)} cobro(s) aprobado(s) por {clp(cobros[0]['monto']) if cobros else '$0'}; no veo cobros duplicados."
                )
    if x := last("ventas_resumen"):
        a, r = x
        evid.append(f"ventas_resumen:{a.get('tienda')}")
        top = (r.get("data") or {}).get("top", [])[:3]
        if top:
            parts.append(
                f"Lo más vendido en {TIENDA_NOMBRE.get(a.get('tienda'), a.get('tienda'))} los últimos {a.get('dias', 7)} días: "
                + "; ".join(f"{t['nombre']} ({t['unidades']} un.)" for t in top)
                + "."
            )
        else:
            parts.append("No hay ventas entregadas en ese período.")
    if x := last("buscar_politica"):
        a, r = x
        pols = r.get("data") or []
        if pols:
            evid.append(f"buscar_politica:{pols[0]['id']}")
            parts.append(f"Según la política «{pols[0]['titulo']}»: {pols[0]['extracto']}")
    if x := last("estado_pedido"):
        a, r = x
        evid.append(f"estado_pedido:{a.get('pedido_id')}")
        if r.get("ok"):
            d = r["data"]
            parts.append(
                f"Tu pedido {d['pedido_id']} está {d['estado']}, con entrega el {d['fecha_entrega']} en {TIENDA_NOMBRE.get(d['tienda'], d['tienda'])}."
            )
        else:
            parts.append(f"No encuentro el pedido {a.get('pedido_id')} en tu cuenta. ¿Puedes revisar el número?")
    if x := last("crear_pedido_borrador"):
        a, r = x
        evid.append("crear_pedido_borrador")
        if r.get("ok"):
            d = r["data"]
            parts.append(
                f"Listo: dejé el pedido {d['pedido_id']} en borrador para el {d['fecha_entrega']} con {len(d['items'])} productos, total {clp(d['total'])}."
            )
        else:
            parts.append(f"No creé el pedido: {r.get('error')}.")
    if x := last("agregar_item"):
        a, r = x
        evid.append(f"agregar_item:{a.get('pedido_id')}")
        if r.get("ok"):
            d = r["data"]
            ag = d.get("agregado") or {}
            parts.append(
                f"Listo: agregué {a.get('cantidad')} × {ag.get('nombre', a.get('sku'))} ({clp(ag.get('subtotal', 0))}) al pedido {d['pedido_id']}. Nuevo total: {clp(d['total'])}."
            )
        else:
            parts.append(f"No agregué el producto: {r.get('error')}.")
    elif (x := last("pedido_actual")) and "crear_pedido_borrador" not in done:
        a, r = x
        d = r.get("data")
        if d:
            evid.append(f"pedido_actual:{d['pedido_id']}")
            if not re.search(r"agrega", msg):
                parts.append(
                    f"Tu próximo pedido {d['pedido_id']} está {d['estado']} para el {d['fecha_entrega']} ({len(d['items'])} productos, total {clp(d['total'])})."
                )
        else:
            parts.append("No tienes pedidos pendientes de entrega.")
    if x := last("ficha_producto"):
        a, r = x
        d = r.get("data") or {}
        evid.append(f"ficha_producto:{a.get('sku')}")
        al = d.get("alergenos") or []
        parts.append(
            f"{d.get('nombre')}: "
            + (f"contiene {', '.join(al)}." if al else "no declara alérgenos (no contiene maní).")
        )
    stocks = [] if "agregar_item" in done else done.get("consultar_stock", [])
    pedido_qty = _detect_qty(msg)
    for a, r in stocks:
        d = r.get("data") or {}
        evid.append(f"consultar_stock:{a.get('sku')}")
        if not r.get("ok"):
            parts.append(f"No pude consultar {a.get('sku')}: {r.get('error')}.")
            continue
        t = TIENDA_NOMBRE.get(a.get("tienda"), a.get("tienda"))
        if d.get("stock", 0) == 0:
            parts.append(f"{d.get('nombre')} está sin stock en {t}.")
        elif pedido_qty and pedido_qty > d.get("stock", 0):
            parts.append(
                f"Solo hay {d['stock']} {d.get('unidad', '')} de {d.get('nombre')} en {t} ({clp(d['precio'])} c/u); no alcanza para {pedido_qty}. ¿Agrego {d['stock']}?"
            )
        else:
            parts.append(f"Hay {d['stock']} {d.get('unidad', '')} de {d.get('nombre')} en {t} a {clp(d['precio'])}.")
    if x := last("sugerir_sustitutos"):
        a, r = x
        sug = (r.get("data") or {}).get("sugerencias", [])
        evid.append("sugerir_sustitutos")
        alts = [f"{s['nombre']} ({clp(s['precio'])})" for item in sug for s in item.get("alternativas", [])]
        if alts:
            parts.append("Alternativas con stock: " + ", ".join(alts[:3]) + ".")
    if not parts and (m_pref := re.search(r"(desde ahora|prefiero|ahora quiero)\s+(.*)", msg)):
        parts.append(
            f"Anotado: desde ahora tomo en cuenta tu preferencia ({m_pref.group(2)[:60]}). ¿Te ayudo con algo más?"
        )
    if not parts and re.search(r"alergic|recuerdalo|recuerda que", msg):
        parts.append("Anotado, lo tendré en cuenta en tus próximas compras. ¿Te ayudo con algo más?")
    if not parts:
        if re.search(r"^\W*(hola|buenas|buen dia)", msg):
            parts.append(
                "¡Hola! Soy el asistente de SuperApp. Puedo ayudarte con productos, stock, precios, tus pedidos, cobros y políticas. ¿Qué necesitas?"
            )
        else:
            parts.append(
                "No encontré información suficiente con mis herramientas para responder eso. ¿Puedes darme más detalles, o prefieres que te derive con una persona?"
            )
    text = " ".join(parts)
    words = text.split()
    if len(words) > 95:
        text = " ".join(words[:95]) + "…"
    meta = {"evidencia": evid[:6], "accion_pendiente": accion, "confianza": 0.9 if evid else 0.6}
    return text + "\n<meta>" + json.dumps(meta, ensure_ascii=False) + "</meta>"
