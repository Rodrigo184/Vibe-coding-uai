import { useQueryClient } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { useState } from 'react'
import { postSSE } from '../../api/client'
import type { EvalResult } from '../../types'
import { Badge, Spinner } from '../common'

type Ev = { tipo: 'inicio'; total: number } | { tipo: 'progreso'; i: number; total: number; resultado: EvalResult } | { tipo: 'fin'; report_id: string }

export function EvalRunner({ selected, total, onDone }: { selected: Set<string>; total: number; onDone: (reportId: string) => void }) {
  const [reps, setReps] = useState(1)
  const [running, setRunning] = useState(false)
  const [prog, setProg] = useState<{ i: number; total: number; last?: EvalResult } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const qc = useQueryClient()
  const ids = selected.size && selected.size < total ? [...selected] : null
  const run = async () => {
    setRunning(true)
    setErr(null)
    setProg({ i: 0, total: (ids?.length ?? total) * reps })
    try {
      await postSSE<Ev>('/evals/run', { ids, repeticiones: reps }, (ev) => {
        if (ev.tipo === 'progreso') setProg({ i: ev.i, total: ev.total, last: ev.resultado })
        if (ev.tipo === 'fin') {
          qc.invalidateQueries({ queryKey: ['reports'] })
          onDone(ev.report_id)
        }
      })
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setRunning(false)
    }
  }
  const p = prog ? Math.round((prog.i / Math.max(1, prog.total)) * 100) : 0
  return (
    <section className="card p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <h2 className="text-sm font-semibold">Correr evaluación</h2>
          <p className="muted text-xs">
            {ids ? `${ids.length} casos seleccionados` : `todos los casos (${total})`} · cada caso en sesión nueva, memoria aislada, sin ejecutar escrituras.
          </p>
        </div>
        <div>
          <label htmlFor="reps" className="label">
            repeticiones
          </label>
          <select id="reps" className="input w-24" value={reps} onChange={(e) => setReps(Number(e.target.value))}>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </div>
        <button type="button" className="btn-primary" onClick={run} disabled={running || total === 0}>
          {running ? <Spinner /> : <Play size={15} aria-hidden />} Ejecutar
        </button>
      </div>
      {prog && (
        <div className="mt-3" aria-live="polite">
          <div className="h-2 overflow-hidden rounded-full bg-panel dark:bg-night" role="progressbar" aria-valuenow={p} aria-valuemin={0} aria-valuemax={100} aria-label="Progreso de la evaluación">
            <div className="h-full rounded-full bg-teal transition-all" style={{ width: `${p}%` }} />
          </div>
          <p className="muted mt-1 flex flex-wrap items-center gap-2 text-xs tabular">
            {prog.i}/{prog.total} ({p} %)
            {prog.last && (
              <>
                · último: <span className="font-mono">{prog.last.case_id}</span>
                <Badge color={prog.last.ok_enrutamiento ? 'green' : 'red'}>{prog.last.agente ?? '—'}</Badge>
              </>
            )}
          </p>
        </div>
      )}
      {err && (
        <p role="alert" className="mt-2 text-sm text-red-tx dark:text-red">
          {err}
        </p>
      )}
    </section>
  )
}
