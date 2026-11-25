"""Genera `negocio.json` (sección 8.3 del SPEC). Las fechas se guardan como desplazamientos en días
respecto del día en que se corre `make seed` (así "mañana" y "esta semana" siempre tienen sentido).

Uso: cd backend && uv run python -m app.seed.build_negocio
"""

from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).parent / "negocio.json"

PRODUCTOS = [
    ("PLT-001", "Palta Hass", "frutas y verduras", "kg", 3990, False, [], "todo el año"),
    ("PLT-002", "Palta Fuerte", "frutas y verduras", "kg", 3490, False, [], "otoño-invierno"),
    ("PAN-204", "Pan integral 500 g", "panadería", "un", 2190, False, ["gluten"], "todo el año"),
    ("PAN-210", "Pan centeno 500 g", "panadería", "un", 2390, False, ["gluten"], "todo el año"),
    ("YOG-301", "Yogur natural 1 L", "lácteos", "un", 1890, False, ["lactosa"], "todo el año"),
    ("YOG-310", "Yogur griego 1 L", "lácteos", "un", 2790, False, ["lactosa"], "todo el año"),
    ("LEC-120", "Leche entera 1 L", "lácteos", "un", 1090, False, ["lactosa"], "todo el año"),
    ("HUE-030", "Huevos 12 un", "huevos", "un", 3990, False, ["huevo"], "todo el año"),
    ("TOM-050", "Tomate", "frutas y verduras", "kg", 1990, False, [], "verano"),
    ("LEC-205", "Lechuga", "frutas y verduras", "un", 1290, False, [], "todo el año"),
    ("MAN-410", "Manzana Fuji", "frutas y verduras", "kg", 1890, False, [], "otoño"),
    ("PLA-420", "Plátano", "frutas y verduras", "kg", 1290, False, [], "todo el año"),
    ("ARR-600", "Arroz 1 kg", "despensa", "un", 1590, False, [], "todo el año"),
    ("FID-610", "Fideos 400 g", "despensa", "un", 990, False, ["gluten"], "todo el año"),
    ("ACE-700", "Aceite de oliva 500 ml", "despensa", "un", 6490, False, [], "todo el año"),
    ("CAF-800", "Café en grano 250 g", "despensa", "un", 5990, False, [], "todo el año"),
    ("VIN-330", "Cabernet reserva 750 ml", "bebidas alcohólicas", "un", 6990, True, ["sulfitos"], "todo el año"),
    ("CER-340", "Cerveza lager 6 un", "bebidas alcohólicas", "un", 5490, True, ["gluten"], "verano"),
    ("MNI-900", "Maní salado 200 g", "snacks", "un", 1490, False, ["maní"], "todo el año"),
    ("ALM-910", "Almendras 200 g", "snacks", "un", 3290, False, ["frutos secos"], "todo el año"),
    ("QUE-500", "Queso gauda 250 g", "fiambrería", "un", 3490, False, ["lactosa"], "todo el año"),
    ("JAM-510", "Jamón de pavo 200 g", "fiambrería", "un", 2990, False, [], "todo el año"),
    ("AGU-100", "Agua 1,5 L", "bebidas", "un", 890, False, [], "todo el año"),
    ("DET-950", "Detergente 3 L", "limpieza", "un", 7990, False, [], "todo el año"),
]

POLITICAS = [
    (
        "devoluciones",
        "Devoluciones de productos",
        "Puedes devolver productos dentro de 10 días corridos desde la entrega, presentando la boleta. Los perecibles (frutas, verduras, lácteos, carnes) solo se aceptan si llegaron en mal estado y se reportan dentro de 48 horas con una foto.",
    ),
    (
        "reembolsos",
        "Reembolsos",
        "Los reembolsos se procesan en 3 a 5 días hábiles y se abonan siempre al medio de pago original. Los cobros duplicados se reembolsan completos tras la confirmación del cliente. Nunca se reembolsa en efectivo ni a otra cuenta.",
    ),
    (
        "alcohol",
        "Venta de alcohol",
        "La venta de bebidas alcohólicas es solo para mayores de 18 años con la edad verificada en la app (Perfil → Verificación, con cédula) y en horario de 09:00 a 21:00. Los pedidos con alcohol fuera de horario se programan para el día siguiente.",
    ),
    (
        "garantia",
        "Garantía de electrodomésticos",
        "Los electrodomésticos tienen 6 meses de garantía legal desde la compra. Durante los primeros 3 meses puedes elegir cambio, reparación o devolución del dinero. Debes presentar la boleta y el producto con sus accesorios.",
    ),
    (
        "cambios_pedido",
        "Cambios de pedido",
        "Puedes cambiar productos, cantidades, dirección u horario de un pedido hasta 2 horas antes del despacho, desde la app o por este canal. Después de ese plazo el pedido ya está en preparación y los cambios no se garantizan.",
    ),
    (
        "datos",
        "Protección de datos personales",
        "Tus datos se usan solo para gestionar tus compras. Puedes ejercer el derecho al olvido desde la app (Perfil → Privacidad → Borrar mis datos) o pidiéndolo a un ejecutivo; el borrado se completa en un máximo de 10 días hábiles. Nunca compartimos datos con terceros.",
    ),
]


def build() -> dict:
    rng = random.Random(42)
    stock = {}
    for tienda in ("LC", "PR", "VI"):
        for p in PRODUCTOS:
            stock[f"{tienda}:{p[0]}"] = rng.randint(0, 60)
    stock["LC:PLT-001"] = 42
    stock["LC:PAN-204"] = 0
    stock["LC:VIN-330"] = 18
    precios = {p[0]: p[4] for p in PRODUCTOS}

    def pedido(pid: str, cliente: str, offset: int, tienda: str, items: list[tuple[str, int]], estado: str) -> dict:
        its = [{"sku": s, "cantidad": c, "precio": precios[s]} for s, c in items]
        return {
            "pedido_id": pid,
            "cliente_id": cliente,
            "fecha_offset": offset,
            "tienda": tienda,
            "items": its,
            "estado": estado,
            "total": sum(i["precio"] * i["cantidad"] for i in its),
        }

    pedidos = []
    # c-118 Restaurante Don Lucho: 8 pedidos semanales entregados, 12–14 ítems, ~$180.000
    base_b2b = [
        "PLT-001",
        "TOM-050",
        "LEC-205",
        "ACE-700",
        "ARR-600",
        "FID-610",
        "QUE-500",
        "JAM-510",
        "HUE-030",
        "PAN-210",
        "LEC-120",
        "AGU-100",
        "MAN-410",
        "CAF-800",
    ]
    base_qty = {
        "PLT-001": 6,
        "TOM-050": 8,
        "LEC-205": 6,
        "ACE-700": 3,
        "ARR-600": 6,
        "FID-610": 8,
        "QUE-500": 5,
        "JAM-510": 4,
        "HUE-030": 4,
        "PAN-210": 6,
        "LEC-120": 10,
        "AGU-100": 8,
        "MAN-410": 4,
        "CAF-800": 2,
    }
    for w in range(8):
        k = 12 + (w % 3)
        skus = base_b2b[:k]
        items = [(s, max(1, base_qty[s] + rng.choice([-1, 0, 0, 1]))) for s in skus]
        pedidos.append(pedido(f"P-{8700 + w * 13}", "c-118", -1 - 7 * w, "LC", items, "entregado"))
    # c42 Camila
    pedidos.append(pedido("P-9001", "c42", -11, "LC", [("PLT-001", 2), ("PAN-204", 1), ("YOG-301", 6)], "entregado"))
    pedidos.append(pedido("P-9055", "c42", -4, "LC", [("PLT-001", 2), ("PAN-204", 1), ("YOG-310", 6)], "entregado"))
    pedidos.append(
        pedido("8812", "c42", -2, "LC", [("LEC-120", 3), ("HUE-030", 3), ("MAN-410", 3), ("PLA-420", 2)], "entregado")
    )
    pedidos.append(
        pedido("P-9120", "c42", 1, "LC", [("PLT-001", 1), ("LEC-120", 2), ("TOM-050", 1), ("YOG-310", 2)], "confirmado")
    )
    # c77 Tomás
    pedidos.append(pedido("P-7701", "c77", 2, "PR", [("AGU-100", 6), ("FID-610", 2), ("TOM-050", 1)], "confirmado"))

    cobros = []
    n = 1
    for p in pedidos:
        if p["estado"] != "entregado":
            continue
        if p["pedido_id"] == "8812":
            cobros.append(
                {"cobro_id": "c1", "pedido_id": "8812", "monto": 23490, "fecha_offset": -2, "estado": "aprobado"}
            )
            cobros.append(
                {"cobro_id": "c2", "pedido_id": "8812", "monto": 23490, "fecha_offset": -2, "estado": "duplicado"}
            )
            continue
        cobros.append(
            {
                "cobro_id": f"k{n:03d}",
                "pedido_id": p["pedido_id"],
                "monto": p["total"],
                "fecha_offset": p["fecha_offset"],
                "estado": "aprobado",
            }
        )
        n += 1

    return {
        "productos": [
            {
                "sku": s,
                "nombre": nm,
                "categoria": cat,
                "unidad": u,
                "precio": pr,
                "contiene_alcohol": alc,
                "alergenos": al,
                "temporada": t,
            }
            for s, nm, cat, u, pr, alc, al, t in PRODUCTOS
        ],
        "stock": stock,
        "clientes": [
            {
                "id": "c42",
                "nombre": "Camila",
                "tienda": "LC",
                "canal": "app",
                "edad_verificada": False,
                "cupo_credito": 120000,
            },
            {
                "id": "c-118",
                "nombre": "Restaurante Don Lucho",
                "tienda": "LC",
                "canal": "web",
                "edad_verificada": True,
                "cupo_credito": 800000,
            },
            {
                "id": "c77",
                "nombre": "Tomás",
                "tienda": "PR",
                "canal": "whatsapp",
                "edad_verificada": True,
                "cupo_credito": 0,
            },
        ],
        "pedidos": pedidos,
        "cobros": cobros,
        "memoria_inicial": {
            "c42": {
                "perfil": {"tienda": "LC", "dia_compra": "viernes", "restriccion": "sin maní", "pan": "integral"},
                "episodios": [
                    {"fecha_offset": -11, "resumen": "cambió yogur natural por griego"},
                    {"fecha_offset": -4, "resumen": "pidió 2 kg palta, pan integral, 6 yogures; entregado ok"},
                ],
            },
            "c-118": {
                "perfil": {"tienda": "LC", "tipo_cliente": "restaurante", "dia_compra": "lunes"},
                "episodios": [],
            },
            "c77": {"perfil": {"tienda": "PR", "canal": "whatsapp"}, "episodios": []},
        },
        "politicas": [{"id": i, "titulo": t, "texto": x} for i, t, x in POLITICAS],
    }


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"negocio.json: {len(data['productos'])} productos, {len(data['pedidos'])} pedidos, {len(data['cobros'])} cobros"
    )
