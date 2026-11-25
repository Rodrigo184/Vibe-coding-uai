"""Agent Explorer Platform — API (FastAPI)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import agents, chat, evals, memory, runs, system, tools
from app.core.config import get_settings
from app.core.redis import detect_modules, ping

log = logging.getLogger("agent-platform")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if await ping():
        mods = await detect_modules()
        log.warning("Redis OK · módulos %s", mods)
        try:
            from app.seed.seed import ensure_seeded

            if await ensure_seeded():
                log.warning("Redis vacío: semilla cargada (negocio + agentes + dataset)")
        except Exception as exc:  # pragma: no cover
            log.error("No se pudo sembrar: %s", exc)
    else:
        log.error("Redis no responde. Revisa REDIS_URL y el estado del servidor.")
    log.warning("LLM: %s", "OpenAI" if s.openai_configured else "MODO DEMO (sin OPENAI_API_KEY): LLM simulado")
    yield


app = FastAPI(title="Agent Explorer Platform", version="1.0.0", lifespan=lifespan)

origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins or ["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"]
)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    return JSONResponse(
        {"error": {"code": str(exc.status_code), "message": str(exc.detail)}}, status_code=exc.status_code
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    msg = "; ".join(f"{'.'.join(str(x) for x in e['loc'] if x != 'body')}: {e['msg']}" for e in exc.errors()[:6])
    return JSONResponse({"error": {"code": "invalid_request", "message": msg}}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
    log.exception("error no controlado")
    return JSONResponse({"error": {"code": "internal", "message": f"{type(exc).__name__}"}}, status_code=500)


for r in (system.router, agents.router, tools.router, chat.router, runs.router, memory.router, evals.router):
    app.include_router(r, prefix="/api")
