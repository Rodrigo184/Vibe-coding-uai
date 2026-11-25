"""Render de prompts con Jinja2 (`{{ }}`, StrictUndefined) + extracción de variables.

Solo `{{identificador}}` es una variable. Cualquier otro uso literal de llaves en un prompt
(p. ej. `{{"$paso": 1}}` en el planner o ejemplos JSON) se protege con bloques raw para que
Jinja lo deje intacto.
"""

from __future__ import annotations

import re
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

VAR_RE = re.compile(r"{{\s*(\w+)\s*}}")
_env = Environment(
    variable_start_string="{{",
    variable_end_string="}}",
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)


class TemplateError(Exception):
    pass


def extraer_variables(texto: str) -> set[str]:
    return set(VAR_RE.findall(texto or ""))


def _to_jinja(texto: str) -> str:
    out: list[str] = []
    pos = 0
    for m in VAR_RE.finditer(texto):
        lit = texto[pos : m.start()]
        out.append(_protect(lit))
        out.append("{{ " + m.group(1) + " }}")
        pos = m.end()
    out.append(_protect(texto[pos:]))
    return "".join(out)


def _protect(lit: str) -> str:
    if any(tok in lit for tok in ("{{", "{%", "{#", "}}", "%}", "#}")):
        return "{% raw %}" + lit + "{% endraw %}"
    return lit


def render(texto: str, variables: dict[str, Any]) -> str:
    """Rinde el prompt. Variable faltante → TemplateError claro (nunca texto vacío)."""
    faltan = sorted(v for v in extraer_variables(texto) if v not in variables)
    if faltan:
        raise TemplateError(f"Variables sin valor: {', '.join(faltan)}")
    try:
        return _env.from_string(_to_jinja(texto)).render(**{k: _fmt(v) for k, v in variables.items()})
    except UndefinedError as exc:  # pragma: no cover - cubierto por la verificación previa
        raise TemplateError(str(exc)) from exc
    except TemplateSyntaxError as exc:
        raise TemplateError(f"Sintaxis de plantilla inválida (línea {exc.lineno}): {exc.message}") from exc


def _fmt(v: Any) -> Any:
    if v is None:
        return "null"
    return v


def render_safe(texto: str, variables: dict[str, Any]) -> tuple[str, list[str]]:
    """Para la UI: rinde y deja `{{var}}` visible para lo que falte (no lanza)."""
    faltan = sorted(v for v in extraer_variables(texto) if v not in variables)
    vals = dict(variables)
    for f in faltan:
        vals[f] = "{{" + f + "}}"
    try:
        return render(texto, vals), faltan
    except TemplateError as exc:
        return texto, [str(exc)]


AISLADO_NO = re.compile(r"(?<![A-Za-zÁÉÍÓÚÑáéíóúñ])NO(?![A-Za-zÁÉÍÓÚÑáéíóúñ])")


def tiene_no_aislado(texto: str) -> bool:
    return bool(AISLADO_NO.search(texto or ""))
