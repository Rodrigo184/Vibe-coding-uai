import { ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { forwardRef, memo, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { TraceEvent } from '../../types'
import { CopyButton } from '../common'

const TIPO_STYLE: Record<string, string> = {
  node_start: 'text-[#9AA8BB]',
  node_end: 'text-[#6B7A8F]',
  thought: 'text-[#B3A9FF]',
  llm_call: 'text-[#5CD3EC]',
  tool_call: 'text-[#F2C14E]',
  tool_result: 'text-[#F2C14E]',
  rule: 'text-[#F2C14E]',
  decision: 'text-[#7EE2A8]',
  judge: 'text-[#FF8A93]',
  memory: 'text-[#B3A9FF]',
  confirm_required: 'text-[#FF8A93] font-bold',
  output: 'text-[#7EE2A8]',
  error: 'text-[#FF6B75] font-bold',
  final: 'text-white font-bold',
}

export const TraceEventRow = memo(function TraceEventRow({ e, verbose }: { e: TraceEvent; verbose: boolean }) {
  const [open, setOpen] = useState(false)
  const hora = new Date(e.ts * 1000).toLocaleTimeString('es-CL', { hour12: false })
  const hasBody = e.contenido !== '' && e.contenido != null
  const metrics = [
    e.modelo && e.modelo,
    e.tokens_in || e.tokens_out ? `${e.tokens_in}→${e.tokens_out} tok` : null,
    e.costo_usd ? `$${e.costo_usd.toFixed(5)}` : null,
    e.ms ? `${e.ms} ms` : null,
  ].filter(Boolean)
  if (!verbose && (e.tipo === 'node_end' || e.tipo === 'node_start')) return null
  return (
    <li className="border-b border-white/5 py-0.5">
      <button
        type="button"
        onClick={() => hasBody && setOpen((o) => !o)}
        className="grid w-full grid-cols-[16px_auto_minmax(0,1fr)_auto] items-start gap-x-2 gap-y-0.5 rounded px-1 text-left hover:bg-white/5 sm:flex sm:gap-2"
        aria-expanded={hasBody ? open : undefined}
      >
        <span className="w-4 shrink-0 pt-0.5 text-[#6B7A8F]">{hasBody ? open ? <ChevronDown size={12} aria-hidden /> : <ChevronRight size={12} aria-hidden /> : null}</span>
        <span className="shrink-0 tabular text-[#9AA8BB]">{hora}</span>
        <span className="shrink-0 truncate font-semibold uppercase text-[#C9D4E2] sm:w-[84px]">{e.nodo}</span>
        <span className={`shrink-0 sm:w-[112px] ${TIPO_STYLE[e.tipo] ?? ''}`}>{e.tipo}</span>
        <span className="col-span-3 col-start-2 min-w-0 flex-1 break-words text-[#E6EDF5]">
          {e.titulo}
          {metrics.length > 0 && <span className="ml-2 text-[11px] text-[#9AA8BB]">{metrics.join(' · ')}</span>}
        </span>
      </button>
      {open && hasBody && (
        <pre className="ml-6 mt-1 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-black/30 p-2 text-[11px] leading-relaxed text-[#C9D4E2]">
          {typeof e.contenido === 'string' ? e.contenido : JSON.stringify(e.contenido, null, 2)}
        </pre>
      )}
    </li>
  )
})

export const TraceConsole = forwardRef<HTMLDivElement, { events: TraceEvent[]; autoScroll?: boolean; className?: string }>(function TraceConsole(
  { events, autoScroll = true, className = '' },
  ref,
) {
  const [verbose, setVerbose] = useState(false)
  const listRef = useRef<HTMLOListElement>(null)
  useEffect(() => {
    const el = listRef.current
    if (autoScroll && el) el.scrollTop = el.scrollHeight
  }, [events.length, autoScroll])
  const runId = [...events].reverse().find((e) => e.run_id)?.run_id
  return (
    <div ref={ref} tabIndex={-1} className={`flex min-h-0 flex-col rounded-xl bg-console font-mono text-[12px] text-[#E6EDF5] ${className}`} aria-label="Traza en vivo">
      <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[#9AA8BB]">Traza en vivo</span>
        <span className="text-[11px] text-[#6B7A8F]">{events.length} eventos</span>
        <label className="ml-auto flex cursor-pointer items-center gap-1 text-[11px] text-[#9AA8BB]">
          <input type="checkbox" checked={verbose} onChange={(e) => setVerbose(e.target.checked)} className="accent-teal" />
          inicio/fin de nodo
        </label>
        <CopyButton
          text={() => events.map((e) => `${new Date(e.ts * 1000).toISOString()} ${e.nodo} ${e.tipo} ${e.titulo}`).join('\n')}
          label="Copiar traza"
          className="!min-h-[28px] !px-2 !text-[11px] !text-[#9AA8BB] hover:!bg-white/10"
        />
        {runId && (
          <Link to={`/runs/${runId}`} className="btn-ghost !min-h-[28px] !px-2 !text-[11px] !text-[#9AA8BB] hover:!bg-white/10">
            <ExternalLink size={12} aria-hidden /> Abrir run
          </Link>
        )}
      </div>
      <ol ref={listRef} className="scroll-thin min-h-0 flex-1 overflow-auto px-2 py-1" aria-live="off">
        {events.length === 0 && <li className="px-1 py-3 text-[#9AA8BB]">Envía un mensaje para ver las llamadas al modelo, las herramientas, las reglas y el veredicto.</li>}
        {events.map((e) => (
          <TraceEventRow key={`${e.run_id}-${e.seq}`} e={e} verbose={verbose} />
        ))}
      </ol>
    </div>
  )
})
