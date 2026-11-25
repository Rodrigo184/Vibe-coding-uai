"""Router con el LLM mockeado (respuestas fijas, sin el modo demo)."""

from __future__ import annotations

import json

import pytest

from app.llm import client as llm
from tests.conftest import run_chat


def fake_router(salida: dict):
    async def _call(kind, messages, *, model, **kw):
        if kw.get("name") == "RouterOut":
            return llm.LLMResult(content=json.dumps(salida), parsed=salida, tokens_in=10, tokens_out=5, modelo=model)
        if kind == "json" and kw.get("name") == "JudgeOut":
            v = {
                "precision": 5,
                "consistencia": 5,
                "cumplimiento_reglas": 5,
                "evidencia": "ok",
                "veredicto": "publicar",
                "feedback": None,
            }
            return llm.LLMResult(content=json.dumps(v), parsed=v, modelo=model)
        if kind == "json":
            return llm.LLMResult(content='{"hechos": []}', parsed={"hechos": []}, modelo=model)
        return llm.LLMResult(content="Respuesta de prueba.", modelo=model)

    return _call


@pytest.mark.parametrize(
    "salida,esperado",
    [
        (
            {
                "agente": "financiero",
                "confianza": 0.93,
                "motivo": "cobro",
                "intenciones_secundarias": [],
                "alternativo": None,
            },
            "financiero",
        ),
        (
            {
                "agente": "financiero",
                "confianza": 0.4,
                "motivo": "dudoso",
                "intenciones_secundarias": [],
                "alternativo": None,
            },
            "humano",
        ),
        (
            {
                "agente": "inventado",
                "confianza": 0.9,
                "motivo": "x",
                "intenciones_secundarias": [],
                "alternativo": "pedidos",
            },
            "pedidos",
        ),
        (
            {
                "agente": "inventado",
                "confianza": 0.9,
                "motivo": "x",
                "intenciones_secundarias": [],
                "alternativo": None,
            },
            "humano",
        ),
    ],
)
async def test_router_valida_salida(seeded, monkeypatch, salida, esperado):
    monkeypatch.setattr(llm, "_call", fake_router(salida))
    st, events = await run_chat("c42", "mensaje cualquiera")
    decision = next(e for e in events if e.nodo == "router" and e.tipo == "decision")
    assert decision.contenido["elegido"] == esperado
    if esperado == "humano":
        assert st.estado == "humano" and st.ticket_id


async def test_router_demo_clasifica_escenarios(seeded):
    casos = {
        "me cobraron dos veces el pedido 8812": "financiero",
        "¿hasta cuándo puedo devolver un producto?": "politicas",
        "prepara el pedido semanal del restaurante": "planner",
        "quiero 3 botellas de vino": "ventas",
        "¿qué se vendió más esta semana en Las Condes?": "analista",
    }
    for msg, esperado in casos.items():
        st, _ = await run_chat("c42", msg, sesion_id=f"s-{esperado}")
        assert st.router["agente"] == esperado, msg
