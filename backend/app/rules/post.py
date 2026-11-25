"""Reglas POST: verifican la salida del especialista (respuesta + bloque <meta>)."""

from __future__ import annotations

import json
import re
from typing import Any

from app.rules.base import RuleResult, rule
from app.tools import data

MONTO = re.compile(r"\$\s?(\d{1,3}(?:\.\d{3})+|\d+)")
META = re.compile(r"<meta>(.*?)</meta>", re.S)
CLAVES_MONTO = {"precio", "monto", "total", "subtotal", "cupo_disponible", "disponible"}


def parse_monto(s: str) -> int:
    return int(s.replace(".", ""))


def _montos_en(obj: Any, out: set[int]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in CLAVES_MONTO and isinstance(v, int | float):
                out.add(int(v))
            else:
                _montos_en(v, out)
    elif isinstance(obj, list):
        for x in obj:
            _montos_en(x, out)
    elif isinstance(obj, str):
        try:
            _montos_en(json.loads(obj), out)
        except (json.JSONDecodeError, TypeError):
            pass


def montos_permitidos(state: Any) -> set[int]:
    base: set[int] = set(int(v) for v in state.precios_vistos.values())
    for t in state.tools_llamadas:
        _montos_en(t.get("result"), base)
    for p in state.precios_api or []:
        if isinstance(p, dict) and "precio" in p:
            base.add(int(p["precio"]))
    derivados = set(base)
    for p in base:
        for k in range(1, 101):
            derivados.add(p * k)
    lista = sorted(base)
    for i, a in enumerate(lista):
        for b in lista[i:]:
            derivados.add(a + b)
    return derivados


def texto_sin_meta(texto: str) -> str:
    return META.sub("", texto or "").strip()


@rule(
    "precios_desde_api",
    "post",
    "Todo monto $N de la respuesta debe venir de una herramienta (precios, montos, totales) o de un cálculo directo desde ellos.",
)
async def precios_desde_api(state: Any) -> RuleResult:
    montos = [parse_monto(m) for m in MONTO.findall(texto_sin_meta(state.respuesta or ""))]
    if not montos:
        return RuleResult("precios_desde_api", True, "la respuesta no menciona montos")
    permitidos = montos_permitidos(state)
    malos = [m for m in montos if m not in permitidos]
    if malos:
        fmt = ", ".join("$" + f"{m:,}".replace(",", ".") for m in malos)
        return RuleResult(
            "precios_desde_api",
            False,
            f"montos sin respaldo en herramientas: {fmt}. Usa solo precios y montos devueltos por las tools.",
            accion="regenerar",
        )
    return RuleResult("precios_desde_api", True, f"{len(montos)} monto(s) verificados contra las tools")


@rule("formato_meta", "post", "Si la respuesta incluye el bloque <meta>…</meta>, debe ser JSON válido.")
async def formato_meta(state: Any) -> RuleResult:
    raw = state.respuesta_raw or ""
    m = META.search(raw)
    if not m:
        return RuleResult("formato_meta", True, "sin bloque <meta>")
    try:
        json.loads(m.group(1).strip())
        return RuleResult("formato_meta", True, "<meta> es JSON válido")
    except json.JSONDecodeError as exc:
        return RuleResult(
            "formato_meta",
            False,
            f"<meta> no es JSON válido ({exc.msg}). Devuelve el bloque como JSON estricto.",
            accion="regenerar",
        )


@rule("sin_terceros", "post", "Prohibido mencionar nombres o ids de otros clientes distintos al actual.")
async def sin_terceros(state: Any) -> RuleResult:
    texto = data.norm(texto_sin_meta(state.respuesta or ""))
    encontrados = []
    for cid in await data.clientes_ids():
        if cid == state.cliente_id:
            continue
        c = await data.cliente(cid)
        nombres = [cid] + ([c["nombre"]] if c and c.get("nombre") else [])
        for nm in nombres:
            if re.search(r"\b" + re.escape(data.norm(nm)) + r"\b", texto):
                encontrados.append(nm)
    if encontrados:
        return RuleResult(
            "sin_terceros",
            False,
            f"menciona a otros clientes: {', '.join(sorted(set(encontrados)))}",
            accion="bloquear",
        )
    return RuleResult("sin_terceros", True, "no menciona a otros clientes")


PROMESAS = re.compile(
    r"en 24 ?h|24 horas|hoy mismo|en el d[ií]a|de inmediato|al instante|ma[nñ]ana mismo|en minutos", re.I
)


@rule(
    "sin_promesas_de_plazo",
    "post",
    'Prohibido prometer plazos de reembolso menores a la política ("en 24 horas", "hoy mismo"…).',
)
async def sin_promesas_de_plazo(state: Any) -> RuleResult:
    texto = texto_sin_meta(state.respuesta or "")
    if re.search(r"reembols|devoluci|devolver|la plata|abono", texto, re.I) and (m := PROMESAS.search(texto)):
        return RuleResult(
            "sin_promesas_de_plazo",
            False,
            f"promete un plazo indebido («{m.group(0)}»); el plazo de reembolso es 3 a 5 días hábiles.",
            accion="regenerar",
        )
    return RuleResult("sin_promesas_de_plazo", True, "sin promesas de plazo indebidas")


@rule("longitud_maxima", "post", "La respuesta al cliente debe tener como máximo 120 palabras.")
async def longitud_maxima(state: Any) -> RuleResult:
    n = len(texto_sin_meta(state.respuesta or "").split())
    if n > 120:
        return RuleResult("longitud_maxima", False, f"{n} palabras (> 120). Resume la respuesta.", accion="regenerar")
    return RuleResult("longitud_maxima", True, f"{n} palabras")
