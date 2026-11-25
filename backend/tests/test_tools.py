from __future__ import annotations

from app.tools import registry as tools
from app.tools.registry import ToolContext


def ctx(cid: str = "c42") -> ToolContext:
    return ToolContext(cliente_id=cid, sesion_id="t", run_id="t")


async def test_registro_completo(seeded):
    nombres = {s.name for s in tools.specs()}
    esperadas = {
        "buscar_producto",
        "ficha_producto",
        "consultar_stock",
        "sugerir_sustitutos",
        "pedido_actual",
        "historial_pedidos",
        "estado_pedido",
        "crear_pedido_borrador",
        "agregar_item",
        "consultar_cobros",
        "solicitar_reembolso",
        "buscar_politica",
        "verificar_edad",
        "cupo_credito",
        "crear_ticket",
        "ventas_resumen",
    }
    assert esperadas <= nombres
    spec = tools.get("consultar_stock").spec
    assert spec.parameters["properties"]["tienda"]["enum"] == ["LC", "PR", "VI"]
    assert tools.get("solicitar_reembolso").spec.escritura is True


async def test_buscar_producto_y_stock_forzado(seeded):
    r = await tools.run_tool("buscar_producto", {"q": "palta"}, ctx())
    assert r.ok and r.data[0]["sku"] == "PLT-001"
    s = await tools.run_tool("consultar_stock", {"sku": "PLT-001", "tienda": "LC"}, ctx())
    assert s.ok and s.data["stock"] == 42 and s.data["precio"] == 3990
    s0 = await tools.run_tool("consultar_stock", {"sku": "PAN-204", "tienda": "LC"}, ctx())
    assert s0.data["stock"] == 0


async def test_args_invalidos_error_claro(seeded):
    r = await tools.run_tool("consultar_stock", {"sku": "PLT-001", "tienda": "XX"}, ctx())
    assert not r.ok and "tienda" in r.error and "LC" in r.error
    r2 = await tools.run_tool("consultar_stock", {"sku": "palta", "tienda": "LC"}, ctx())
    assert not r2.ok and "formato" in r2.error
    r3 = await tools.run_tool("no_existe", {}, ctx())
    assert not r3.ok


async def test_aislamiento_por_cliente(seeded):
    # 8812 es de c42: c77 no lo ve, aunque el modelo envíe otro cliente_id
    r = await tools.run_tool("consultar_cobros", {"pedido_id": "8812", "cliente_id": "c42"}, ctx("c77"))
    assert not r.ok and "no encontrado" in r.error
    ok = await tools.run_tool("consultar_cobros", {"pedido_id": "8812"}, ctx("c42"))
    assert ok.ok and {c["estado"] for c in ok.data} == {"aprobado", "duplicado"}


async def test_reembolso_y_doble_reembolso(seeded):
    r = await tools.run_tool("solicitar_reembolso", {"cobro_id": "c2", "motivo": "duplicado"}, ctx())
    assert r.ok and r.data["plazo"] == "3-5 días hábiles"
    r2 = await tools.run_tool("solicitar_reembolso", {"cobro_id": "c2", "motivo": "duplicado"}, ctx())
    assert not r2.ok and "ya fue reembolsado" in r2.error


async def test_agregar_item_idempotente_y_stock(seeded):
    args = {"pedido_id": "P-9120", "sku": "PLT-001", "cantidad": 2, "idempotency_key": "key-1"}
    a = await tools.run_tool("agregar_item", args, ctx())
    b = await tools.run_tool("agregar_item", args, ctx())
    assert a.ok and b.ok and b.data.get("idempotente")
    assert a.data["total"] == b.data["total"]
    big = await tools.run_tool("agregar_item", {**args, "cantidad": 500, "idempotency_key": "key-2"}, ctx())
    assert not big.ok and "stock insuficiente" in big.error


async def test_crear_borrador_dedup(seeded):
    import datetime as dt

    f = (dt.date.today() + dt.timedelta(days=2)).isoformat()
    args = {"items": [{"sku": "PLT-001", "cantidad": 2}], "fecha_entrega": f, "tienda": "LC"}
    a = await tools.run_tool("crear_pedido_borrador", args, ctx())
    b = await tools.run_tool("crear_pedido_borrador", args, ctx())
    assert a.ok and b.ok and a.data["pedido_id"] == b.data["pedido_id"] and b.data.get("deduplicado")
    assert a.data["total"] == 7980 and a.data["estado"] == "borrador"


async def test_historial_promedio_y_ventas(seeded):
    h = await tools.run_tool("historial_pedidos", {"n": 8}, ctx("c-118"))
    assert h.ok and len(h.data["pedidos"]) == 8 and h.data["skus"]
    sin_pan = await tools.run_tool("historial_pedidos", {"n": 8, "excluir": ["pan"]}, ctx("c-118"))
    assert "PAN-210" not in sin_pan.data["skus"]
    v = await tools.run_tool("ventas_resumen", {"tienda": "LC", "dias": 7}, ctx())
    assert v.ok and v.data["top"]


async def test_politica_lexica(seeded):
    r = await tools.run_tool("buscar_politica", {"pregunta": "¿hasta cuándo puedo devolver un producto?"}, ctx())
    assert r.ok and r.data[0]["id"] == "devoluciones"


async def test_sustitutos(seeded):
    r = await tools.run_tool("sugerir_sustitutos", {"skus": ["PAN-204"], "tienda": "LC"}, ctx())
    s = r.data["sugerencias"][0]
    assert s["sin_stock"] and all(a["stock"] > 0 for a in s["alternativas"])
