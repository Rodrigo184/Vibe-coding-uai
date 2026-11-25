import { describe, expect, it } from 'vitest'
import type { AgentDef } from '../types'
import { exportTxt } from './exportPrompts'
import { extraerVariables, fillTemplate } from './fillTemplate'
import { flowDesdeTipo } from './flowLayout'

const agent = {
  id: 'logistica', tipo: 'especialista', nombre: 'Logística', tagline: '', color: 'teal', descripcion: '', dominio: 'envíos',
  tools: ['consultar_stock', 'agregar_item'], acciones_escritura: ['agregar_item'],
  prompt: { system: 'Hola {{nombre_app}} {{"$paso": 1}}', user: '{{mensaje}}', variables: [{ nombre: 'mensaje', descripcion: 'd', ejemplo: 'e', origen: 'estado' }], salida_esperada: 'x', salida_schema: null },
  limits: { max_iters: 5, max_tokens_out: 800, timeout_s: 12, temperature: 0, modelo: null }, constantes: {}, activo: true,
  usar_cuando: [], evitar_cuando: [], riesgos: [], metricas: [], frameworks: [], flow: { nodes: [], edges: [] }, version: 1, actualizado: '',
} as AgentDef

describe('fillTemplate', () => {
  it('rellena variables y deja visibles las faltantes', () => {
    expect(fillTemplate('{{a}} y {{ b }}', { a: 'x' })).toBe('x y {{ b }}')
  })
  it('extrae solo identificadores', () => {
    expect(extraerVariables(agent.prompt.system)).toEqual(['nombre_app'])
  })
})

describe('flowDesdeTipo', () => {
  it('genera nodos de tools y marca escritura', () => {
    const f = flowDesdeTipo(agent)
    expect(f.nodes.filter((n) => n.kind === 'tool')).toHaveLength(2)
    expect(f.edges.some((e) => e.label === 'solo con confirmación')).toBe(true)
  })
})

describe('exportTxt', () => {
  it('usa el formato de la sección 13', () => {
    const txt = exportTxt([agent], [], 7)
    expect(txt).toContain('versión de agentes: 7')
    expect(txt).toContain('############## 1 · LOGISTICA · ESPECIALISTA · Logística ##############')
    expect(txt).toContain('agregar_item (escritura·confirmación)')
    expect(txt).toContain('--- LÍMITES ---')
  })
})
