import { useQuery } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Badge, EmptyState, Spinner, fecha, ms, pct, usd, VEREDICTO_COLOR } from '../components/common'
import { DatasetTable } from '../components/evals/DatasetTable'
import { EvalRunner } from '../components/evals/EvalRunner'
import { MetricsCards } from '../components/evals/MetricsCards'

const Ok = ({ v }: { v: boolean | null }) =>
  v == null ? <span className="muted">—</span> : v ? <Check size={15} className="text-green-tx dark:text-green" aria-label="ok" /> : <X size={15} className="text-red-tx dark:text-red" aria-label="falla" />

export default function EvalsPage() {
  const { data: cases = [], isLoading } = useQuery({ queryKey: ['dataset'], queryFn: api.dataset })
  const { data: reports = [] } = useQuery({ queryKey: ['reports'], queryFn: api.reports })
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [reportId, setReportId] = useState<string | null>(null)
  useEffect(() => {
    if (!reportId && reports.length) setReportId(reports[0].id)
  }, [reports, reportId])
  const { data: report } = useQuery({ queryKey: ['report', reportId], queryFn: () => api.report(reportId!), enabled: !!reportId })
  const idx = reports.findIndex((r) => r.id === reportId)
  const previo = idx >= 0 ? reports[idx + 1] ?? null : null

  return (
    <div className="space-y-3 p-3">
      {isLoading ? (
        <p className="muted flex items-center gap-2"><Spinner /> cargando dataset…</p>
      ) : (
        <DatasetTable cases={cases} selected={selected} onSelect={setSelected} />
      )}
      <EvalRunner selected={selected} total={cases.length} onDone={setReportId} />
      <section className="card overflow-hidden">
        <div className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3 dark:border-night-line">
          <div className="mr-auto">
            <h2 className="text-sm font-semibold">Reporte</h2>
            {report && (
              <p className="muted text-xs">
                {fecha(report.creado)} · agentes v{report.version_agentes} · {report.casos} casos × {report.repeticiones} rep. · LLM {report.modo_llm}
                {previo && ` · Δ vs ${previo.id}`}
              </p>
            )}
          </div>
          {reports.length > 0 && (
            <div>
              <label htmlFor="rep-sel" className="label">
                reportes
              </label>
              <select id="rep-sel" className="input" value={reportId ?? ''} onChange={(e) => setReportId(e.target.value)}>
                {reports.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.id} · precisión {pct(r.metricas?.precision)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        {!report ? (
          <EmptyState title="Sin reportes todavía">Ejecuta el dataset para medir precisión, consistencia, cumplimiento, costo y latencia por agente.</EmptyState>
        ) : (
          <div className="space-y-3 p-3">
            <MetricsCards report={report} previo={previo} />
            {report.por_regla && Object.keys(report.por_regla).length > 0 && (
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="label !mb-0 self-center">por regla POST</span>
                {Object.entries(report.por_regla).map(([k, v]) => (
                  <Badge key={k} color={v >= 1 ? 'green' : v >= 0.9 ? 'amber' : 'red'}>
                    {k}: {pct(v)}
                  </Badge>
                ))}
              </div>
            )}
            <div className="scroll-thin max-h-[520px] overflow-auto rounded-lg border border-line dark:border-night-line">
              <table className="table-base text-xs">
                <thead>
                  <tr>
                    <th>caso</th>
                    <th>rep</th>
                    <th>mensaje</th>
                    <th>agente (esperado → obtenido)</th>
                    <th>ruta</th>
                    <th>tools</th>
                    <th>conf.</th>
                    <th>reglas</th>
                    <th>juez</th>
                    <th>respuesta</th>
                    <th className="text-right">costo</th>
                    <th className="text-right">latencia</th>
                  </tr>
                </thead>
                <tbody>
                  {(report.resultados ?? []).map((r) => (
                    <tr key={`${r.case_id}-${r.repeticion}`}>
                      <td className="font-mono">
                        {r.run_id ? (
                          <Link to={`/runs/${r.run_id}`} className="text-teal-tx underline-offset-2 hover:underline dark:text-teal">
                            {r.case_id}
                          </Link>
                        ) : (
                          r.case_id
                        )}
                        <span className="block">
                          <Badge color={r.etiqueta === 'adversarial' ? 'red' : r.etiqueta === 'borde' ? 'amber' : 'green'}>{r.etiqueta}</Badge>
                        </span>
                      </td>
                      <td className="tabular">{r.repeticion + 1}</td>
                      <td className="max-w-[220px]">{r.mensaje}</td>
                      <td className="whitespace-nowrap font-mono">
                        {Array.isArray(r.agente_esperado) ? r.agente_esperado.join('|') : r.agente_esperado} → {r.agente ?? '—'}
                      </td>
                      <td><Ok v={r.ok_enrutamiento} /></td>
                      <td title={`esperadas: ${r.tools_esperadas.join(', ') || '—'}\nllamadas: ${r.tools.join(', ') || '—'}`}>
                        <Ok v={r.ok_tools} />
                      </td>
                      <td><Ok v={r.ok_confirmacion} /></td>
                      <td title={r.reglas_post.filter((x) => !x.ok).map((x) => `${x.nombre}: ${x.detalle}`).join('\n')}>
                        <Ok v={r.ok_reglas} />
                      </td>
                      <td className="whitespace-nowrap">
                        {r.veredicto ? <Badge color={VEREDICTO_COLOR[r.veredicto] ?? 'muted'}>{r.veredicto}</Badge> : r.estado}
                        {r.juez && (
                          <span className="muted block tabular">
                            P{r.juez.precision} C{r.juez.consistencia} R{r.juez.cumplimiento_reglas}
                          </span>
                        )}
                      </td>
                      <td className="max-w-[300px]">
                        <span className="line-clamp-3" title={r.respuesta ?? ''}>
                          {r.respuesta}
                        </span>
                      </td>
                      <td className="text-right tabular">{usd(r.costo_usd)}</td>
                      <td className="text-right tabular">{ms(r.latencia_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
