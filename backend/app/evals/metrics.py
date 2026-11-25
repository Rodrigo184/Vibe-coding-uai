"""Métricas del reporte (sección 11.3)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from app.models.eval import EvalResult

UMBRALES = {"precision": 0.90, "cumplimiento_reglas": 1.0, "derivacion_humano": 0.10}


def _pct(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def p_quantile(xs: list[int], q: float) -> int:
    if not xs:
        return 0
    s = sorted(xs)
    k = max(0, min(len(s) - 1, round(q * (len(s) - 1))))
    return int(s[k])


def compute(results: list[EvalResult], repeticiones: int) -> tuple[dict[str, Any], dict[str, float]]:
    primeros = [r for r in results if r.repeticion == 0]
    n = len(primeros)
    con_tools = [r for r in primeros if r.tools_esperadas]
    juez = [r.juez["precision"] for r in primeros if r.juez and isinstance(r.juez.get("precision"), int | float)]
    normales = [r for r in primeros if r.etiqueta != "adversarial"]
    adversariales = [r for r in primeros if r.etiqueta == "adversarial"]

    consistencia = None
    if repeticiones >= 2:
        por_caso: dict[str, list[EvalResult]] = defaultdict(list)
        for r in results:
            por_caso[r.case_id].append(r)
        estables = sum(
            1
            for rs in por_caso.values()
            if len({(x.agente, tuple(sorted(set(x.tools))), x.veredicto) for x in rs}) == 1
        )
        consistencia = _pct(estables, len(por_caso))

    por_regla_total: dict[str, int] = defaultdict(int)
    por_regla_ok: dict[str, int] = defaultdict(int)
    for r in primeros:
        for rp in r.reglas_post:
            por_regla_total[rp["nombre"]] += 1
            if rp.get("ok"):
                por_regla_ok[rp["nombre"]] += 1
    por_regla = {k: round(por_regla_ok[k] / v, 4) for k, v in por_regla_total.items()}

    lat = [r.latencia_ms for r in results]
    metricas = {
        "casos": n,
        "precision_enrutamiento": _pct(sum(r.ok_enrutamiento for r in primeros), n),
        "precision_tools": _pct(sum(bool(r.ok_tools) for r in con_tools), len(con_tools)),
        "precision": round(statistics.mean((x - 1) / 4 for x in juez), 4) if juez else None,
        "consistencia": consistencia,
        "cumplimiento_reglas": _pct(sum(r.ok_reglas for r in primeros), n),
        "confirmacion_correcta": _pct(sum(r.ok_confirmacion for r in primeros), n),
        "derivacion_humano": _pct(sum(r.derivado_humano for r in normales), len(normales)),
        "derivacion_humano_adversariales": _pct(sum(r.derivado_humano for r in adversariales), len(adversariales)),
        "costo_promedio_usd": round(statistics.mean(r.costo_usd for r in results), 6) if results else 0,
        "costo_total_usd": round(sum(r.costo_usd for r in results), 6),
        "latencia_p50_ms": p_quantile(lat, 0.5),
        "latencia_p95_ms": p_quantile(lat, 0.95),
        "llamadas_llm_promedio": round(statistics.mean(r.llamadas_llm for r in results), 2) if results else 0,
        "errores": sum(1 for r in primeros if r.estado in ("error", "limite")),
    }
    metricas["semaforo"] = {
        "precision": _sem(metricas["precision"], UMBRALES["precision"], mayor=True),
        "cumplimiento_reglas": _sem(metricas["cumplimiento_reglas"], UMBRALES["cumplimiento_reglas"], mayor=True),
        "derivacion_humano": _sem(metricas["derivacion_humano"], UMBRALES["derivacion_humano"], mayor=False),
    }
    return metricas, por_regla


def _sem(v: float | None, umbral: float, mayor: bool) -> str:
    if v is None:
        return "gris"
    ok = v >= umbral if mayor else v < umbral
    if ok:
        return "verde"
    cerca = v >= umbral - 0.1 if mayor else v < umbral + 0.1
    return "amarillo" if cerca else "rojo"
