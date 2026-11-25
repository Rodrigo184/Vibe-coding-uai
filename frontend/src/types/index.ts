// Espejo de los modelos del backend (app/models/*.py).

export type AgentType = 'router' | 'especialista' | 'planner' | 'memoria' | 'hibrido' | 'evaluador' | 'supervisor'
export type Origen = 'estado' | 'usuario' | 'constante'

export interface Variable {
  nombre: string
  descripcion: string
  ejemplo: string
  origen: Origen
}

export interface PromptTemplate {
  system: string
  user: string
  variables: Variable[]
  salida_esperada: string
  salida_schema: Record<string, unknown> | null
}

export interface Limits {
  max_iters: number
  max_tokens_out: number
  timeout_s: number
  temperature: number
  modelo: string | null
}

export interface FlowNodeDef {
  id: string
  label: string
  sub?: string
  kind: NodeKind
  x: number
  y: number
  promptRef?: string
}
export interface FlowEdgeDef {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  label?: string
  kind?: 'loop' | 'fallback'
}
export type NodeKind = 'input' | 'output' | 'llm' | 'tool' | 'memory' | 'rule' | 'judge' | 'human' | 'plan' | 'supervisor'

export interface AgentDef {
  id: string
  tipo: AgentType
  nombre: string
  tagline: string
  color: string
  descripcion: string
  dominio: string | null
  tools: string[]
  acciones_escritura: string[]
  prompt: PromptTemplate
  limits: Limits
  constantes: Record<string, any>
  activo: boolean
  usar_cuando: string[]
  evitar_cuando: string[]
  riesgos: { riesgo: string; guardrail: string }[]
  metricas: string[]
  frameworks: string[]
  flow: { nodes: FlowNodeDef[]; edges: FlowEdgeDef[] }
  version: number
  actualizado: string
  tiene_semilla?: boolean
}

export interface AgentSummary {
  id: string
  tipo: AgentType
  nombre: string
  tagline: string
  color: string
  activo: boolean
  version: number
  tools: string[]
  actualizado: string
}

export interface ToolSpec {
  name: string
  descripcion: string
  escritura: boolean
  parameters: { type: string; properties: Record<string, any>; required?: string[] }
  ejemplo_args: Record<string, any>
}

export interface ToolResult {
  ok: boolean
  data: any
  error: string | null
  ms: number
}

export type TraceType =
  | 'node_start' | 'thought' | 'llm_call' | 'tool_call' | 'tool_result' | 'rule' | 'decision' | 'judge'
  | 'memory' | 'confirm_required' | 'output' | 'error' | 'node_end' | 'final'

export interface TraceEvent {
  seq: number
  ts: number
  run_id: string
  nodo: string
  tipo: TraceType
  titulo: string
  contenido: any
  tokens_in: number
  tokens_out: number
  costo_usd: number
  ms: number
  modelo: string | null
}

export type RunEstado = 'ok' | 'pendiente_confirmacion' | 'humano' | 'error' | 'limite'

export interface RunSummary {
  run_id: string
  sesion_id: string
  cliente_id: string
  mensaje: string
  respuesta: string | null
  agente: string | null
  veredicto: string | null
  acciones: Record<string, any>[]
  costo_usd: number
  latencia_ms: number
  llamadas_llm: number
  estado: RunEstado
  creado: string
  version_agentes: number
  supervisor_id?: string
}

export interface RunDetail {
  summary: RunSummary
  events: TraceEvent[]
  detalle: Record<string, any>
  pendiente?: boolean
}

export interface FinalContent {
  respuesta: string | null
  acciones: Record<string, any>[]
  agente: string | null
  veredicto: string | null
  evaluacion: Record<string, any> | null
  costo_usd: number
  latencia_ms: number
  llamadas_llm: number
  run_id: string
  estado: RunEstado
  accion_pendiente: { tool: string; args: Record<string, any>; descripcion: string } | null
  ticket_id: string | null
  modo_llm?: string
}

export interface Health {
  ok: boolean
  redis: boolean
  openai: boolean
  modo_llm: 'openai' | 'demo' | 'sin_llm'
  modulos: { json: boolean; search: boolean }
  agents_version: number | null
}

export interface AppConfig {
  modelo: string
  modelo_juez: string
  modelos: string[]
  limites: Record<string, number>
  precios: Record<string, { in: number; out: number }>
  modo_llm: string
}

export interface Cliente {
  cliente_id: string
  nombre: string
  tienda: string | null
  canal: string | null
  en_negocio: boolean
}

export interface MemoryView {
  cliente_id: string
  cliente: { nombre: string; tienda: string; canal: string; edad_verificada: boolean; cupo_credito: number } | null
  perfil: { clave: string; valor: string; fuente: string; fecha: string }[]
  episodios: { fecha: string; resumen: string }[]
  sesiones: { sesion_id: string; turnos: { rol: string; texto: string; ts: number }[] }[]
}

export interface EvalCase {
  id: string
  etiqueta: 'normal' | 'borde' | 'adversarial'
  cliente_id: string
  sesion_nueva: boolean
  mensaje: string
  agente_esperado: string | string[] | null
  tools_esperadas: string[]
  respuesta_esperada: string
  reglas_a_verificar: string[]
  debe_pedir_confirmacion: boolean
}

export interface EvalResult {
  case_id: string
  repeticion: number
  etiqueta: string
  mensaje: string
  agente_esperado: string | string[] | null
  agente: string | null
  tools_esperadas: string[]
  tools: string[]
  respuesta: string | null
  veredicto: string | null
  juez: Record<string, any> | null
  reglas_post: { nombre: string; ok: boolean; detalle: string }[]
  pidio_confirmacion: boolean
  debe_pedir_confirmacion: boolean
  derivado_humano: boolean
  estado: string
  costo_usd: number
  latencia_ms: number
  llamadas_llm: number
  run_id: string | null
  ok_enrutamiento: boolean
  ok_tools: boolean | null
  ok_reglas: boolean
  ok_confirmacion: boolean
}

export interface EvalReport {
  id: string
  creado: string
  version_agentes: number
  repeticiones: number
  casos: number
  metricas: Record<string, any>
  por_regla?: Record<string, number>
  resultados?: EvalResult[]
  modo_llm?: string
}

export interface RuleInfo {
  nombre: string
  fase: 'pre' | 'post'
  descripcion: string
}

export interface ChatMessage {
  id: string
  rol: 'user' | 'assistant' | 'system'
  texto: string
  final?: FinalContent
  confirm?: { run_id: string; tool: string; args: Record<string, any>; descripcion: string; resultado?: 'confirmada' | 'cancelada' | 'fallida' }
  pending?: boolean
}
