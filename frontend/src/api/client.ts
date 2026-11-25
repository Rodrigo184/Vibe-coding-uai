// Cliente tipado de la API + lector SSE (fetch + ReadableStream). La clave de OpenAI nunca llega aquí.
import type {
  AgentDef, AgentSummary, AppConfig, Cliente, EvalCase, EvalReport, Health, MemoryView, RuleInfo, RunDetail, RunSummary, ToolResult, ToolSpec,
  TraceEvent,
} from '../types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export class ApiError extends Error {
  code: string
  status: number
  constructor(status: number, code: string, message: string) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let code = String(res.status)
    let message = res.statusText
    try {
      const body = await res.json()
      code = body?.error?.code ?? code
      message = body?.error?.message ?? message
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, code, message)
  }
  return res.json() as Promise<T>
}

const json = (body: unknown) => ({ body: JSON.stringify(body) })

export const api = {
  health: () => req<Health>('/health'),
  config: () => req<AppConfig>('/config'),
  rules: () => req<RuleInfo[]>('/rules'),
  seed: (que: string[]) => req<Record<string, unknown>>('/seed', { method: 'POST', ...json({ que }) }),

  agents: () => req<AgentSummary[]>('/agents'),
  agent: (id: string) => req<AgentDef>(`/agents/${encodeURIComponent(id)}`),
  createAgent: (a: Partial<AgentDef>) => req<{ agent: AgentDef; agents_version: number }>('/agents', { method: 'POST', ...json(a) }),
  updateAgent: (a: AgentDef) =>
    req<{ agent: AgentDef; agents_version: number; mensaje: string }>(`/agents/${encodeURIComponent(a.id)}`, { method: 'PUT', ...json(a) }),
  deleteAgent: (id: string) => req<{ ok: boolean }>(`/agents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  restoreAgent: (id: string) => req<{ agent: AgentDef }>(`/agents/${encodeURIComponent(id)}/restore`, { method: 'POST' }),
  validateAgent: (a: Partial<AgentDef> & { _creando?: boolean }) =>
    req<{ ok: boolean; problemas: { nivel: 'error' | 'aviso'; campo: string; mensaje: string }[] }>('/agents/validate', { method: 'POST', ...json(a) }),
  renderAgent: (id: string, agent?: AgentDef, variables: Record<string, unknown> = {}) =>
    req<{ system: string; user: string; faltantes: string[] }>(`/agents/${encodeURIComponent(id)}/render`, { method: 'POST', ...json({ variables, agent }) }),

  tools: () => req<ToolSpec[]>('/tools'),
  testTool: (name: string, args: Record<string, unknown>, cliente_id: string, confirm = false) =>
    req<ToolResult>(`/tools/${name}/test`, { method: 'POST', ...json({ args, cliente_id, confirm }) }),

  runs: (params: { limit?: number; cliente_id?: string; estado?: string } = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== '' && q.set(k, String(v)))
    return req<RunSummary[]>(`/runs?${q.toString()}`)
  },
  run: (id: string) => req<RunDetail>(`/runs/${id}`),
  exportRunUrl: (id: string) => `${BASE}/api/runs/${id}/export`,

  clientes: () => req<Cliente[]>('/memory'),
  memory: (cid: string) => req<MemoryView>(`/memory/${encodeURIComponent(cid)}`),
  putPerfil: (cid: string, hechos: Record<string, string>) =>
    req<{ ok: boolean; descartados: string[] }>(`/memory/${encodeURIComponent(cid)}/perfil`, { method: 'PUT', ...json({ hechos }) }),
  deleteMemory: (cid: string) => req<{ ok: boolean }>(`/memory/${encodeURIComponent(cid)}`, { method: 'DELETE' }),
  cerrarSesion: (cid: string, sid: string) =>
    req<{ ok: boolean; episodio: string }>(`/memory/${encodeURIComponent(cid)}/cerrar_sesion/${encodeURIComponent(sid)}`, { method: 'POST' }),

  dataset: () => req<EvalCase[]>('/evals/dataset'),
  putDataset: (cases: EvalCase[]) => req<{ ok: boolean }>('/evals/dataset', { method: 'PUT', ...json(cases) }),
  addCase: (c: EvalCase) => req<{ ok: boolean }>('/evals/dataset/cases', { method: 'POST', ...json(c) }),
  reports: () => req<EvalReport[]>('/evals/reports'),
  report: (id: string) => req<EvalReport>(`/evals/reports/${id}`),
}

/** POST con respuesta text/event-stream: invoca onEvent por cada `data:` JSON. */
export async function postSSE<T = unknown>(path: string, body: unknown, onEvent: (ev: T) => void, signal?: AbortSignal): Promise<void> {
  const res = await fetch(`${BASE}/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) {
    let message = res.statusText
    try {
      const b = await res.json()
      message = b?.error?.message ?? message
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, 'sse_error', message)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    let idx: number
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      const data = block
        .split('\n')
        .filter((l) => l.startsWith('data:'))
        .map((l) => l.slice(5).trimStart())
        .join('\n')
      if (!data) continue
      try {
        onEvent(JSON.parse(data) as T)
      } catch {
        /* evento no JSON (ping) */
      }
    }
  }
}

export const chatSSE = (
  body: { cliente_id: string; sesion_id: string; mensaje: string; supervisor_id?: string; forzar_agente?: string },
  onEvent: (e: TraceEvent) => void,
  signal?: AbortSignal,
) => postSSE<TraceEvent>('/chat', body, onEvent, signal)

export const confirmSSE = (run_id: string, confirmar: boolean, onEvent: (e: TraceEvent) => void) =>
  postSSE<TraceEvent>('/chat/confirm', { run_id, confirmar }, onEvent)
