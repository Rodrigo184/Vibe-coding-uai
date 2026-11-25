import type { AgentDef, AgentType, FlowEdgeDef, FlowNodeDef } from '../types'

// Flow estándar por tipo de agente (botón "Regenerar desde el tipo").
export function flowDesdeTipo(agent: Pick<AgentDef, 'id' | 'tipo' | 'nombre' | 'tools' | 'acciones_escritura'>): { nodes: FlowNodeDef[]; edges: FlowEdgeDef[] } {
  const tipo: AgentType = agent.tipo
  const kindAgente = tipo === 'planner' || tipo === 'memoria' ? 'plan' : tipo === 'evaluador' ? 'judge' : tipo === 'supervisor' ? 'supervisor' : 'llm'
  const nodes: FlowNodeDef[] = [
    { id: 'in', label: 'Entrada', sub: 'mensaje + contexto', kind: 'input', x: 40, y: 220 },
  ]
  const edges: FlowEdgeDef[] = []
  let entrada = 'in'
  if (tipo === 'hibrido') {
    nodes.push({ id: 'pre', label: 'Reglas PRE', sub: 'código', kind: 'rule', x: 300, y: 220 })
    edges.push({ id: 'e-pre', source: 'in', target: 'pre' })
    entrada = 'pre'
  }
  const xAg = tipo === 'hibrido' ? 560 : 320
  nodes.push({ id: 'ag', label: agent.nombre || agent.id, sub: tipo, kind: kindAgente, x: xAg, y: 220, promptRef: agent.id })
  edges.push({ id: 'e-in', source: entrada, target: 'ag' })
  agent.tools.forEach((t, i) => {
    const w = agent.acciones_escritura.includes(t)
    nodes.push({ id: `t${i}`, label: t, sub: w ? 'escritura · confirma' : 'lectura', kind: 'tool', x: xAg + 300, y: 40 + i * 110 })
    edges.push({ id: `e-t${i}`, source: 'ag', target: `t${i}`, label: w ? 'solo con confirmación' : undefined })
    if (!w) edges.push({ id: `e-t${i}b`, source: `t${i}`, target: 'ag', kind: 'loop' })
  })
  const xOut = xAg + (agent.tools.length ? 600 : 300)
  if (tipo === 'hibrido' || tipo === 'especialista') {
    nodes.push({ id: 'post', label: 'Reglas POST', sub: 'precios · formato', kind: 'rule', x: xOut, y: 220 })
    edges.push({ id: 'e-post', source: 'ag', target: 'post' })
    nodes.push({ id: 'out', label: 'Respuesta', sub: 'verificada', kind: 'output', x: xOut + 260, y: 220 })
    edges.push({ id: 'e-out', source: 'post', target: 'out' })
  } else {
    nodes.push({ id: 'out', label: 'Salida', sub: tipo === 'router' || tipo === 'evaluador' ? 'JSON validado' : 'resultado', kind: 'output', x: xOut, y: 220 })
    edges.push({ id: 'e-out', source: 'ag', target: 'out' })
  }
  return { nodes, edges }
}

// Pipeline del supervisor para el Playground (especialistas agrupados en un nodo).
export const PIPELINE_FLOW: { nodes: FlowNodeDef[]; edges: FlowEdgeDef[] } = {
  nodes: [
    { id: 'memoria', label: 'Memoria', sub: 'historial · perfil · episodios', kind: 'memory', x: 0, y: 0 },
    { id: 'reglas_pre', label: 'Reglas PRE', sub: 'edad · cupo · horario', kind: 'rule', x: 234, y: 0 },
    { id: 'router', label: 'Router', sub: 'clasifica la intención', kind: 'llm', x: 468, y: 0 },
    { id: 'especialista', label: 'Especialista', sub: 'elegido por el router', kind: 'llm', x: 234, y: 121 },
    { id: 'planner', label: 'Planner', sub: 'planifica y verifica', kind: 'plan', x: 468, y: 121 },
    { id: 'humano', label: 'Humano', sub: 'derivación con ticket', kind: 'human', x: 468, y: 255 },
    { id: 'tools', label: 'Tools', sub: 'lectura · escritura confirmada', kind: 'tool', x: 0, y: 121 },
    { id: 'reglas_post', label: 'Reglas POST', sub: 'precios · formato · privacidad', kind: 'rule', x: 0, y: 255 },
    { id: 'evaluador', label: 'Evaluador', sub: 'verifica la respuesta', kind: 'judge', x: 234, y: 255 },
    { id: 'extractor', label: 'Extractor', sub: 'actualiza el perfil', kind: 'memory', x: 234, y: 371 },
    { id: 'final', label: 'Respuesta', sub: 'texto y acciones', kind: 'output', x: 0, y: 371 },
  ],
  edges: [
    { id: 'memoria->reglas_pre', source: 'memoria', target: 'reglas_pre' },
    { id: 'reglas_pre->router', source: 'reglas_pre', target: 'router' },
    { id: 'reglas_pre->humano', source: 'reglas_pre', target: 'humano', sourceHandle: 'bottom', targetHandle: 'top', kind: 'fallback' },
    { id: 'router->especialista', source: 'router', target: 'especialista', sourceHandle: 'bottom', targetHandle: 'top' },
    { id: 'router->planner', source: 'router', target: 'planner', sourceHandle: 'bottom', targetHandle: 'top' },
    { id: 'router->humano', source: 'router', target: 'humano', sourceHandle: 'right', targetHandle: 'right', kind: 'fallback' },
    { id: 'especialista->tools', source: 'especialista', target: 'tools', sourceHandle: 'left', targetHandle: 'right' },
    { id: 'tools->especialista', source: 'tools', target: 'especialista', sourceHandle: 'top', targetHandle: 'top', kind: 'loop' },
    { id: 'planner->tools', source: 'planner', target: 'tools', sourceHandle: 'bottom', targetHandle: 'bottom' },
    { id: 'especialista->reglas_post', source: 'especialista', target: 'reglas_post', sourceHandle: 'bottom', targetHandle: 'top' },
    { id: 'planner->reglas_post', source: 'planner', target: 'reglas_post', sourceHandle: 'bottom', targetHandle: 'top' },
    { id: 'reglas_post->evaluador', source: 'reglas_post', target: 'evaluador' },
    { id: 'evaluador->especialista', source: 'evaluador', target: 'especialista', sourceHandle: 'top', targetHandle: 'bottom', kind: 'loop' },
    { id: 'evaluador->humano', source: 'evaluador', target: 'humano', kind: 'fallback' },
    { id: 'evaluador->extractor', source: 'evaluador', target: 'extractor', sourceHandle: 'bottom', targetHandle: 'top' },
    { id: 'humano->extractor', source: 'humano', target: 'extractor', sourceHandle: 'bottom', targetHandle: 'right' },
    { id: 'extractor->final', source: 'extractor', target: 'final', sourceHandle: 'left', targetHandle: 'right' },
    { id: 'humano->final', source: 'humano', target: 'final', sourceHandle: 'bottom', targetHandle: 'bottom', kind: 'fallback' },
  ],
}

export const KIND_COLOR: Record<string, string> = {
  input: 'green', output: 'green', llm: 'teal', tool: 'amber', memory: 'violet', rule: 'amber', judge: 'red', human: 'red', plan: 'violet', supervisor: 'ink',
}
