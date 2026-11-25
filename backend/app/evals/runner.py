"""Corre el dataset contra la configuración actual de agentes y guarda un EvalReport.

Cada caso lee la memoria del cliente en una sesión nueva. La evaluación registra la traza
y mide las solicitudes de confirmación sin guardar hechos ni ejecutar acciones de escritura.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import get_settings
from app.core.redis import get_json, get_redis, set_json
from app.engine import pipeline, registry
from app.evals import metrics
from app.models.eval import EvalCase, EvalReport, EvalResult


async def dataset() -> list[EvalCase]:
    raw = await get_json("eval:dataset", [])
    return [EvalCase.model_validate(c) for c in raw]


def _evaluar(case: EvalCase, st: Any, rep: int) -> EvalResult:
    tools = [t["name"] for t in st.tools_llamadas if t.get("agente") != "humano" or t["name"] == "crear_ticket"]
    if st.accion_pendiente:
        tools.append(st.accion_pendiente["tool"])
    agente = st.agente_id if st.estado != "humano" or st.agente_id else "humano"
    if st.estado == "humano" and not st.agente_id:
        agente = "humano"
    esperado = case.agente_esperado
    esperados = esperado if isinstance(esperado, list) else ([esperado] if esperado else [])
    ok_ruta = (not esperados) or agente in esperados or (st.estado == "humano" and "humano" in esperados)
    ok_tools = all(t in tools for t in case.tools_esperadas) if case.tools_esperadas else None
    pidio = st.estado == "pendiente_confirmacion" or any(
        a.get("estado") == "pendiente_confirmacion" for a in st.acciones
    )
    juez = st.evaluacion or None
    fallas = [r for r in st.reglas_post if not r.get("ok")]
    ok_reglas = not fallas and (not juez or int(juez.get("cumplimiento_reglas") or 5) >= 4)
    return EvalResult(
        case_id=case.id,
        repeticion=rep,
        etiqueta=case.etiqueta,
        mensaje=case.mensaje,
        agente_esperado=case.agente_esperado,
        agente=agente,
        tools_esperadas=case.tools_esperadas,
        tools=tools,
        respuesta=st.respuesta,
        veredicto=(juez or {}).get("veredicto") or ("humano" if st.estado == "humano" else None),
        juez=juez,
        reglas_post=st.reglas_post,
        pidio_confirmacion=pidio,
        debe_pedir_confirmacion=case.debe_pedir_confirmacion,
        derivado_humano=st.estado == "humano",
        estado=st.estado,
        costo_usd=round(st.costo_usd, 6),
        latencia_ms=int((dt.datetime.now().timestamp() - st.inicio) * 1000),
        llamadas_llm=st.llamadas_llm,
        run_id=st.run_id,
        ok_enrutamiento=ok_ruta,
        ok_tools=ok_tools,
        ok_reglas=ok_reglas,
        ok_confirmacion=pidio == case.debe_pedir_confirmacion,
    )


async def run_eval(
    ids: list[str] | None = None, repeticiones: int = 1, supervisor_id: str = "supervisor"
) -> AsyncIterator[dict[str, Any]]:
    casos = [c for c in await dataset() if not ids or c.id in ids]
    repeticiones = max(1, min(5, repeticiones))
    total = len(casos) * repeticiones
    resultados: list[EvalResult] = []
    i = 0
    yield {"tipo": "inicio", "total": total, "casos": len(casos), "repeticiones": repeticiones}
    for rep in range(repeticiones):
        for case in casos:
            i += 1
            sesion = f"eval-{uuid.uuid4().hex[:8]}"
            try:
                turn = await pipeline.build_turn(
                    cliente_id=case.cliente_id,
                    sesion_id=sesion,
                    mensaje=case.mensaje,
                    supervisor_id=supervisor_id,
                    respuesta_esperada=case.respuesta_esperada or None,
                    evaluating=True,
                )
                st = await pipeline.run_turn(turn)
                res = _evaluar(case, st, rep)
            except Exception as exc:
                res = EvalResult(
                    case_id=case.id,
                    repeticion=rep,
                    etiqueta=case.etiqueta,
                    mensaje=case.mensaje,
                    agente_esperado=case.agente_esperado,
                    estado="error",
                    respuesta=f"{type(exc).__name__}: {exc}",
                    tools_esperadas=case.tools_esperadas,
                    ok_confirmacion=not case.debe_pedir_confirmacion,
                )
            resultados.append(res)
            yield {"tipo": "progreso", "i": i, "total": total, "resultado": res.model_dump()}
    met, por_regla = metrics.compute(resultados, repeticiones)
    report = EvalReport(
        id="ev-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4],
        creado=dt.datetime.now(dt.UTC).isoformat(),
        version_agentes=await registry.version(),
        repeticiones=repeticiones,
        casos=len(casos),
        metricas=met,
        por_regla=por_regla,
        resultados=resultados,
        modo_llm="demo" if get_settings().use_mock_llm else "openai",
    )
    await set_json(f"eval:report:{report.id}", report.model_dump(mode="json"))
    await get_redis().zadd("eval:reports:index", {report.id: dt.datetime.now().timestamp()})
    yield {"tipo": "fin", "report_id": report.id, "metricas": met}


async def run_eval_sync(ids: list[str] | None = None, repeticiones: int = 1) -> dict[str, Any]:
    last: dict[str, Any] = {}
    async for ev in run_eval(ids, repeticiones):
        if ev["tipo"] == "progreso":
            r = ev["resultado"]
            print(
                f"[{ev['i']:>3}/{ev['total']}] {r['case_id']:<8} agente={r['agente']!s:<11} ruta={'✓' if r['ok_enrutamiento'] else '✗'} estado={r['estado']}"
            )
        last = ev
    return last


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--repeticiones", type=int, default=1)
    a = ap.parse_args()
    out = asyncio.run(run_eval_sync(a.ids, a.repeticiones))
    print(json.dumps(out, ensure_ascii=False, indent=2))
