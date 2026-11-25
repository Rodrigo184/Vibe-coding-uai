from __future__ import annotations

import json

import httpx
import pytest

from app.main import app


@pytest.fixture
async def client(seeded):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def sse_events(text: str) -> list[dict]:
    out = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        data = [ln[5:].strip() for ln in block.splitlines() if ln.startswith("data:")]
        if data:
            try:
                out.append(json.loads("".join(data)))
            except json.JSONDecodeError:
                pass
    return out


async def test_health_config(client):
    h = (await client.get("/api/health")).json()
    assert h["redis"] is True and h["modo_llm"] == "demo"
    c = (await client.get("/api/config")).json()
    assert "OPENAI_API_KEY" not in json.dumps(c) and "sk-" not in json.dumps(c)


async def test_agents_crud_y_version(client):
    lst = (await client.get("/api/agents")).json()
    assert len(lst) == 11 and lst[0]["id"] == "supervisor"
    router = (await client.get("/api/agents/router")).json()
    router["prompt"]["system"] += "\n- Nueva regla de prueba."
    r = await client.put("/api/agents/router", json=router)
    assert r.status_code == 200 and r.json()["agent"]["version"] == 2
    rest = await client.post("/api/agents/router/restore")
    assert "Nueva regla de prueba" not in rest.json()["agent"]["prompt"]["system"]


async def test_validate_detecta_problemas(client):
    a = (await client.get("/api/agents/analista")).json()
    a["prompt"]["system"] += "\n{{variable_fantasma}}\nNO hagas eso."
    a["tools"].append("tool_fantasma")
    a["prompt"]["salida_schema"] = {"type": "string"}
    res = (await client.post("/api/agents/validate", json=a)).json()
    txt = json.dumps(res["problemas"], ensure_ascii=False)
    assert not res["ok"]
    assert "variable_fantasma" in txt and "tool_fantasma" in txt and "NO" in txt and "salida_schema" in txt


async def test_crear_especialista_y_enrutar_sin_reiniciar(client):
    base = (await client.get("/api/agents/analista")).json()
    nuevo = {
        **base,
        "id": "logistica",
        "nombre": "Logística",
        "dominio": "Despacho, reparto, envíos y logística de entrega de pedidos a domicilio",
        "tools": ["consultar_stock", "sugerir_sustitutos"],
        "acciones_escritura": [],
        "constantes": {"ejemplo": "¿cuánto demora el despacho a domicilio?"},
    }
    r = await client.post("/api/agents", json=nuevo)
    assert r.status_code == 201, r.text
    sup = (await client.get("/api/agents/supervisor")).json()
    sup["constantes"]["especialistas"].append("logistica")
    assert (await client.put("/api/agents/supervisor", json=sup)).status_code == 200
    resp = await client.post(
        "/api/chat",
        json={
            "cliente_id": "c42",
            "sesion_id": "s-log",
            "mensaje": "¿cuánto demora el despacho a domicilio de mi entrega?",
        },
    )
    evs = sse_events(resp.text)
    dec = next(e for e in evs if e["tipo"] == "decision" and e["nodo"] == "router")
    assert dec["contenido"]["elegido"] == "logistica"
    borrar = await client.delete("/api/agents/logistica")
    assert borrar.status_code == 409  # el supervisor lo referencia


async def test_chat_sse_y_confirm(client):
    r = await client.post(
        "/api/chat", json={"cliente_id": "c42", "sesion_id": "s-api", "mensaje": "me cobraron dos veces el pedido 8812"}
    )
    assert r.headers["content-type"].startswith("text/event-stream")
    evs = sse_events(r.text)
    tipos = [e["tipo"] for e in evs]
    assert tipos[0] == "node_start" and "confirm_required" in tipos and tipos[-1] == "final"
    run_id = evs[-1]["contenido"]["run_id"]
    c = await client.post("/api/chat/confirm", json={"run_id": run_id, "confirmar": True})
    fin = sse_events(c.text)[-1]
    assert fin["contenido"]["estado"] == "ok" and fin["contenido"]["veredicto"] == "publicar"
    runs = (await client.get("/api/runs")).json()
    assert runs[0]["run_id"] == run_id
    det = (await client.get(f"/api/runs/{run_id}")).json()
    assert det["events"][-1]["tipo"] == "final"


async def test_tools_api(client):
    r = await client.post("/api/tools/consultar_stock/test", json={"args": {"sku": "PLT-001", "tienda": "LC"}})
    assert r.json()["data"]["stock"] == 42
    w = await client.post("/api/tools/solicitar_reembolso/test", json={"args": {"cobro_id": "c2", "motivo": "x"}})
    assert w.status_code == 409 and w.json()["error"]["code"] == "confirm_required"


async def test_memoria_api(client):
    m = (await client.get("/api/memory/c42")).json()
    assert any(h["clave"] == "restriccion" for h in m["perfil"]) and len(m["episodios"]) == 2
    p = await client.put("/api/memory/c42/perfil", json={"hechos": {"tienda": "VI", "tarjeta": "4111"}})
    assert p.json()["descartados"]
    d = await client.delete("/api/memory/c42")
    assert d.json()["ok"]
    assert (await client.get("/api/memory/c42")).json()["perfil"] == []


async def test_evals_run(client):
    r = await client.post("/api/evals/run", json={"ids": ["ast-01", "fin-01", "mem-02"], "repeticiones": 2})
    evs = sse_events(r.text)
    fin = evs[-1]
    assert fin["tipo"] == "fin"
    rep = (await client.get(f"/api/evals/reports/{fin['report_id']}")).json()
    m = rep["metricas"]
    for k in (
        "precision_enrutamiento",
        "precision_tools",
        "precision",
        "consistencia",
        "cumplimiento_reglas",
        "confirmacion_correcta",
        "derivacion_humano",
        "costo_promedio_usd",
        "latencia_p95_ms",
        "llamadas_llm_promedio",
    ):
        assert k in m
    assert m["precision_enrutamiento"] == 1.0
