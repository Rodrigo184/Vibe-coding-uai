from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.tools import data
from app.tools.registry import ToolContext, ToolError, tool

SKU = r"^[A-Z]{3}-\d{3}$"


class BuscarProductoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(..., min_length=2, max_length=80, description="texto a buscar: nombre o categoría")


@tool(
    "buscar_producto",
    "Busca productos del catálogo por texto (nombre o categoría). Devuelve hasta 5 resultados con SKU y precio. Úsala para obtener el SKU antes de consultar stock.",
    ejemplo={"q": "palta"},
)
async def buscar_producto(args: BuscarProductoArgs, ctx: ToolContext) -> list[dict]:
    q = data.norm(args.q).strip()
    qt = data.tokens(args.q)
    scored = []
    for p in await data.productos():
        nombre = data.norm(p["nombre"])
        cat = data.norm(p["categoria"])
        score = 0
        if q and q in nombre:
            score += 10 + (5 if nombre.startswith(q) else 0)
        if q and q in cat:
            score += 4
        nt = data.tokens(p["nombre"] + " " + p["categoria"])
        score += sum(2 for t in qt if t in nt)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1]["sku"]))
    return [{k: p[k] for k in ("sku", "nombre", "categoria", "unidad", "precio")} for _, p in scored[:5]]


class FichaProductoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(..., pattern=SKU)


@tool(
    "ficha_producto",
    "Ficha completa de un SKU: alérgenos, si contiene alcohol, temporada, unidad y precio.",
    ejemplo={"sku": "PAN-204"},
)
async def ficha_producto(args: FichaProductoArgs, ctx: ToolContext) -> dict:
    p = await data.producto(args.sku)
    if not p:
        raise ToolError(f"SKU {args.sku} no existe")
    return p


class SugerirSustitutosArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skus: list[str] = Field(..., max_length=20, description="SKUs a reemplazar (lista vacía = nada que sustituir)")
    tienda: Literal["LC", "PR", "VI"]


@tool(
    "sugerir_sustitutos",
    "Para cada SKU indica si tiene stock en la tienda y propone 1–2 alternativas de la misma categoría con stock.",
    ejemplo={"skus": ["PAN-204"], "tienda": "LC"},
)
async def sugerir_sustitutos(args: SugerirSustitutosArgs, ctx: ToolContext) -> dict:
    todos = await data.productos()
    out: list[dict[str, Any]] = []
    for sku in args.skus:
        p = await data.producto(sku)
        if not p:
            out.append({"sku": sku, "error": "SKU no existe", "alternativas": []})
            continue
        st = await data.stock(args.tienda, sku)
        alts = []
        for q in todos:
            if q["sku"] == sku or q["categoria"] != p["categoria"]:
                continue
            s2 = await data.stock(args.tienda, q["sku"])
            if s2 > 0:
                alts.append({"sku": q["sku"], "nombre": q["nombre"], "precio": q["precio"], "stock": s2})
        alts.sort(key=lambda a: abs(a["precio"] - p["precio"]))
        out.append({"sku": sku, "nombre": p["nombre"], "stock": st, "sin_stock": st == 0, "alternativas": alts[:2]})
    return {"tienda": args.tienda, "sugerencias": out}
