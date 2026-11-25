import { useQuery } from '@tanstack/react-query'
import { FlaskConical, Play } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api/client'
import { Badge, JsonView, Modal, Spinner } from '../components/common'
import type { ToolResult, ToolSpec } from '../types'

function campoInicial(spec: ToolSpec): Record<string, string> {
  const out: Record<string, string> = {}
  for (const k of Object.keys(spec.parameters.properties ?? {})) {
    const v = spec.ejemplo_args[k]
    out[k] = v === undefined ? '' : typeof v === 'string' ? v : JSON.stringify(v)
  }
  return out
}

function parseValor(raw: string, schema: any): unknown {
  if (raw === '') return undefined
  const t = schema?.type ?? schema?.anyOf?.find((x: any) => x.type !== 'null')?.type
  if (t === 'integer' || t === 'number') return Number(raw)
  if (t === 'array' || t === 'object' || t === 'boolean') {
    try {
      return JSON.parse(raw)
    } catch {
      return raw
    }
  }
  return raw
}

function ToolTester({ spec, onClose }: { spec: ToolSpec; onClose: () => void }) {
  const [vals, setVals] = useState(() => campoInicial(spec))
  const [cliente, setCliente] = useState('c42')
  const [res, setRes] = useState<ToolResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmar, setConfirmar] = useState(false)
  const props = spec.parameters.properties ?? {}
  const run = async (confirm: boolean) => {
    setBusy(true)
    setErr(null)
    const args: Record<string, unknown> = {}
    for (const [k, raw] of Object.entries(vals)) {
      const v = parseValor(raw, props[k])
      if (v !== undefined) args[k] = v
    }
    try {
      setRes(await api.testTool(spec.name, args, cliente, confirm))
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
      setConfirmar(false)
    }
  }
  return (
    <Modal open onClose={onClose} title={`Probar · ${spec.name}`} wide>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (spec.escritura) setConfirmar(true)
          else run(false)
        }}
      >
        <p className="muted text-sm">{spec.descripcion}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="tt-cliente" className="label">
              cliente (contexto, nunca argumento)
            </label>
            <select id="tt-cliente" className="input" value={cliente} onChange={(e) => setCliente(e.target.value)}>
              <option value="c42">c42 · Camila</option>
              <option value="c-118">c-118 · Restaurante Don Lucho</option>
              <option value="c77">c77 · Tomás</option>
            </select>
          </div>
          {Object.entries(props).map(([k, sch]: [string, any]) => (
            <div key={k}>
              <label htmlFor={`tt-${k}`} className="label">
                {k} {spec.parameters.required?.includes(k) && <span className="text-red-tx dark:text-red">*</span>}
              </label>
              {sch.enum ? (
                <select id={`tt-${k}`} className="input" value={vals[k]} onChange={(e) => setVals({ ...vals, [k]: e.target.value })}>
                  <option value="">—</option>
                  {sch.enum.map((o: string) => (
                    <option key={o}>{o}</option>
                  ))}
                </select>
              ) : (
                <input id={`tt-${k}`} className="input font-mono text-xs" value={vals[k]} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
              )}
              <p className="muted mt-0.5 text-[11px]">
                {sch.type ?? sch.anyOf?.map((x: any) => x.type).join(' | ')}
                {sch.pattern ? ` · ${sch.pattern}` : ''}
                {sch.description ? ` · ${sch.description}` : ''}
              </p>
            </div>
          ))}
        </div>
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? <Spinner /> : <Play size={15} aria-hidden />} Ejecutar
        </button>
        {spec.escritura && <p className="text-xs text-amber-tx dark:text-amber">Herramienta de escritura: modifica datos de Redis; pedirá confirmación.</p>}
        {err && (
          <p role="alert" className="text-sm text-red-tx dark:text-red">
            {err}
          </p>
        )}
        {res && (
          <div>
            <p className="mb-1 flex items-center gap-2 text-sm font-semibold">
              <Badge color={res.ok ? 'green' : 'red'}>{res.ok ? 'ok' : 'error'}</Badge> <span className="muted tabular text-xs">{res.ms} ms</span>
            </p>
            <JsonView value={res.ok ? res.data : res.error} />
          </div>
        )}
      </form>
      <Modal
        open={confirmar}
        onClose={() => setConfirmar(false)}
        title="Confirmar acción de escritura"
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setConfirmar(false)}>
              Cancelar
            </button>
            <button type="button" className="btn-primary" onClick={() => run(true)}>
              Confirmar y ejecutar
            </button>
          </>
        }
      >
        <p className="text-sm">
          Vas a ejecutar <strong className="font-mono">{spec.name}</strong> sobre los datos de {cliente}. Esta acción escribe en Redis (se puede restaurar con <code>make seed</code>).
        </p>
      </Modal>
    </Modal>
  )
}

export default function ToolsPage() {
  const { data: tools = [], isLoading } = useQuery({ queryKey: ['tools'], queryFn: api.tools })
  const [sel, setSel] = useState<ToolSpec | null>(null)
  return (
    <div className="p-3">
      <section className="card overflow-hidden">
        <div className="border-b border-line px-4 py-3 dark:border-night-line">
          <h2 className="text-base font-semibold">Registro de tools</h2>
          <p className="muted text-sm">Implementaciones en código (backend/app/tools); el schema JSON es exactamente lo que ve el modelo.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="table-base">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Descripción</th>
                <th>Tipo</th>
                <th>Schema</th>
                <th><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="muted">
                    <Spinner /> cargando…
                  </td>
                </tr>
              )}
              {tools.map((t) => (
                <tr key={t.name}>
                  <td className="whitespace-nowrap font-mono text-[13px] font-semibold">{t.name}</td>
                  <td className="min-w-[260px] max-w-md text-[13px]">{t.descripcion}</td>
                  <td>
                    <Badge color={t.escritura ? 'amber' : 'green'}>{t.escritura ? 'escritura' : 'lectura'}</Badge>
                  </td>
                  <td className="min-w-[260px]">
                    <JsonView value={t.parameters} collapsed />
                  </td>
                  <td>
                    <button type="button" className="btn-secondary !min-h-[32px] text-xs" onClick={() => setSel(t)}>
                      <FlaskConical size={14} aria-hidden /> Probar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {sel && <ToolTester spec={sel} onClose={() => setSel(null)} />}
    </div>
  )
}
