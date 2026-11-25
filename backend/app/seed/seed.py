"""`make seed`: negocio + agentes + dataset (idempotente; no toca la memoria de clientes salvo la inicial
si aún no existe). `make reset`: borra TODO (incluida memoria, runs y reportes) y vuelve a sembrar.

Uso: python -m app.seed.seed [--reset] [--que negocio agentes dataset | --indexar-politicas]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.redis import get_redis, set_json
from app.llm import client as llm

HERE = Path(__file__).parent


def _load(name: str) -> Any:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _fecha(offset: int) -> str:
    return (dt.date.today() + dt.timedelta(days=int(offset))).isoformat()


async def _borrar(pattern: str) -> int:
    r = get_redis()
    n = 0
    async for k in r.scan_iter(match=pattern):
        n += await r.delete(k)
    return n


async def seed_negocio() -> dict[str, int]:
    r = get_redis()
    await _borrar("negocio:*")
    d = _load("negocio.json")
    for p in d["productos"]:
        await r.hset(
            f"negocio:producto:{p['sku']}",
            mapping={
                "nombre": p["nombre"],
                "categoria": p["categoria"],
                "unidad": p["unidad"],
                "precio": p["precio"],
                "contiene_alcohol": "true" if p["contiene_alcohol"] else "false",
                "alergenos": json.dumps(p["alergenos"], ensure_ascii=False),
                "temporada": p["temporada"],
            },
        )
        await r.sadd("negocio:productos:index", p["sku"])
    for k, v in d["stock"].items():
        await r.set(f"negocio:stock:{k}", v)
    for c in d["clientes"]:
        await r.hset(
            f"negocio:cliente:{c['id']}",
            mapping={
                "nombre": c["nombre"],
                "tienda": c["tienda"],
                "canal": c["canal"],
                "edad_verificada": "true" if c["edad_verificada"] else "false",
                "cupo_credito": c["cupo_credito"],
            },
        )
    pedidos = sorted(d["pedidos"], key=lambda p: p["fecha_offset"])
    for p in pedidos:
        pedido = {k: v for k, v in p.items() if k != "fecha_offset"}
        pedido["fecha_entrega"] = _fecha(p["fecha_offset"])
        await set_json(f"negocio:pedido:{p['pedido_id']}", pedido)
        await r.rpush(f"negocio:pedidos:{p['cliente_id']}", p["pedido_id"])
    for c in d["cobros"]:
        await r.hset(
            f"negocio:cobro:{c['cobro_id']}",
            mapping={
                "pedido_id": c["pedido_id"],
                "monto": c["monto"],
                "fecha": _fecha(c["fecha_offset"]),
                "estado": c["estado"],
            },
        )
        await r.rpush(f"negocio:cobros:{c['pedido_id']}", c["cobro_id"])
    embeddings = None
    try:
        embeddings = await llm.embed([f"{p['titulo']}. {p['texto']}" for p in d["politicas"]])
    except Exception:
        embeddings = None
    for i, p in enumerate(d["politicas"]):
        mapping = {"titulo": p["titulo"], "texto": p["texto"]}
        if embeddings:
            mapping["embedding"] = json.dumps(embeddings[i])
        await r.hset(f"negocio:politica:{p['id']}", mapping=mapping)
    return {
        "productos": len(d["productos"]),
        "pedidos": len(pedidos),
        "cobros": len(d["cobros"]),
        "politicas": len(d["politicas"]),
        "embeddings": bool(embeddings),
    }


async def seed_memoria_inicial(force: bool = False) -> list[str]:
    r = get_redis()
    d = _load("negocio.json")
    hechos = []
    for cid, mem in d["memoria_inicial"].items():
        if not force and (await r.exists(f"cliente:{cid}:perfil") or await r.exists(f"cliente:{cid}:episodios")):
            continue
        await r.delete(f"cliente:{cid}:perfil", f"cliente:{cid}:episodios")
        hoy = dt.date.today().isoformat()
        for k, v in mem["perfil"].items():
            await r.hset(f"cliente:{cid}:perfil", mapping={k: v, f"_fuente:{k}": "semilla", f"_fecha:{k}": hoy})
        for e in mem["episodios"]:
            fecha = dt.date.today() + dt.timedelta(days=e["fecha_offset"])
            await r.rpush(
                f"cliente:{cid}:episodios",
                json.dumps(
                    {"fecha": fecha.isoformat(), "resumen": f"{fecha:%d-%m}: {e['resumen']}"}, ensure_ascii=False
                ),
            )
        hechos.append(cid)
    return hechos


async def seed_agentes() -> int:
    r = get_redis()
    await _borrar("agent:*")
    await _borrar("agents:seed:*")
    await r.delete("agents:index")
    agents = _load("agentes.json")
    now = dt.datetime.now(dt.UTC).isoformat()
    for a in agents:
        a["actualizado"] = now
        await set_json(f"agent:{a['id']}", a)
        await set_json(f"agents:seed:{a['id']}", a)
        await r.sadd("agents:index", a["id"])
    await r.incr("agents:version")
    return len(agents)


async def seed_dataset() -> int:
    data = _load("dataset.json")
    await set_json("eval:dataset", data)
    return len(data)


async def seed(que: list[str] | None = None) -> dict[str, Any]:
    que = que or ["negocio", "agentes", "dataset"]
    out: dict[str, Any] = {}
    if "negocio" in que:
        out["negocio"] = await seed_negocio()
        out["memoria_inicial"] = await seed_memoria_inicial()
    if "agentes" in que:
        out["agentes"] = await seed_agentes()
    if "dataset" in que:
        out["dataset"] = await seed_dataset()
    return out


async def reset() -> dict[str, Any]:
    await get_redis().flushdb()
    out = await seed()
    out["memoria_inicial"] = await seed_memoria_inicial(force=True)
    return out


async def ensure_seeded() -> bool:
    """Al iniciar: si Redis está vacío, siembra todo (útil en docker compose up)."""
    r = get_redis()
    if await r.exists("agents:index"):
        return False
    await seed()
    return True


async def indexar_politicas() -> dict[str, int]:
    """Actualiza los vectores de las políticas existentes sin resembrar el negocio."""
    if not get_settings().openai_configured:
        raise ValueError("Configura OPENAI_API_KEY antes de indexar las políticas.")
    r = get_redis()
    keys = [key async for key in r.scan_iter(match="negocio:politica:*")]
    if not keys:
        return {"politicas_indexadas": 0}
    docs = [await r.hgetall(key) for key in keys]
    vectors = await llm.embed([f"{doc['titulo']}. {doc['texto']}" for doc in docs])
    if vectors is None or len(vectors) != len(keys):
        raise ValueError("OpenAI no devolvió un vector para cada política.")
    async with r.pipeline(transaction=True) as pipe:
        for key, vector in zip(keys, vectors, strict=True):
            pipe.hset(key, "embedding", json.dumps(vector))
        await pipe.execute()
    return {"politicas_indexadas": len(keys)}


def main() -> None:
    ap = argparse.ArgumentParser()
    actions = ap.add_mutually_exclusive_group()
    actions.add_argument("--reset", action="store_true")
    actions.add_argument("--que", nargs="*")
    actions.add_argument("--indexar-politicas", action="store_true")
    a = ap.parse_args()
    if a.indexar_politicas:
        res = asyncio.run(indexar_politicas())
    else:
        res = asyncio.run(reset() if a.reset else seed(a.que))
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
