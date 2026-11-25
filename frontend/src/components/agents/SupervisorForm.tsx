import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, X } from 'lucide-react'
import { api } from '../../api/client'
import type { AgentDef } from '../../types'
import { PromptEditor } from './PromptEditor'

export function SupervisorForm({ agent, onChange }: { agent: AgentDef; onChange: (c: Record<string, any>) => void }) {
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: api.agents })
  const { data: rules = [] } = useQuery({ queryKey: ['rules'], queryFn: api.rules })
  const c = agent.constantes
  const set = (k: string, v: unknown) => onChange({ ...c, [k]: v })
  const of = (tipos: string[]) => agents.filter((a) => tipos.includes(a.tipo))
  const esp: string[] = c.especialistas ?? []
  const candidatos = agents.filter((a) => ['especialista', 'hibrido', 'planner'].includes(a.tipo) && !esp.includes(a.id))
  const move = (i: number, d: -1 | 1) => {
    const n = [...esp]
    const j = i + d
    if (j < 0 || j >= n.length) return
    ;[n[i], n[j]] = [n[j], n[i]]
    set('especialistas', n)
  }
  const sel = (k: string, tipos: string[], label: string) => (
    <div>
      <label htmlFor={`sup-${k}`} className="label">
        {label}
      </label>
      <select id={`sup-${k}`} className="input" value={c[k] ?? ''} onChange={(e) => set(k, e.target.value)}>
        {of(tipos).map((a) => (
          <option key={a.id} value={a.id}>
            {a.id} · {a.nombre}
          </option>
        ))}
      </select>
    </div>
  )
  const reglas = (fase: 'pre' | 'post') => {
    const actual: string[] = c[`reglas_${fase}`] ?? []
    return (
      <fieldset>
        <legend className="label">Reglas {fase.toUpperCase()} (código)</legend>
        <div className="space-y-1.5">
          {rules
            .filter((r) => r.fase === fase)
            .map((r) => (
              <label key={r.nombre} className="flex cursor-pointer items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 accent-amber"
                  checked={actual.includes(r.nombre)}
                  onChange={(e) => set(`reglas_${fase}`, e.target.checked ? [...actual, r.nombre] : actual.filter((x) => x !== r.nombre))}
                />
                <span>
                  <span className="font-mono text-[13px] font-semibold">{r.nombre}</span>
                  <span className="muted block text-xs">{r.descripcion}</span>
                </span>
              </label>
            ))}
        </div>
      </fieldset>
    )
  }
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        {sel('router_id', ['router'], 'Router')}
        {sel('evaluador_id', ['evaluador'], 'Evaluador')}
        {sel('extractor_id', ['memoria'], 'Extractor de memoria')}
      </div>
      <div>
        <p className="label">Especialistas (orden = lista que ve el router)</p>
        <ol className="space-y-1">
          {esp.map((id, i) => (
            <li key={id} className="flex items-center gap-2 rounded-lg border border-line px-2 py-1 dark:border-night-line">
              <span className="muted w-5 text-right text-xs tabular">{i + 1}</span>
              <span className="flex-1 font-mono text-[13px]">{id}</span>
              <button type="button" className="btn-icon h-8 w-8" aria-label={`Subir ${id}`} onClick={() => move(i, -1)}>
                <ArrowUp size={14} aria-hidden />
              </button>
              <button type="button" className="btn-icon h-8 w-8" aria-label={`Bajar ${id}`} onClick={() => move(i, 1)}>
                <ArrowDown size={14} aria-hidden />
              </button>
              <button type="button" className="btn-icon h-8 w-8" aria-label={`Quitar ${id}`} onClick={() => set('especialistas', esp.filter((x) => x !== id))}>
                <X size={14} aria-hidden />
              </button>
            </li>
          ))}
        </ol>
        {candidatos.length > 0 && (
          <select aria-label="Agregar especialista" className="input mt-2 max-w-xs" value="" onChange={(e) => e.target.value && set('especialistas', [...esp, e.target.value])}>
            <option value="">+ agregar especialista…</option>
            {candidatos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.id} · {a.nombre}
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        {reglas('pre')}
        {reglas('post')}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <label htmlFor="sup-umbral" className="label">
            umbral_confianza
          </label>
          <input id="sup-umbral" type="number" step={0.05} min={0} max={1} className="input tabular" value={c.umbral_confianza ?? 0.6} onChange={(e) => set('umbral_confianza', Number(e.target.value))} />
        </div>
        <div>
          <label htmlFor="sup-regen" className="label">
            max_regeneraciones
          </label>
          <input id="sup-regen" type="number" min={0} max={3} className="input tabular" value={c.max_regeneraciones ?? 1} onChange={(e) => set('max_regeneraciones', Number(e.target.value))} />
        </div>
        <div>
          <label htmlFor="sup-app" className="label">
            nombre_app
          </label>
          <input id="sup-app" className="input" value={c.nombre_app ?? ''} onChange={(e) => set('nombre_app', e.target.value)} />
        </div>
      </div>
      <div>
        <label htmlFor="sup-humano" className="label">
          mensaje_humano <span className="normal-case">(usa {'{ticket_id}'})</span>
        </label>
        <textarea id="sup-humano" rows={2} className="input" value={c.mensaje_humano ?? ''} onChange={(e) => set('mensaje_humano', e.target.value)} />
      </div>
      <div>
        <p className="label">bloque_tools · se inyecta como [CÓMO USAR LAS HERRAMIENTAS] en todo agente con tools</p>
        <PromptEditor label="Bloque de uso de herramientas" value={c.bloque_tools ?? ''} onChange={(v) => set('bloque_tools', v)} minHeight="90px" />
      </div>
    </div>
  )
}
