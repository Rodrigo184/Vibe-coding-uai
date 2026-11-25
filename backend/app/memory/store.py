"""Memoria en Redis (sección 5.3): historial de sesión (corto plazo), perfil (estructurada) y episodios."""

from __future__ import annotations

import datetime as dt
import json
import re
import time
from typing import Any

from app.core.redis import get_redis

HISTORIAL_MAX = 20
HISTORIAL_TTL = 24 * 3600
EPISODIOS_MAX = 30

CLAVES_PROHIBIDAS = re.compile(
    r"tarjeta|cuenta|rut|password|contrasena|clave|salud|diagnostico|religion|politica|direccion_completa|edad_verificada|cupo",
    re.I,
)
VALOR_SENSIBLE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _hoy() -> str:
    return dt.date.today().isoformat()


async def historial(sesion_id: str) -> list[dict[str, Any]]:
    raw = await get_redis().lrange(f"sesion:{sesion_id}:historial", 0, -1)
    out = []
    for x in raw:
        try:
            out.append(json.loads(x))
        except json.JSONDecodeError:
            continue
    return out


async def push_turno(sesion_id: str, cliente_id: str, rol: str, texto: str) -> None:
    r = get_redis()
    key = f"sesion:{sesion_id}:historial"
    await r.rpush(key, json.dumps({"rol": rol, "texto": texto, "ts": time.time()}, ensure_ascii=False))
    await r.ltrim(key, -HISTORIAL_MAX, -1)
    await r.expire(key, HISTORIAL_TTL)
    await r.sadd(f"cliente:{cliente_id}:sesiones", sesion_id)
    await r.set(f"sesion:{sesion_id}:cliente", cliente_id, ex=HISTORIAL_TTL)


async def sesiones(cliente_id: str) -> list[dict[str, Any]]:
    r = get_redis()
    out = []
    for sid in sorted(await r.smembers(f"cliente:{cliente_id}:sesiones")):
        h = await historial(sid)
        if not h:
            await r.srem(f"cliente:{cliente_id}:sesiones", sid)
            continue
        out.append({"sesion_id": sid, "turnos": h})
    return out


async def perfil(cliente_id: str) -> dict[str, str]:
    h = await get_redis().hgetall(f"cliente:{cliente_id}:perfil")
    return {k: v for k, v in h.items() if not k.startswith("_")}


async def perfil_detalle(cliente_id: str) -> list[dict[str, str]]:
    h = await get_redis().hgetall(f"cliente:{cliente_id}:perfil")
    return [
        {"clave": k, "valor": v, "fuente": h.get(f"_fuente:{k}", ""), "fecha": h.get(f"_fecha:{k}", "")}
        for k, v in sorted(h.items())
        if not k.startswith("_")
    ]


def hecho_permitido(clave: str, valor: str) -> str | None:
    """None si se puede guardar; si no, el motivo del descarte."""
    if CLAVES_PROHIBIDAS.search(clave or ""):
        return f"clave prohibida ({clave})"
    if VALOR_SENSIBLE.search(valor or ""):
        return "el valor parece un número de tarjeta o cuenta"
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", clave or ""):
        return "clave inválida (usa snake_case)"
    return None


async def set_hecho(cliente_id: str, clave: str, valor: str, fuente: str = "", reemplaza: bool = True) -> str:
    """Devuelve 'guardado' | 'ignorado' (ya existe y reemplaza=false) | 'descartado: motivo'."""
    motivo = hecho_permitido(clave, valor)
    if motivo:
        return f"descartado: {motivo}"
    r = get_redis()
    key = f"cliente:{cliente_id}:perfil"
    if not reemplaza and await r.hexists(key, clave):
        return "ignorado"
    await r.hset(key, mapping={clave: valor, f"_fuente:{clave}": fuente[:120], f"_fecha:{clave}": _hoy()})
    return "guardado"


async def reemplazar_perfil(cliente_id: str, hechos: dict[str, str]) -> list[str]:
    r = get_redis()
    key = f"cliente:{cliente_id}:perfil"
    actual = await r.hgetall(key)
    await r.delete(key)
    problemas = []
    for k, v in hechos.items():
        motivo = hecho_permitido(k, v)
        if motivo:
            problemas.append(f"{k}: {motivo}")
            continue
        await r.hset(
            key,
            mapping={
                k: v,
                f"_fuente:{k}": actual.get(f"_fuente:{k}", "editado en la UI")
                if actual.get(k) == v
                else "editado en la UI",
                f"_fecha:{k}": actual.get(f"_fecha:{k}", _hoy()) if actual.get(k) == v else _hoy(),
            },
        )
    return problemas


async def episodios(cliente_id: str) -> list[dict[str, Any]]:
    raw = await get_redis().lrange(f"cliente:{cliente_id}:episodios", 0, -1)
    out = []
    for x in raw:
        try:
            out.append(json.loads(x))
        except json.JSONDecodeError:
            out.append({"fecha": "", "resumen": x})
    return out


async def push_episodio(cliente_id: str, resumen: str, fecha: str | None = None) -> None:
    r = get_redis()
    key = f"cliente:{cliente_id}:episodios"
    await r.rpush(key, json.dumps({"fecha": fecha or _hoy(), "resumen": resumen}, ensure_ascii=False))
    await r.ltrim(key, -EPISODIOS_MAX, -1)


async def cerrar_sesion(cliente_id: str, sesion_id: str) -> None:
    r = get_redis()
    await r.delete(f"sesion:{sesion_id}:historial", f"sesion:{sesion_id}:cliente")
    await r.srem(f"cliente:{cliente_id}:sesiones", sesion_id)


async def borrar_todo(cliente_id: str) -> int:
    r = get_redis()
    n = 0
    for sid in await r.smembers(f"cliente:{cliente_id}:sesiones"):
        n += await r.delete(f"sesion:{sid}:historial", f"sesion:{sid}:cliente")
    n += await r.delete(
        f"cliente:{cliente_id}:perfil", f"cliente:{cliente_id}:episodios", f"cliente:{cliente_id}:sesiones"
    )
    return n


async def clientes_con_memoria() -> list[str]:
    ids = set()
    async for k in get_redis().scan_iter(match="cliente:*"):
        parts = k.split(":")
        if len(parts) >= 3:
            ids.add(parts[1])
    return sorted(ids)
