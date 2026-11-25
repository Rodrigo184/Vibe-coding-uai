"""Wrapper del SDK oficial de OpenAI: chat(), chat_json(schema), chat_tools(tools).

- Reintentos ×2 con backoff ante 429/5xx (SDK `max_retries=2`).
- Timeout por llamada = limits.timeout_s del agente.
- Devuelve LLMResult con tokens, costo (PRICES_JSON), ms y modelo.
- Sin OPENAI_API_KEY → modo DEMO: un LLM simulado determinístico (llm/mock.py) para que la
  plataforma se pueda mostrar completa antes de cargar credenciales.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.costs import cost_usd

_client: Any = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON string tal como lo entrega el modelo

    def args(self) -> dict[str, Any]:
        try:
            v = json.loads(self.arguments or "{}")
            return v if isinstance(v, dict) else {"_raw": v}
        except json.JSONDecodeError:
            return {"_raw": self.arguments}


@dataclass
class LLMResult:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    parsed: Any = None
    tokens_in: int = 0
    tokens_out: int = 0
    costo_usd: float = 0.0
    ms: int = 0
    modelo: str = ""
    demo: bool = False

    def assistant_message(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in self.tool_calls
            ]
        return msg


class LLMError(Exception):
    pass


def _openai() -> Any:
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=get_settings().openai_api_key, max_retries=2)
    return _client


def reset_client() -> None:
    global _client
    _client = None


def default_model() -> str:
    return get_settings().openai_model


async def _call(
    kind: str, messages: list[dict], *, model: str, temperature: float, max_tokens: int, timeout: float, **extra: Any
) -> LLMResult:
    settings = get_settings()
    t0 = time.perf_counter()
    if settings.use_mock_llm:
        from app.llm import mock

        res = mock.respond(kind, messages, model=model, **extra)
        res.ms = int((time.perf_counter() - t0) * 1000) + res.ms
        res.costo_usd = cost_usd(model, res.tokens_in, res.tokens_out)
        res.modelo = f"demo:{model}"
        res.demo = True
        return res
    if not settings.openai_configured:
        raise LLMError("OPENAI_API_KEY no configurada")

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "timeout": timeout,
    }
    # modelos de razonamiento (o1/o3/gpt-5…) no aceptan temperature != 1
    if not model.startswith(("o1", "o3", "o4", "gpt-5")):
        kwargs["temperature"] = temperature
    else:
        kwargs.pop("max_tokens")
        kwargs["max_completion_tokens"] = max_tokens
    if kind == "json":
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": extra["name"], "schema": extra["schema"], "strict": extra.get("strict", True)},
        }
    elif kind == "tools":
        if extra.get("tools"):
            kwargs["tools"] = extra["tools"]
            kwargs["tool_choice"] = extra.get("tool_choice", "auto")

    client = _openai()
    try:
        resp = await client.chat.completions.create(**kwargs)
    except Exception as exc:  # schema no compatible con strict → json_object
        if kind == "json" and "schema" in str(exc).lower():
            kwargs["response_format"] = {"type": "json_object"}
            resp = await client.chat.completions.create(**kwargs)
        else:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

    choice = resp.choices[0].message
    usage = resp.usage
    res = LLMResult(
        content=choice.content,
        tool_calls=[
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments) for c in (choice.tool_calls or [])
        ],
        tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
        tokens_out=getattr(usage, "completion_tokens", 0) or 0,
        ms=int((time.perf_counter() - t0) * 1000),
        modelo=resp.model or model,
    )
    res.costo_usd = cost_usd(model, res.tokens_in, res.tokens_out)
    if kind == "json":
        try:
            res.parsed = json.loads(res.content or "{}")
        except json.JSONDecodeError as exc:
            raise LLMError(f"El modelo devolvió JSON inválido: {exc}") from exc
    return res


async def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
    timeout: float = 12,
) -> LLMResult:
    return await _call(
        "text",
        messages,
        model=model or default_model(),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


async def chat_json(
    messages: list[dict],
    *,
    schema: dict,
    name: str,
    strict: bool = True,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
    timeout: float = 12,
) -> LLMResult:
    return await _call(
        "json",
        messages,
        model=model or default_model(),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        schema=schema,
        name=name,
        strict=strict,
    )


async def chat_tools(
    messages: list[dict],
    *,
    tools: list[dict],
    tool_choice: str = "auto",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
    timeout: float = 12,
    ctx: dict | None = None,
) -> LLMResult:
    return await _call(
        "tools",
        messages,
        model=model or default_model(),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        tools=tools,
        tool_choice=tool_choice,
        ctx=ctx or {},
    )


async def embed(texts: list[str]) -> list[list[float]] | None:
    """Embeddings con OPENAI_EMBED_MODEL; None si no hay clave (se usa búsqueda léxica)."""
    settings = get_settings()
    if not settings.openai_configured:
        return None
    resp = await _openai().embeddings.create(model=settings.openai_embed_model, input=texts)
    return [d.embedding for d in resp.data]
