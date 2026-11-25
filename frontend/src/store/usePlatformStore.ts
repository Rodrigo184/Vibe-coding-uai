import { create } from 'zustand'
import type { ChatMessage, TraceEvent } from '../types'

const nuevaSesion = () => `s-${Math.random().toString(36).slice(2, 8)}`

function lsGet(k: string, d: string): string {
  try {
    return localStorage.getItem(k) ?? d
  } catch {
    return d
  }
}
function lsSet(k: string, v: string) {
  try {
    localStorage.setItem(k, v)
  } catch {
    /* almacenamiento bloqueado */
  }
}

export type NodeStatus = 'idle' | 'active' | 'done' | 'error'

interface PlatformState {
  dark: boolean
  toggleDark: () => void

  clienteId: string
  sesionId: string
  setCliente: (id: string) => void
  nuevaSesion: () => void

  messages: ChatMessage[]
  addMessage: (m: ChatMessage) => void
  patchMessage: (id: string, patch: Partial<ChatMessage>) => void

  events: TraceEvent[]
  pushEvent: (e: TraceEvent) => void
  clearTrace: () => void
  busy: boolean
  setBusy: (b: boolean) => void

  nodeStatus: Record<string, NodeStatus>
  lastNode: string | null
  visitedEdges: string[]
  agenteElegido: string | null
  toolFlash: string | null
  lastLlmByNode: Record<string, TraceEvent>
  resetFlow: () => void

  selectedNode: string | null
  selectNode: (id: string | null) => void
  helpOpen: boolean
  setHelp: (b: boolean) => void
}

// Mapea el nodo del evento (p. ej. "financiero") al nodo del pipeline en el canvas.
export const PIPELINE_NODES = ['memoria', 'reglas_pre', 'router', 'especialista', 'planner', 'humano', 'tools', 'reglas_post', 'evaluador', 'extractor', 'final']

export function canvasNode(nodo: string, planner = 'planner'): string {
  if (PIPELINE_NODES.includes(nodo)) return nodo
  if (nodo === planner) return 'planner'
  return 'especialista'
}

export const usePlatformStore = create<PlatformState>((set, get) => ({
  dark: typeof document !== 'undefined' && document.documentElement.classList.contains('dark'),
  toggleDark: () => {
    const dark = !get().dark
    document.documentElement.classList.toggle('dark', dark)
    lsSet('aep-theme', dark ? 'dark' : 'light')
    set({ dark })
  },

  clienteId: lsGet('aep-cliente', 'c42'),
  sesionId: nuevaSesion(),
  setCliente: (id) => {
    lsSet('aep-cliente', id)
    set({ clienteId: id, sesionId: nuevaSesion(), messages: [], events: [] })
    get().resetFlow()
  },
  nuevaSesion: () => {
    set({ sesionId: nuevaSesion(), messages: [], events: [] })
    get().resetFlow()
  },

  messages: [],
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  patchMessage: (id, patch) => set((s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)) })),

  events: [],
  pushEvent: (e) =>
    set((s) => {
      const target = canvasNode(e.nodo)
      const nodeStatus = { ...s.nodeStatus }
      const visited = [...s.visitedEdges]
      let agenteElegido = s.agenteElegido
      let toolFlash = s.toolFlash
      const lastLlmByNode = { ...s.lastLlmByNode }
      let lastNode = s.lastNode
      if (e.tipo === 'node_start') {
        // el nodo previo activo pasa a 'done' y se marca la arista recorrida
        const prev = s.lastNode
        if (prev && prev !== target) {
          if (nodeStatus[prev] === 'active') nodeStatus[prev] = 'done'
          visited.push(`${prev}->${target}`)
        }
        lastNode = target
        nodeStatus[target] = 'active'
        if (target === 'especialista' || target === 'planner') agenteElegido = e.nodo
      }
      if (e.tipo === 'tool_call') {
        const from = s.lastNode
        if (from && from !== 'tools') visited.push(`${from}->tools`, `tools->${from}`)
        nodeStatus.tools = 'done'
        toolFlash = e.contenido?.tool ?? e.titulo
      }
      if (e.tipo === 'node_end') nodeStatus[target] = nodeStatus[target] === 'error' ? 'error' : 'done'
      if (e.tipo === 'error') nodeStatus[target] = 'error'
      if (e.tipo === 'llm_call') lastLlmByNode[target] = e
      if (e.tipo === 'final') {
        Object.keys(nodeStatus).forEach((k) => nodeStatus[k] === 'active' && (nodeStatus[k] = 'done'))
        if (s.lastNode && s.lastNode !== 'final') visited.push(`${s.lastNode}->final`)
        lastNode = 'final'
        nodeStatus.final = e.contenido?.estado === 'error' ? 'error' : 'done'
      }
      return { events: [...s.events, e], nodeStatus, visitedEdges: visited, agenteElegido, toolFlash, lastLlmByNode, lastNode }
    }),
  clearTrace: () => set({ events: [] }),
  busy: false,
  setBusy: (b) => set({ busy: b }),

  nodeStatus: {},
  lastNode: null,
  visitedEdges: [],
  agenteElegido: null,
  toolFlash: null,
  lastLlmByNode: {},
  resetFlow: () => set({ nodeStatus: {}, lastNode: null, visitedEdges: [], agenteElegido: null, toolFlash: null, lastLlmByNode: {} }),

  selectedNode: null,
  selectNode: (id) => set({ selectedNode: id }),
  helpOpen: false,
  setHelp: (b) => set({ helpOpen: b }),
}))
