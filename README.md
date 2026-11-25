# Agent Explorer Platform

Plataforma de agentes de IA **dinámicos**: los agentes son datos (se crean y editan desde la UI y se guardan en **Redis**), se ejecutan con la **API de OpenAI** (tool calling nativo + salidas JSON validadas), usan **herramientas reales** sobre un supermercado de juguete, recuerdan a cada cliente, pasan por **reglas en código** y por un **evaluador LLM-as-judge**, y cada turno se ve **en vivo** como un *flow* animado con su traza.

> Sesión 4 · Agent Tech · Certificado Profesional en AI Context & Vibe Engineering 2026 · UAI + XeraX

## Inicio rápido (Docker)

La demo de este workspace está configurada en **http://localhost:5174**. La API responde en **http://localhost:8001/api/health** y la documentación está en **http://localhost:8001/docs**. Docker publica los tres puertos en `127.0.0.1` y conserva los datos de la demo en su propio volumen de Redis.

```bash
test -f .env || cp .env.example .env
docker compose up -d --build --wait
```

Una copia nueva de `.env.example` usa los puertos 5173, 8000 y 6379. Puedes cambiarlos con `FRONTEND_PORT`, `BACKEND_PORT` y `REDIS_PORT`. Si cambias el puerto de Redis, ajusta también `REDIS_URL` para los comandos que se ejecutan en el host. El backend carga automáticamente el negocio, los agentes y el dataset cuando Redis está vacío.

### Modo demo (sin `OPENAI_API_KEY`)

Si `OPENAI_API_KEY` está vacía, la plataforma usa un **LLM simulado determinístico** (`backend/app/llm/mock.py`). Todo lo demás es real: Redis, tools sobre datos del negocio, confirmaciones, reglas PRE/POST, memoria, runs y evaluaciones. El header muestra `OpenAI · demo` en ámbar. Para pasar a modelos reales:

```bash
# edita .env → OPENAI_API_KEY=sk-...
docker compose up -d --wait backend  # recrea el backend con la nueva variable
```

Para activar la búsqueda semántica sobre las políticas ya cargadas, ejecuta `docker compose exec backend python -m app.seed.seed --indexar-politicas`. El comando actualiza los embeddings de las políticas existentes y conserva los pedidos, cobros y memoria de la demo.

## Desarrollo local

Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22 o superior, Git y Docker Desktop con Compose. Para usar el modo de desarrollo con recarga, detén primero `frontend` y `backend` de esta demo con `docker compose stop frontend backend`.

```bash
make install     # dependencias fijadas por uv.lock y package-lock.json, crea .env si falta
make dev         # Redis en Docker + Uvicorn y Vite con recarga en los puertos de .env
make seed        # re-siembra negocio, agentes y dataset (no toca memoria de clientes)
make reset       # borra TODO Redis (memoria, runs, reportes) y vuelve a sembrar
make test        # pytest (fakeredis, LLM mockeado) + vitest
make lint        # ruff + mypy + eslint + tsc
make build       # build del frontend + imágenes docker
make eval        # corre el dataset de evaluación y guarda el reporte
```

## Arquitectura

```
frontend (Vite + React + TS)  ──SSE/REST /api──►  backend (FastAPI · Python 3.12)  ──►  Redis (agentes, memoria, runs, negocio)
  Playground · Agentes · Tools                       api/ engine/ tools/ rules/          OpenAI (chat + tools + json_schema + embeddings)
  Runs · Memoria · Evaluación · Prompts              memory/ evals/ llm/ seed/
```

Flujo de un turno (`POST /api/chat`, eventos SSE `TraceEvent`):

`memoria → reglas PRE → router → (especialista | planner | humano) → tools → reglas POST → evaluador → extractor de memoria → final`

- **Escrituras con confirmación**: si el especialista pide una tool de escritura, el turno se pausa (`confirm_required`, `estado=pendiente_confirmacion`) y la acción queda en `run:{id}:pendiente` 15 min; `POST /api/chat/confirm` la ejecuta o cancela y continúa el turno.
- **Límites globales** por turno (`MAX_LLM_CALLS_PER_TURN`, `MAX_TURN_COST_USD`, `MAX_TURN_SECONDS`) → corte limpio con `estado=limite`; nunca un 500 a medio stream.
- Los prompts docentes se importan de `backend/app/seed/prompts_semilla.txt`, una copia de `Sesion4_Prompts_Agentes.txt`. `make agentes` vuelve a generar las definiciones y `make seed-docker` carga las definiciones generadas en Redis.
- **Aislamiento por cliente**: toda tool usa `ctx.cliente_id`; un `cliente_id` que venga del modelo se descarta.
- **Prompt injection**: resultados de tools viajan como mensajes `tool` (datos), nunca concatenados al `system`.

Estructura: ver `backend/app/*` (sección 4 del SPEC). Claves de Redis: sección 5.3.

## Cómo agregar un agente (UI, sin desplegar)

1. **Agentes → Nuevo agente**: tipo → nombre y dominio → tools. Se crea desde la plantilla de semilla del tipo.
2. Ajusta el prompt (pestaña *Prompt*), **Validar** detecta variables no declaradas, tools inexistentes, “NO” aislado y JSON schema inválido. **Ver con ejemplo** renderiza el prompt.
3. Abre el **supervisor → Pipeline** y agrega el id a *Especialistas*. Guarda: `agents:version` sube y el próximo turno ya enruta hacia él (sin reiniciar el backend).
4. Pestaña **Probar**: chatea solo con ese agente (router fijado).

## Cómo agregar una tool (código)

```python
# backend/app/tools/logistica.py
class EstimarDespachoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tienda: Literal["LC", "PR", "VI"]

@tool("estimar_despacho", "Ventana de despacho estimada para la tienda.", escritura=False, ejemplo={"tienda": "LC"})
async def estimar_despacho(args: EstimarDespachoArgs, ctx: ToolContext) -> dict:
    return {"ventana": "mañana 10:00–14:00"}
```

Importa el módulo en `_ensure_loaded()` de `tools/registry.py`. El decorador genera el JSON Schema para OpenAI, valida argumentos (errores claros para el modelo) y la expone en `/api/tools` y en la UI.

## Evaluación

- Dataset de 50 casos (`backend/app/seed/dataset.json`: 30 de la sección 11.2 + 20 adicionales; 60 % normales, 24 % borde, 16 % adversariales), editable en **Evaluación**.
- Cada caso usa una sesión nueva y lee el perfil y los episodios del cliente. El reporte conserva la traza y registra las solicitudes de confirmación sin aplicarlas al negocio ni escribir en la memoria del cliente.
- Métricas (sección 11.3): precisión de enrutamiento, de tools, precisión del juez, consistencia (≥2 repeticiones), cumplimiento de reglas (también por regla), confirmación correcta, derivación a humano, costo, latencia p50/p95 y llamadas LLM. Semáforo: precisión ≥ 0,90 · cumplimiento = 1,0 · derivación < 10 %.

## Despliegue

- **Backend** (Render / Fly.io / Railway): imagen `backend/Dockerfile`. Variables: las de `.env.example` (`REDIS_URL` apuntando a Redis Cloud, `CORS_ORIGINS` con el dominio del frontend). Health: `/api/health`.
- **Frontend** (Vercel / Netlify): `cd frontend && npm run build`, publicar `dist/`. Define `VITE_API_URL=https://tu-backend` en el build, o usa la imagen `frontend/Dockerfile` (nginx con proxy `/api` y SSE sin buffer).
- **Redis Cloud** (o Upstash): Redis Stack recomendado; si no hay módulo JSON, el JSON se guarda como string (se detecta al iniciar).
- Tras el primer despliegue: `python -m app.seed.seed` (o `POST /api/seed`).

## Decisiones (lo ambiguo del SPEC, resuelto a lo más simple)

- **Modo demo** sin clave (`DEMO_MODE_WITHOUT_KEY=true`): permite mostrar la plataforma completa antes de cargar credenciales.
- `consultar_stock` acepta también `skus: [...]` (opcional) y `historial_pedidos` devuelve `promedio_items`/`skus` y acepta `excluir`, para que el planner pueda encadenar pasos con referencias `{"$paso": n, "campo": "skus"}`.
- `agregar_item` acepta `pedido_id="actual"` (próximo pedido abierto del cliente), útil para el agente híbrido de ventas.
- El especialista `pedidos` incluye `buscar_producto` (el caso ped-02 lo espera).
- `cupo_credito` bloquea con cupo ≤ 0 (el caso ven-03 tiene cupo 0).
- El caso `fin-02` se reformuló con contexto (“…del cobro duplicado del pedido 8812”) porque cada caso corre en sesión nueva.
- La parte A del prompt del extractor se inyecta como `[MEMORIA DISPONIBLE]` en todo especialista; la B se usa para hechos y la C para episodios. El planner separa su `system` en planificador y `[VERIFICADOR]`.
- Las llamadas LLM de la continuación tras confirmar tienen su propio presupuesto de llamadas; el costo se acumula en el mismo run.
- Langfuse es opcional y no se instala por defecto (`pip install langfuse` + variables `LANGFUSE_*`).
