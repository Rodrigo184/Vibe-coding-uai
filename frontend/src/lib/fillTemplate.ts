// Rellena {{variable}} (solo identificadores). Lo faltante queda visible como {{variable}}.
export const VAR_RE = /{{\s*(\w+)\s*}}/g

export function extraerVariables(texto: string): string[] {
  const out = new Set<string>()
  for (const m of texto.matchAll(VAR_RE)) out.add(m[1])
  return [...out]
}

export function fillTemplate(texto: string, vars: Record<string, unknown>): string {
  return texto.replace(VAR_RE, (full, name: string) => (name in vars && vars[name] != null ? String(vars[name]) : full))
}

// Catálogo de variables de estado que provee el runtime (SPEC 7.2), para autocompletar en la UI.
export const VARIABLES_ESTADO: Record<string, string> = {
  nombre_app: 'nombre comercial de la app',
  fecha: 'fecha ISO del turno',
  hora: 'hora local (America/Santiago)',
  canal: 'app / whatsapp / web',
  mensaje: 'texto del usuario',
  solicitud: 'texto del usuario (alias)',
  historial: 'últimos turnos, formato rol: texto',
  perfil: 'JSON de hechos estables del cliente',
  episodios: 'JSON con los últimos 3 resúmenes de sesión',
  tienda: 'código de tienda del cliente',
  tools_json: 'schemas de las tools permitidas',
  lista_especialistas: 'id — dominio — ejemplo (desde el supervisor)',
  motivo: 'motivo del router',
  intenciones_secundarias: 'intenciones secundarias del router',
  veredicto_reglas: 'JSON de las reglas PRE',
  precios_api: 'precios vistos/consultados por el runtime',
  acciones_escritura: 'tools que exigen confirmación',
  max_iters: 'límite de ciclos del agente',
  max_pasos: 'límite de pasos del planner',
  nombre_especialista: 'nombre del agente',
  descripcion_dominio: 'dominio del agente',
  respuesta: 'respuesta a evaluar / extraer',
  contexto: 'contexto para el evaluador',
  tools_resultados: 'tools llamadas y resultados',
  respuesta_esperada: 'referencia del dataset o "ninguna"',
  reglas_negocio: 'reglas del negocio (constante del evaluador)',
  objetivo: 'objetivo del planner',
  cliente: 'id y nombre del cliente',
  resultados_previos: 'plan y resultados previos',
  cliente_id: 'id del cliente',
  sesion_id: 'id de la sesión',
  max_llamadas: 'límite global de llamadas LLM',
  max_costo_usd: 'presupuesto por turno',
  timeout_s: 'timeout total por turno',
}
