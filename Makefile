# Agent Explorer Platform — tareas comunes
SHELL := /bin/bash
BACK := cd backend &&
FRONT := cd frontend &&
UV := uv run
DC := docker compose
BACKEND_PORT := $(or $(shell sed -n 's/^BACKEND_PORT=//p' .env 2>/dev/null),8000)
FRONTEND_PORT := $(or $(shell sed -n 's/^FRONTEND_PORT=//p' .env 2>/dev/null),5173)

.PHONY: help install up down logs ps seed seed-docker reset reset-docker dev dev-back dev-front test test-integration lint build eval eval-docker agentes

help: ## Lista las tareas
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependencias locales (uv + npm)
	@test -f .env || cp .env.example .env
	$(BACK) uv sync --locked --python 3.12 --extra dev
	$(FRONT) npm ci --no-audit --no-fund

up: ## Levanta todo con Docker (redis + backend + frontend) → http://localhost:5173
	@test -f .env || cp .env.example .env
	$(DC) up -d --build
	@echo "Frontend: http://localhost:$(FRONTEND_PORT) · API: http://localhost:$(BACKEND_PORT)/api/health"

down: ## Detiene los contenedores
	$(DC) down

logs: ## Logs del backend
	$(DC) logs -f backend

ps: ## Estado de los contenedores
	$(DC) ps

seed: ## Re-siembra negocio + agentes + dataset (local; no toca memoria de clientes)
	$(BACK) $(UV) python -m app.seed.seed

seed-docker: ## Igual que seed, dentro del contenedor
	$(DC) exec backend python -m app.seed.seed

reset: ## Borra TODO Redis (memoria, runs, reportes) y vuelve a sembrar (local)
	$(BACK) $(UV) python -m app.seed.seed --reset

reset-docker: ## Igual que reset, dentro del contenedor
	$(DC) exec backend python -m app.seed.seed --reset

dev: ## Desarrollo local: Redis en Docker, backend y Vite con recarga
	$(DC) up -d redis
	@trap 'kill 0' EXIT; \
	 ($(MAKE) dev-back) & \
	 ($(MAKE) dev-front) & wait

dev-back: ## Solo backend local con recarga
	$(BACK) $(UV) uvicorn app.main:app --reload --port $(BACKEND_PORT)

dev-front: ## Solo frontend local (vite)
	$(FRONT) VITE_BACKEND_URL=http://127.0.0.1:$(BACKEND_PORT) npm run dev -- --host 127.0.0.1 --port $(FRONTEND_PORT) --strictPort

test: ## Tests unitarios (pytest con fakeredis + vitest)
	$(BACK) $(UV) pytest -q
	$(FRONT) npx vitest run

test-integration: ## Integración real (Redis local + OPENAI_API_KEY_REAL)
	$(BACK) $(UV) pytest -q -m integration

lint: ## ruff + mypy + eslint + tsc
	$(BACK) $(UV) ruff check app tests && $(UV) ruff format --check app tests && $(UV) mypy app
	$(FRONT) npx eslint . && npx tsc -b --noEmit

build: ## Build de producción del frontend + imágenes Docker
	$(FRONT) npm run build
	$(DC) build

eval: ## Corre el dataset de evaluación (local)
	$(BACK) $(UV) python -m app.evals.runner

eval-docker: ## Corre el dataset dentro del contenedor
	$(DC) exec backend python -m app.evals.runner

agentes: ## Regenera seed/agentes.json desde prompts_semilla.txt
	$(BACK) $(UV) python -m app.seed.build_agentes
