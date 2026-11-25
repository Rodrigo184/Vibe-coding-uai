"""Reglas PRE: determinísticas, antes del LLM. El modelo solo recibe el veredicto."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any
from zoneinfo import ZoneInfo

from app.rules.base import RuleResult, rule
from app.tools import data

ALCOHOL = re.compile(r"\b(alcohol\w*|vinos?|cervezas?|pisco|cabernet|whisky|ron|vodka|espumantes?|champa\w*)\b", re.I)
CREDITO = re.compile(r"cr[eé]dito", re.I)
TARJETA = re.compile(r"\b(?:\d[ -]?){13,19}\b")
TZ = ZoneInfo("America/Santiago")


def menciona_alcohol(msg: str) -> bool:
    return bool(ALCOHOL.search(msg or ""))


def hora_local(state: Any) -> dt.datetime:
    override = getattr(state, "hora_override", None)
    if override:
        h, m = (int(x) for x in override.split(":"))
        return dt.datetime.now(TZ).replace(hour=h, minute=m)
    return dt.datetime.now(TZ)


@rule(
    "alcohol_requiere_edad",
    "pre",
    "Si el mensaje menciona alcohol (vino, cerveza, pisco…) y el cliente no tiene la edad verificada → requiere verificación.",
)
async def alcohol_requiere_edad(state: Any) -> RuleResult:
    if not menciona_alcohol(state.mensaje):
        return RuleResult("alcohol_requiere_edad", True, "el mensaje no menciona alcohol")
    c = await data.cliente(state.cliente_id)
    verificada = bool(c and c["edad_verificada"])  # fuente de verdad: negocio:cliente, nunca lo que diga el mensaje
    if verificada:
        return RuleResult("alcohol_requiere_edad", True, "edad verificada", datos={"edad_verificada": True})
    return RuleResult(
        "alcohol_requiere_edad",
        False,
        "el cliente no tiene la edad verificada",
        accion="requiere_verificacion",
        alternativa="verificar la edad con cédula en la app (Perfil → Verificación) o elegir productos sin alcohol",
        datos={"edad_verificada": False},
    )


@rule(
    "cupo_credito",
    "pre",
    "Si el mensaje menciona la línea de crédito, consulta el cupo del cliente; sin cupo disponible → bloquea con alternativa.",
)
async def cupo_credito(state: Any) -> RuleResult:
    if not CREDITO.search(state.mensaje or ""):
        return RuleResult("cupo_credito", True, "el mensaje no menciona crédito")
    c = await data.cliente(state.cliente_id)
    disponible = c["cupo_credito"] if c else 0
    if disponible <= 0:
        return RuleResult(
            "cupo_credito",
            False,
            f"cupo disponible {disponible}",
            accion="bloquear",
            alternativa="pagar con tarjeta de débito, tarjeta de crédito bancaria o transferencia",
            datos={"ok": False, "disponible": disponible},
        )
    return RuleResult(
        "cupo_credito", True, f"cupo disponible {disponible}", datos={"ok": True, "disponible": disponible}
    )


@rule(
    "horario_alcohol",
    "pre",
    "La venta de alcohol solo está permitida de 09:00 a 21:00 (hora de Chile, America/Santiago).",
)
async def horario_alcohol(state: Any) -> RuleResult:
    if not menciona_alcohol(state.mensaje):
        return RuleResult("horario_alcohol", True, "el mensaje no menciona alcohol")
    ahora = hora_local(state)
    ok = 9 <= ahora.hour < 21
    if ok:
        return RuleResult(
            "horario_alcohol", True, f"hora local {ahora:%H:%M} dentro de 09:00–21:00", datos={"ok": True}
        )
    return RuleResult(
        "horario_alcohol",
        False,
        f"hora local {ahora:%H:%M} fuera de 09:00–21:00",
        accion="bloquear",
        alternativa="programar el pedido para mañana desde las 09:00",
        datos={"ok": False},
    )


@rule(
    "datos_sensibles_entrada",
    "pre",
    "Si el mensaje contiene un número de tarjeta → bloqueo total con respuesta fija; nada se guarda en memoria.",
)
async def datos_sensibles_entrada(state: Any) -> RuleResult:
    if TARJETA.search(state.mensaje or ""):
        return RuleResult(
            "datos_sensibles_entrada",
            False,
            "el mensaje contiene un número que parece de tarjeta",
            accion="bloqueo_total",
            alternativa="Por tu seguridad, nunca compartas números de tarjeta por este canal. Para pagar o guardar un medio de pago usa la sección Pagos de la app. Ya descartamos tu mensaje.",
        )
    return RuleResult("datos_sensibles_entrada", True, "sin datos sensibles")


BLOQUEO_KEY = {"alcohol_requiere_edad": "edad", "cupo_credito": "cupo_credito", "horario_alcohol": "horario_alcohol"}


def veredicto(resultados: list[RuleResult]) -> dict[str, Any]:
    """JSON que reciben el pipeline y el agente híbrido (variable veredicto_reglas)."""
    v: dict[str, Any] = {"bloqueo": None, "alternativa": None}
    for r in resultados:
        if r.nombre == "alcohol_requiere_edad" and r.datos:
            v["edad_verificada"] = r.datos.get("edad_verificada")
        if r.nombre == "cupo_credito" and r.datos:
            v["cupo_credito"] = r.datos
        if r.nombre == "horario_alcohol" and r.datos:
            v["horario_alcohol"] = r.datos
        if not r.ok and v["bloqueo"] is None:
            v["bloqueo"] = BLOQUEO_KEY.get(r.nombre, r.nombre)
            v["alternativa"] = r.alternativa
    v["reglas"] = [{"nombre": r.nombre, "ok": r.ok, "accion": r.accion} for r in resultados]
    return v
