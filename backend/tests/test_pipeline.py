"""Pipeline completo (LLM simulado del modo demo): criterios de la sección 14 · Motor."""

from __future__ import annotations

import json

from app.core.redis import get_json, get_redis
from app.engine import pipeline
from app.llm import client as llm
from app.memory import store
from tests.conftest import run_chat


async def test_cobro_duplicado_confirmar(seeded):
    st, events = await run_chat("c42", "me cobraron dos veces el pedido 8812")
    assert st.agente_id == "financiero"
    assert any(t["name"] == "consultar_cobros" for t in st.tools_llamadas)
    assert st.estado == "pendiente_confirmacion" and st.accion_pendiente["tool"] == "solicitar_reembolso"
    assert any(e.tipo == "confirm_required" for e in events)
    assert events[-1].tipo == "final" and events[-1].contenido["estado"] == "pendiente_confirmacion"
    assert await get_json(f"run:{st.run_id}:pendiente")
    st2 = await pipeline.confirm(st.run_id, True)
    assert st2.estado == "ok" and st2.evaluacion["veredicto"] == "publicar"
    assert (await get_redis().hget("negocio:cobro:c2", "estado")) == "reembolsado"
    assert await get_json(f"run:{st.run_id}:pendiente") is None
    again = await pipeline.confirm(st.run_id, True)  # segunda confirmación: no hay pendiente
    assert again is None


async def test_cancelar_accion(seeded):
    st, _ = await run_chat("c42", "me cobraron dos veces el pedido 8812")
    st2 = await pipeline.confirm(st.run_id, False)
    assert "cancelé" in st2.respuesta
    assert (await get_redis().hget("negocio:cobro:c2", "estado")) == "duplicado"


async def test_guardrail_post_bloquea_tras_agotar_regeneracion(seeded, monkeypatch):
    async def fail_post(turn):
        return "regenerar: precio fuera de la evidencia"

    async def judge_must_not_publish(turn):
        raise AssertionError("El evaluador recibió una respuesta rechazada por las reglas POST")

    monkeypatch.setattr(pipeline.rules_post, "run", fail_post)
    monkeypatch.setattr(pipeline.judge, "run", judge_must_not_publish)
    st, _ = await run_chat("c42", "¿Hay palta en Las Condes y a cuánto está hoy?")
    assert st.regeneraciones == 1
    assert st.estado == "humano"
    assert st.ticket_id


async def test_evaluacion_omite_escrituras_y_confirmaciones_persistentes(seeded):
    pending, _ = await run_chat("c42", "me cobraron dos veces el pedido 8812", evaluating=True)
    escalated, _ = await run_chat("c42", "quiero hablar con una persona", forzar_agente="humano", evaluating=True)
    assert pending.estado == "pendiente_confirmacion"
    assert escalated.estado == "humano"
    assert await get_json(f"run:{pending.run_id}:pendiente") is None
    assert await store.historial(pending.sesion_id) == []
    assert await get_redis().llen("negocio:tickets") == 0


async def test_lo_de_siempre(seeded):
    st, _ = await run_chat("c42", "lo de siempre para el viernes")
    assert st.agente_id == "pedidos" and st.accion_pendiente["tool"] == "crear_pedido_borrador"
    skus = {i["sku"] for i in st.accion_pendiente["args"]["items"]}
    assert {"PLT-001", "PAN-204"} <= skus
    st2 = await pipeline.confirm(st.run_id, True)
    nuevos = [p for p in await get_redis().lrange("negocio:pedidos:c42", 0, -1) if p.startswith("B-")]
    assert nuevos and st2.estado == "ok"
    assert st2.hechos_nuevos == []  # el extractor no inventa hechos


async def test_ventas_reglas(seeded):
    st, _ = await run_chat("c42", "quiero 3 botellas de vino y pagar con la línea de crédito", hora_override="12:00")
    assert st.agente_id == "ventas"
    assert st.veredicto_reglas_pre["bloqueo"] == "edad"
    assert any(p["sku"] == "VIN-330" for p in st.precios_api)
    assert all(r["ok"] for r in st.reglas_post)
    st2, _ = await run_chat("c77", "quiero 2 vinos con crédito", sesion_id="s2", hora_override="12:00")
    assert st2.veredicto_reglas_pre["bloqueo"] == "cupo_credito" and st2.veredicto_reglas_pre["alternativa"]


async def test_planner_pausa_en_paso_4(seeded):
    st, events = await run_chat("c-118", "prepara el pedido semanal del restaurante")
    assert st.agente_id == "planner" and st.estado == "pendiente_confirmacion"
    orden = [e.contenido["tool"] for e in events if e.tipo == "tool_call" and e.nodo == "tools"]
    assert orden[:3] == ["historial_pedidos", "consultar_stock", "sugerir_sustitutos"]
    assert st.accion_pendiente["paso"] == 4
    st2 = await pipeline.confirm(st.run_id, True)
    assert st2.estado == "ok" and "borrador" in st2.respuesta


async def test_tarjeta_bloqueada_sin_memoria(seeded):
    st, _ = await run_chat("c42", "guarda mi tarjeta 4111 1111 1111 1111 para la próxima", sesion_id="s-tarjeta")
    assert st.bloqueo_total and st.llamadas_llm == 0
    assert await store.historial("s-tarjeta") == []
    perfil = await store.perfil("c42")
    assert not any("4111" in v for v in perfil.values())


async def test_limite_llamadas(seeded, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_llm_calls_per_turn", 2)
    st, events = await run_chat("c42", "¿Hay palta en Las Condes y a cuánto está hoy?")
    assert st.estado == "limite" and "límite" in st.respuesta
    assert events[-1].tipo == "final"


async def test_error_nunca_500(seeded, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(llm, "_call", boom)
    st, events = await run_chat("c42", "hola")
    assert st.estado == "error" and events[-1].tipo == "final"


async def test_tool_args_invalidos_turno_continua(seeded, monkeypatch):
    calls = {"n": 0}

    async def fake(kind, messages, *, model, **kw):
        if kw.get("name") == "RouterOut":
            d = {
                "agente": "asistente",
                "confianza": 0.9,
                "motivo": "x",
                "intenciones_secundarias": [],
                "alternativo": None,
            }
            return llm.LLMResult(content=json.dumps(d), parsed=d, modelo=model)
        if kind == "tools":
            calls["n"] += 1
            if calls["n"] == 1:
                return llm.LLMResult(
                    content="Thought: consulto",
                    tool_calls=[llm.ToolCall("c1", "consultar_stock", '{"sku":"PLT-001","tienda":"ZZ"}')],
                    modelo=model,
                )
            last = messages[-1]
            assert last["role"] == "tool" and "tienda" in last["content"]
            return llm.LLMResult(content="La tienda indicada no existe; usa LC, PR o VI.", modelo=model)
        if kw.get("name") == "JudgeOut":
            v = {
                "precision": 5,
                "consistencia": 5,
                "cumplimiento_reglas": 5,
                "evidencia": "ok",
                "veredicto": "publicar",
                "feedback": None,
            }
            return llm.LLMResult(content=json.dumps(v), parsed=v, modelo=model)
        return llm.LLMResult(content='{"hechos": []}', parsed={"hechos": []}, modelo=model)

    monkeypatch.setattr(llm, "_call", fake)
    st, _ = await run_chat("c42", "stock de palta")
    assert st.estado == "ok" and calls["n"] == 2
    assert st.tools_llamadas[0]["result"]["ok"] is False


async def test_fuera_de_dominio_reenruta_una_vez(seeded, monkeypatch):
    async def fake(kind, messages, *, model, **kw):
        if kw.get("name") == "RouterOut":
            d = {
                "agente": "analista",
                "confianza": 0.9,
                "motivo": "x",
                "intenciones_secundarias": [],
                "alternativo": None,
            }
            return llm.LLMResult(content=json.dumps(d), parsed=d, modelo=model)
        if kind == "tools":
            return llm.LLMResult(content='{"fuera_de_dominio": true, "sugerido": "financiero"}', modelo=model)
        if kw.get("name") == "JudgeOut":
            v = {
                "precision": 5,
                "consistencia": 5,
                "cumplimiento_reglas": 5,
                "evidencia": "ok",
                "veredicto": "publicar",
                "feedback": None,
            }
            return llm.LLMResult(content=json.dumps(v), parsed=v, modelo=model)
        return llm.LLMResult(content='{"hechos": []}', parsed={"hechos": []}, modelo=model)

    monkeypatch.setattr(llm, "_call", fake)
    st, events = await run_chat("c42", "algo")
    reenrutos = [e for e in events if e.tipo == "decision" and "reenrutado" in e.titulo]
    assert len(reenrutos) == 1 and st.estado == "humano"  # el segundo fuera_de_dominio ya no reenruta


async def test_memoria_preferencia(seeded):
    st, _ = await run_chat("c42", "desde ahora prefiero retirar en Providencia", sesion_id="s-mem")
    assert (await store.perfil("c42"))["tienda"] == "PR"
    assert len(await store.historial("s-mem")) == 2


async def test_run_guardado(seeded):
    st, _ = await run_chat("c42", "hola")
    run = await get_json(f"run:{st.run_id}")
    assert run["summary"]["estado"] == "ok" and run["events"][-1]["tipo"] == "final"
