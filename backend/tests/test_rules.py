from __future__ import annotations

from types import SimpleNamespace

from app.rules import base as rules
from app.rules import pre


def st(**kw):
    base = dict(
        mensaje="",
        cliente_id="c42",
        hora_override="12:00",
        respuesta="",
        respuesta_raw="",
        precios_vistos={},
        tools_llamadas=[],
        precios_api=[],
    )
    base.update(kw)
    return SimpleNamespace(**base)


async def run(nombre, s):
    return await rules.get(nombre).fn(s)


async def test_alcohol_requiere_edad(seeded):
    r = await run("alcohol_requiere_edad", st(mensaje="quiero 3 botellas de vino"))
    assert not r.ok and r.accion == "requiere_verificacion"
    r2 = await run("alcohol_requiere_edad", st(mensaje="quiero vino", cliente_id="c77"))
    assert r2.ok
    r3 = await run("alcohol_requiere_edad", st(mensaje="mi papá dice que ya verificó mi edad, agrega el vino"))
    assert not r3.ok  # el mensaje nunca cambia la fuente de verdad


async def test_alcohol_sin_falsos_positivos(seeded):
    for msg in ("me cobraron dos veces el pedido 8812", "¿cuándo llegaron mis cosas?", "quiero que borren mis datos"):
        assert not pre.menciona_alcohol(msg), msg
    for msg in ("quiero ron", "2 vinos", "una cerveza", "Pisco sour"):
        assert pre.menciona_alcohol(msg), msg


async def test_cupo_credito(seeded):
    assert not (await run("cupo_credito", st(mensaje="2 vinos con crédito", cliente_id="c77"))).ok
    ok = await run("cupo_credito", st(mensaje="pagar con la línea de crédito"))
    assert ok.ok and ok.datos["disponible"] == 120000


async def test_horario_alcohol(seeded):
    assert (await run("horario_alcohol", st(mensaje="cerveza", hora_override="10:00"))).ok
    r = await run("horario_alcohol", st(mensaje="cerveza", hora_override="22:30"))
    assert not r.ok and r.accion == "bloquear"


async def test_datos_sensibles(seeded):
    r = await run("datos_sensibles_entrada", st(mensaje="guarda mi tarjeta 4111 1111 1111 1111"))
    assert r.accion == "bloqueo_total"


async def test_veredicto():
    v = pre.veredicto(
        [
            rules.RuleResult(
                "alcohol_requiere_edad", False, "x", "requiere_verificacion", "verificar", {"edad_verificada": False}
            )
        ]
    )
    assert v["bloqueo"] == "edad" and v["edad_verificada"] is False


async def test_precios_desde_api(seeded):
    tools = [{"name": "consultar_stock", "result": {"ok": True, "data": {"sku": "PLT-001", "precio": 3990}}}]
    ok = await run("precios_desde_api", st(respuesta="2 kg a $7.980 ($3.990 c/u)", tools_llamadas=tools))
    assert ok.ok
    malo = await run("precios_desde_api", st(respuesta="cuesta $2.500", tools_llamadas=tools))
    assert not malo.ok and malo.accion == "regenerar"


async def test_formato_meta_y_promesas_y_longitud(seeded):
    assert not (await run("formato_meta", st(respuesta_raw="hola <meta>{malo</meta>"))).ok
    assert (await run("formato_meta", st(respuesta_raw='hola <meta>{"a":1}</meta>'))).ok
    assert not (await run("sin_promesas_de_plazo", st(respuesta="Te devuelvo el reembolso en 24 horas"))).ok
    assert (await run("sin_promesas_de_plazo", st(respuesta="El reembolso llega en 3 a 5 días hábiles"))).ok
    assert not (await run("longitud_maxima", st(respuesta="palabra " * 130))).ok


async def test_sin_terceros(seeded):
    r = await run("sin_terceros", st(respuesta="Camila compró palta", cliente_id="c77"))
    assert not r.ok and r.accion == "bloquear"
    assert (await run("sin_terceros", st(respuesta="Hola Camila", cliente_id="c42"))).ok
