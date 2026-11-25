from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.errors import ApiError, not_found
from app.models.tool import ToolResult, ToolSpec
from app.tools import registry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolSpec])
async def list_tools() -> list[ToolSpec]:
    return registry.specs()


class ToolTestIn(BaseModel):
    args: dict[str, Any] = {}
    cliente_id: str = "c42"
    confirm: bool = False


@router.post("/{name}/test", response_model=ToolResult)
async def test_tool(name: str, body: ToolTestIn) -> ToolResult:
    t = registry.get(name)
    if not t:
        raise not_found(f"la herramienta '{name}'")
    if t.spec.escritura and not body.confirm:
        raise ApiError(409, "confirm_required", f"'{name}' es de escritura: envía confirm=true para ejecutarla")
    ctx = registry.ToolContext(cliente_id=body.cliente_id, sesion_id="tools-test", run_id="tools-test")
    return await registry.run_tool(name, body.args, ctx)
