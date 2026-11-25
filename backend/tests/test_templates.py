from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.engine import templates

SEED = Path(__file__).parents[1] / "app" / "seed"


def test_render_ok():
    assert templates.render("Hola {{ nombre }}", {"nombre": "Camila"}) == "Hola Camila"


def test_variable_faltante_error_claro():
    with pytest.raises(templates.TemplateError, match="Variables sin valor: cliente"):
        templates.render("Hola {{cliente}}", {})


def test_llaves_literales_se_respetan():
    txt = 'Reutiliza por referencia {{"$paso": 1}} y {"a": {"b": 1}} con {{x}}'
    out = templates.render(txt, {"x": "ok"})
    assert '{{"$paso": 1}}' in out and out.endswith("con ok")


def test_extraer_variables():
    assert templates.extraer_variables('{{a}} {{ b }} {{"$paso": 1}}') == {"a", "b"}


def test_no_aislado():
    assert templates.tiene_no_aislado("NO hagas eso")
    assert not templates.tiene_no_aislado("Nunca hagas eso. NOTA: ok. no minúscula")


def test_prompts_de_semilla_sin_no_aislado_y_variables_declaradas():
    agentes = json.loads((SEED / "agentes.json").read_text(encoding="utf-8"))
    assert len(agentes) == 11
    for a in agentes:
        for campo in ("system", "user"):
            assert not templates.tiene_no_aislado(a["prompt"][campo]), f"{a['id']}.{campo} contiene NO aislado"
        usadas = templates.extraer_variables(a["prompt"]["system"]) | templates.extraer_variables(a["prompt"]["user"])
        declaradas = {v["nombre"] for v in a["prompt"]["variables"]}
        assert usadas <= declaradas, f"{a['id']}: {usadas - declaradas}"


def test_prompts_copiados_textualmente():
    txt = (SEED / "prompts_semilla.txt").read_text(encoding="utf-8")
    agentes = json.loads((SEED / "agentes.json").read_text(encoding="utf-8"))
    for a in agentes:
        assert a["prompt"]["system"] in txt, a["id"]
        assert a["prompt"]["user"] in txt, a["id"]
