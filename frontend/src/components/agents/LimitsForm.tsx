import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Limits } from '../../types'

const CAMPOS: { k: keyof Limits; label: string; help: string; min: number; max: number; step: number }[] = [
  { k: 'max_iters', label: 'max_iters', help: 'ciclos ReAct máximos (tool calling)', min: 1, max: 20, step: 1 },
  { k: 'max_tokens_out', label: 'max_tokens_out', help: 'tokens de salida por llamada', min: 16, max: 8000, step: 16 },
  { k: 'timeout_s', label: 'timeout_s', help: 'timeout por llamada al modelo', min: 1, max: 120, step: 1 },
  { k: 'temperature', label: 'temperature', help: '0 = determinístico', min: 0, max: 2, step: 0.1 },
]

export function LimitsForm({ limits, onChange }: { limits: Limits; onChange: (l: Limits) => void }) {
  const { data: cfg } = useQuery({ queryKey: ['config'], queryFn: api.config })
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {CAMPOS.map((c) => (
        <div key={c.k}>
          <label htmlFor={`lim-${c.k}`} className="label">
            {c.label}
          </label>
          <input
            id={`lim-${c.k}`}
            type="number"
            className="input tabular"
            min={c.min}
            max={c.max}
            step={c.step}
            value={limits[c.k] as number}
            onChange={(e) => onChange({ ...limits, [c.k]: Number(e.target.value) })}
          />
          <p className="muted mt-1 text-xs">{c.help}</p>
        </div>
      ))}
      <div>
        <label htmlFor="lim-modelo" className="label">
          modelo
        </label>
        <select id="lim-modelo" className="input" value={limits.modelo ?? ''} onChange={(e) => onChange({ ...limits, modelo: e.target.value || null })}>
          <option value="">por defecto ({cfg?.modelo ?? 'OPENAI_MODEL'})</option>
          {(cfg?.modelos ?? []).map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <p className="muted mt-1 text-xs">El evaluador usa OPENAI_JUDGE_MODEL ({cfg?.modelo_juez ?? '—'}) salvo que fijes uno aquí.</p>
      </div>
    </div>
  )
}
