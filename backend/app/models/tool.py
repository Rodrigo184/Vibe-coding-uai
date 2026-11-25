from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ToolSpec(BaseModel):
    name: str
    descripcion: str
    escritura: bool
    parameters: dict[str, Any]
    ejemplo_args: dict[str, Any] = {}


class ToolResult(BaseModel):
    ok: bool
    data: Any | None = None
    error: str | None = None
    ms: int = 0


class ToolCallRecord(BaseModel):
    name: str
    args: dict[str, Any]
    result: ToolResult
    escritura: bool = False
    confirmada: bool = False
