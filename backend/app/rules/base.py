"""Registro de reglas en código: `@rule("nombre", fase="pre"|"post", descripcion=...)`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal

Accion = Literal["pasa", "regenerar", "bloquear", "requiere_verificacion", "bloqueo_total"]


@dataclass
class RuleResult:
    nombre: str
    ok: bool
    detalle: str
    accion: Accion = "pasa"
    alternativa: str | None = None
    datos: dict[str, Any] | None = None

    def dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class RuleDef:
    nombre: str
    fase: Literal["pre", "post"]
    descripcion: str
    fn: Callable[[Any], Awaitable[RuleResult]]


RULES: dict[str, RuleDef] = {}


def rule(nombre: str, fase: Literal["pre", "post"], descripcion: str):
    def deco(fn: Callable[[Any], Awaitable[RuleResult]]):
        RULES[nombre] = RuleDef(nombre=nombre, fase=fase, descripcion=descripcion, fn=fn)
        return fn

    return deco


def catalogo() -> list[dict[str, str]]:
    from app.rules import post, pre  # noqa: F401

    return [{"nombre": r.nombre, "fase": r.fase, "descripcion": r.descripcion} for r in RULES.values()]


def get(nombre: str) -> RuleDef | None:
    from app.rules import post, pre  # noqa: F401

    return RULES.get(nombre)
