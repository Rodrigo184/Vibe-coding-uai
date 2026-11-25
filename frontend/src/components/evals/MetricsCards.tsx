import { ArrowDownRight, ArrowUpRight, Circle } from 'lucide-react'
import type { EvalReport } from '../../types'
import { ms, pct, usd } from '../common'

type Fmt = 'pct' | 'usd' | 'ms' | 'num'
const METRICAS: { k: string; label: string; fmt: Fmt; mejorAlto: boolean; sem?: string; meta?: string }[] = [
  { k: 'precision', label: 'Precisión (juez)', fmt: 'pct', mejorAlto: true, sem: 'precision', meta: '≥ 90 %' },
  { k: 'cumplimiento_reglas', label: 'Cumplimiento de reglas', fmt: 'pct', mejorAlto: true, sem: 'cumplimiento_reglas', meta: '= 100 %' },
  { k: 'derivacion_humano', label: 'Derivación a humano (normales)', fmt: 'pct', mejorAlto: false, sem: 'derivacion_humano', meta: '< 10 %' },
  { k: 'precision_enrutamiento', label: 'Precisión de enrutamiento', fmt: 'pct', mejorAlto: true },
  { k: 'precision_tools', label: 'Precisión de tools', fmt: 'pct', mejorAlto: true },
  { k: 'confirmacion_correcta', label: 'Confirmación correcta', fmt: 'pct', mejorAlto: true },
  { k: 'consistencia', label: 'Consistencia (≥2 repeticiones)', fmt: 'pct', mejorAlto: true },
  { k: 'derivacion_humano_adversariales', label: 'Derivación (adversariales)', fmt: 'pct', mejorAlto: true },
  { k: 'costo_promedio_usd', label: 'Costo promedio / caso', fmt: 'usd', mejorAlto: false },
  { k: 'latencia_p50_ms', label: 'Latencia p50', fmt: 'ms', mejorAlto: false },
  { k: 'latencia_p95_ms', label: 'Latencia p95', fmt: 'ms', mejorAlto: false },
  { k: 'llamadas_llm_promedio', label: 'Llamadas LLM promedio', fmt: 'num', mejorAlto: false },
]

const fmt = (v: unknown, f: Fmt) => (v == null ? '—' : f === 'pct' ? pct(v as number) : f === 'usd' ? usd(v as number) : f === 'ms' ? ms(v as number) : String(v))
const SEM = {
  verde: { cls: 'text-green-tx dark:text-green', txt: 'cumple' },
  amarillo: { cls: 'text-amber-tx dark:text-amber', txt: 'cerca' },
  rojo: { cls: 'text-red-tx dark:text-red', txt: 'no cumple' },
  gris: { cls: 'text-muted', txt: 'sin datos' },
} as const

export function MetricsCards({ report, previo }: { report: EvalReport; previo?: EvalReport | null }) {
  const m = report.metricas
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
      {METRICAS.map((d) => {
        const v = m[d.k]
        const p = previo?.metricas?.[d.k]
        const delta = typeof v === 'number' && typeof p === 'number' ? v - p : null
        const mejora = delta == null || delta === 0 ? null : d.mejorAlto ? delta > 0 : delta < 0
        const sem = d.sem ? SEM[(m.semaforo?.[d.sem] ?? 'gris') as keyof typeof SEM] : null
        return (
          <div key={d.k} className={`rounded-xl border p-3 ${d.sem ? 'border-line bg-white dark:border-night-line dark:bg-night-card' : 'border-transparent bg-panel dark:bg-night'}`}>
            <p className="muted text-[11px] font-semibold uppercase leading-tight tracking-wide">{d.label}</p>
            <p className="mt-1 text-xl font-bold tabular">{fmt(v, d.fmt)}</p>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px]">
              {sem && (
                <span className={`flex items-center gap-1 font-semibold ${sem.cls}`}>
                  <Circle size={8} fill="currentColor" aria-hidden /> {sem.txt} ({d.meta})
                </span>
              )}
              {delta != null && delta !== 0 && (
                <span className={`flex items-center tabular ${mejora ? 'text-green-tx dark:text-green' : 'text-red-tx dark:text-red'}`} title="Δ vs reporte anterior">
                  {delta > 0 ? <ArrowUpRight size={12} aria-hidden /> : <ArrowDownRight size={12} aria-hidden />}
                  {d.fmt === 'pct' ? `${(delta * 100).toFixed(0)} pp` : d.fmt === 'usd' ? delta.toFixed(4) : delta.toFixed(0)}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
