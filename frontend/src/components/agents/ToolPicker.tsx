import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { AgentDef } from '../../types'
import { Badge, JsonView } from '../common'

export function ToolPicker({ agent, onChange }: { agent: AgentDef; onChange: (tools: string[], escritura: string[]) => void }) {
  const { data: tools = [] } = useQuery({ queryKey: ['tools'], queryFn: api.tools })
  const sel = new Set(agent.tools)
  const esc = new Set(agent.acciones_escritura)
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-semibold">
        Tools permitidas <span className="muted font-normal">({agent.tools.length} seleccionadas · el modelo solo ve estos schemas)</span>
      </legend>
      <div className="grid gap-2 md:grid-cols-2">
        {tools.map((t) => {
          const on = sel.has(t.name)
          return (
            <div key={t.name} className={`rounded-lg border p-3 ${on ? 'border-teal-dk bg-teal/5 dark:border-teal' : 'border-line dark:border-night-line'}`}>
              <label className="flex cursor-pointer items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-teal"
                  checked={on}
                  onChange={(e) => {
                    const next = e.target.checked ? [...agent.tools, t.name] : agent.tools.filter((x) => x !== t.name)
                    const nextEsc = e.target.checked
                      ? t.escritura && t.name !== 'crear_ticket'
                        ? [...new Set([...agent.acciones_escritura, t.name])]
                        : agent.acciones_escritura
                      : agent.acciones_escritura.filter((x) => x !== t.name)
                    onChange(next, nextEsc)
                  }}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="font-mono text-[13px] font-semibold">{t.name}</span>
                    <Badge color={t.escritura ? 'amber' : 'green'}>{t.escritura ? 'escritura' : 'lectura'}</Badge>
                  </span>
                  <span className="muted mt-0.5 block text-xs">{t.descripcion}</span>
                </span>
              </label>
              {on && (
                <div className="mt-2 space-y-2 pl-6">
                  <label className="flex cursor-pointer items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-amber"
                      checked={esc.has(t.name)}
                      onChange={(e) => onChange(agent.tools, e.target.checked ? [...agent.acciones_escritura, t.name] : agent.acciones_escritura.filter((x) => x !== t.name))}
                    />
                    exige confirmación del usuario
                  </label>
                  <details>
                    <summary className="muted cursor-pointer text-xs">schema que ve el modelo</summary>
                    <JsonView value={t.parameters} className="mt-1" />
                  </details>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </fieldset>
  )
}
