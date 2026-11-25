import { Plus, Trash2, Wand2 } from 'lucide-react'
import { VARIABLES_ESTADO, extraerVariables } from '../../lib/fillTemplate'
import type { AgentDef, Origen, Variable } from '../../types'

export function VariablesTable({ agent, onChange }: { agent: AgentDef; onChange: (vars: Variable[], constantes?: Record<string, any>) => void }) {
  const vars = agent.prompt.variables
  const usadas = new Set([...extraerVariables(agent.prompt.system), ...extraerVariables(agent.prompt.user)])
  const declaradas = new Set(vars.map((v) => v.nombre))
  const faltan = [...usadas].filter((v) => !declaradas.has(v))

  const set = (i: number, patch: Partial<Variable>) => onChange(vars.map((v, j) => (j === i ? { ...v, ...patch } : v)))
  const autocompletar = () =>
    onChange([
      ...vars,
      ...faltan.map((n) => ({ nombre: n, descripcion: VARIABLES_ESTADO[n] ?? '', ejemplo: '', origen: (n in VARIABLES_ESTADO ? 'estado' : 'constante') as Origen })),
    ])

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">Variables del prompt</h3>
        {faltan.length > 0 && (
          <button type="button" className="btn-secondary !min-h-[30px] text-xs" onClick={autocompletar}>
            <Wand2 size={13} aria-hidden /> Declarar {faltan.length} faltante(s): {faltan.join(', ')}
          </button>
        )}
        <button
          type="button"
          className="btn-ghost ml-auto !min-h-[30px] text-xs"
          onClick={() => onChange([...vars, { nombre: '', descripcion: '', ejemplo: '', origen: 'constante' }])}
        >
          <Plus size={13} aria-hidden /> Agregar
        </button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-line dark:border-night-line">
        <table className="table-base">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Origen</th>
              <th>Descripción</th>
              <th>Ejemplo / valor constante</th>
              <th className="w-10"><span className="sr-only">Acciones</span></th>
            </tr>
          </thead>
          <tbody>
            {vars.map((v, i) => (
              <tr key={i}>
                <td className="min-w-[150px]">
                  <input
                    aria-label={`Nombre de variable ${i + 1}`}
                    list="vars-estado"
                    className={`input !py-1 font-mono text-xs ${!usadas.has(v.nombre) && v.nombre ? 'border-amber' : ''}`}
                    value={v.nombre}
                    onChange={(e) => set(i, { nombre: e.target.value.replace(/\W/g, '_'), descripcion: v.descripcion || VARIABLES_ESTADO[e.target.value] || '' })}
                  />
                  {v.nombre && !usadas.has(v.nombre) && <p className="mt-0.5 text-[11px] text-amber-tx dark:text-amber">no se usa en el prompt</p>}
                </td>
                <td>
                  <select aria-label={`Origen de ${v.nombre}`} className="input !py-1 text-xs" value={v.origen} onChange={(e) => set(i, { origen: e.target.value as Origen })}>
                    <option value="estado">estado (runtime)</option>
                    <option value="constante">constante</option>
                    <option value="usuario">usuario</option>
                  </select>
                </td>
                <td className="min-w-[180px]">
                  <input aria-label={`Descripción de ${v.nombre}`} className="input !py-1 text-xs" value={v.descripcion} onChange={(e) => set(i, { descripcion: e.target.value })} />
                </td>
                <td className="min-w-[220px]">
                  {v.origen === 'constante' ? (
                    <textarea
                      aria-label={`Valor constante de ${v.nombre}`}
                      rows={2}
                      className="input !py-1 font-mono text-xs"
                      value={String(agent.constantes[v.nombre] ?? '')}
                      onChange={(e) => onChange(vars, { ...agent.constantes, [v.nombre]: e.target.value })}
                    />
                  ) : (
                    <input aria-label={`Ejemplo de ${v.nombre}`} className="input !py-1 font-mono text-xs" value={v.ejemplo} onChange={(e) => set(i, { ejemplo: e.target.value })} />
                  )}
                </td>
                <td>
                  <button type="button" className="btn-icon h-8 w-8" aria-label={`Quitar variable ${v.nombre}`} onClick={() => onChange(vars.filter((_, j) => j !== i))}>
                    <Trash2 size={14} aria-hidden />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <datalist id="vars-estado">
        {Object.keys(VARIABLES_ESTADO).map((k) => (
          <option key={k} value={k} />
        ))}
      </datalist>
    </div>
  )
}
