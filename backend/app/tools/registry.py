"""Registro de tools: `@tool(name, descripcion, escritura)` → ToolSpec con JSON Schema desde el modelo
Pydantic de argumentos; valida antes de ejecutar y envuelve errores en ToolResult(ok=False, error=…)."""

from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

from pydantic import BaseModel, ValidationError

from app.models.tool import ToolResult, ToolSpec


@dataclass
class ToolContext:
    cliente_id: str
    sesion_id: str = ""
    run_id: str = ""
    redis: Any = None
    extra: dict[str, Any] = field(default_factory=dict)


class ToolError(Exception):
    """Error de negocio con mensaje claro para el modelo."""


@dataclass
class RegisteredTool:
    spec: ToolSpec
    args_model: type[BaseModel]
    fn: Callable[[BaseModel, ToolContext], Awaitable[Any]]


TOOLS: dict[str, RegisteredTool] = {}


def _deref(schema: dict) -> dict:
    defs = schema.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"].split("/")[-1]
                return walk(dict(defs.get(ref, {})))
            return {k: walk(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


def tool(name: str, descripcion: str, escritura: bool = False, ejemplo: dict | None = None):
    def deco(fn: Callable[..., Awaitable[Any]]):
        hints = get_type_hints(fn)
        first = next(iter(inspect.signature(fn).parameters))
        model: type[BaseModel] = hints[first]
        params = _deref(model.model_json_schema())
        params.setdefault("properties", {})
        params["additionalProperties"] = False
        TOOLS[name] = RegisteredTool(
            spec=ToolSpec(
                name=name, descripcion=descripcion, escritura=escritura, parameters=params, ejemplo_args=ejemplo or {}
            ),
            args_model=model,
            fn=fn,
        )
        return fn

    return deco


def _fmt_validation(exc: ValidationError) -> str:
    msgs = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "args"
        t = err["type"]
        if t == "literal_error":
            exp = err.get("ctx", {}).get("expected", "")
            msgs.append(f"{loc} inválido; usa {exp.replace(' or ', ' o ')}")
        elif t == "string_pattern_mismatch":
            msgs.append(
                f"{loc} con formato inválido (esperado {err.get('ctx', {}).get('pattern', '')}, p. ej. PLT-001)"
            )
        elif t == "missing":
            msgs.append(f"falta el argumento obligatorio '{loc}'")
        elif t == "extra_forbidden":
            msgs.append(f"argumento '{loc}' no existe en el schema")
        else:
            msgs.append(f"{loc}: {err['msg']}")
    return "; ".join(msgs)


def get(name: str) -> RegisteredTool | None:
    _ensure_loaded()
    return TOOLS.get(name)


def specs() -> list[ToolSpec]:
    _ensure_loaded()
    return [t.spec for t in TOOLS.values()]


def openai_tools(names: list[str]) -> list[dict]:
    _ensure_loaded()
    out = []
    for n in names:
        t = TOOLS.get(n)
        if not t:
            continue
        desc = t.spec.descripcion + (" [ESCRITURA: requiere confirmación del usuario]" if t.spec.escritura else "")
        out.append({"type": "function", "function": {"name": n, "description": desc, "parameters": t.spec.parameters}})
    return out


def tools_json(names: list[str], acciones_escritura: list[str] | None = None) -> list[dict]:
    """Versión compacta para el bloque [HERRAMIENTAS] de los prompts."""
    _ensure_loaded()
    out = []
    for n in names:
        t = TOOLS.get(n)
        if not t:
            continue
        escritura = t.spec.escritura or (acciones_escritura is not None and n in acciones_escritura)
        out.append(
            {
                "name": n,
                "description": t.spec.descripcion,
                "escritura": escritura,
                "parameters": t.spec.parameters.get("properties", {}),
            }
        )
    return out


async def run_tool(name: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ensure_loaded()
    t0 = time.perf_counter()
    t = TOOLS.get(name)
    if t is None:
        return ToolResult(ok=False, error=f"la herramienta '{name}' no existe", ms=0)
    args = {k: v for k, v in (args or {}).items() if k != "cliente_id"}  # nunca confiar en un cliente_id del modelo
    try:
        parsed = t.args_model.model_validate(args)
    except ValidationError as exc:
        return ToolResult(ok=False, error=_fmt_validation(exc), ms=int((time.perf_counter() - t0) * 1000))
    try:
        data = await t.fn(parsed, ctx)
        return ToolResult(ok=True, data=data, ms=int((time.perf_counter() - t0) * 1000))
    except ToolError as exc:
        return ToolResult(ok=False, error=str(exc), ms=int((time.perf_counter() - t0) * 1000))
    except Exception as exc:  # error inesperado → mensaje genérico, sin filtrar internals
        return ToolResult(
            ok=False,
            error=f"error interno de la herramienta ({type(exc).__name__})",
            ms=int((time.perf_counter() - t0) * 1000),
        )


_loaded = False


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    from app.tools import catalogo, clientes, cobros, humano, pedidos, politicas, stock  # noqa: F401
