import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download, Repeat } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { PIPELINE_FLOW } from '../../lib/flowLayout'
import { canvasNode, usePlatformStore } from '../../store/usePlatformStore'
import { Badge, ESTADO_COLOR, JsonView, Spinner, VEREDICTO_COLOR, fecha, ms, usd } from '../common'
import { FlowCanvas } from '../flow/FlowCanvas'
import { TraceConsole } from '../trace/TraceConsole'

export function RunDetail({ runId }: { runId: string }) {
  const { data, isLoading, error } = useQuery({ queryKey: ['run', runId], queryFn: () => api.run(runId) })
  const [tab, setTab] = useState<'traza' | 'llm'>('traza')
  const nav = useNavigate()
  const setCliente = usePlatformStore((s) => s.setCliente)

  const { status, visited, agente } = useMemo(() => {
    const status: Record<string, 'done' | 'error'> = {}
    const visited: string[] = []
    let last: string | null = null
    let agente: string | null = null
    for (const e of data?.events ?? []) {
      const n = canvasNode(e.nodo)
      if (e.tipo === 'node_start') {
        if (last && last !== n) visited.push(`${last}->${n}`)
        last = n
        status[n] = 'done'
        if (n === 'especialista' || n === 'planner') agente = e.nodo
      }
      if (e.tipo === 'tool_call' && last) {
        visited.push(`${last}->tools`, `tools->${last}`)
        status.tools = 'done'
      }
      if (e.tipo === 'error') status[n] = 'error'
      if (e.tipo === 'final') {
        if (last) visited.push(`${last}->final`)
        status.final = e.contenido?.estado === 'error' ? 'error' : 'done'
      }
    }
    return { status, visited, agente }
  }, [data])

  if (isLoading) return <p className="muted flex items-center gap-2 p-6"><Spinner /> cargando run…</p>
  if (error || !data) return <p className="p-6 text-red-tx dark:text-red">No se encontró el run (expira a los 7 días).</p>
  const s = data.summary
  const llm = data.events.filter((e) => e.tipo === 'llm_call')

  const reejecutar = () => {
    setCliente(s.cliente_id)
    try {
      sessionStorage.setItem('aep-reejecutar', s.mensaje)
    } catch {
      /* almacenamiento bloqueado */
    }
    nav('/')
  }

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <section className="card p-4">
        <div className="flex flex-wrap items-start gap-3">
          <Link to="/runs" className="btn-ghost" aria-label="Volver a runs">
            <ArrowLeft size={15} aria-hidden /> Runs
          </Link>
          <div className="min-w-0 flex-1">
            <h2 className="font-mono text-sm font-semibold">{s.run_id}</h2>
            <p className="mt-1 text-[15px] font-medium">“{s.mensaje}”</p>
            <p className="muted mt-1 text-xs">
              {fecha(s.creado)} · cliente {s.cliente_id} · sesión {s.sesion_id} · agentes v{s.version_agentes}
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={reejecutar} title="Envía el mismo mensaje en una sesión nueva (para comparar versiones de prompts)">
              <Repeat size={15} aria-hidden /> Re-ejecutar
            </button>
            <a className="btn-secondary" href={api.exportRunUrl(s.run_id)} download>
              <Download size={15} aria-hidden /> Exportar JSON
            </a>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <Badge color={ESTADO_COLOR[s.estado]}>{s.estado.replace('_', ' ')}</Badge>
          {s.agente && <Badge color="teal">{s.agente}</Badge>}
          {s.veredicto && <Badge color={VEREDICTO_COLOR[s.veredicto] ?? 'muted'}>evaluador: {s.veredicto}</Badge>}
          <span className="muted tabular">
            {usd(s.costo_usd)} · {ms(s.latencia_ms)} · {s.llamadas_llm} llamadas LLM
          </span>
          {data.pendiente && <Badge color="amber">acción pendiente de confirmación</Badge>}
        </div>
        {s.respuesta && <p className="mt-3 whitespace-pre-wrap rounded-lg bg-panel p-3 text-sm dark:bg-night">{s.respuesta}</p>}
        {s.acciones.length > 0 && (
          <div className="mt-2">
            <p className="label">Acciones</p>
            <JsonView value={s.acciones} collapsed />
          </div>
        )}
      </section>
      <div className="grid min-h-0 gap-3 xl:grid-cols-2">
        <section className="card h-[420px] overflow-hidden" aria-label="Flow recorrido">
          <FlowCanvas nodes={PIPELINE_FLOW.nodes} edges={PIPELINE_FLOW.edges} status={status} visited={visited} badges={{ especialista: agente !== 'planner' ? agente : null }} fitKey={runId} />
        </section>
        <section className="flex h-[420px] min-h-0 flex-col gap-2">
          <div role="tablist" aria-label="Detalle del run" className="flex gap-1">
            <button role="tab" aria-selected={tab === 'traza'} type="button" className={tab === 'traza' ? 'btn-primary' : 'btn-secondary'} onClick={() => setTab('traza')}>
              Traza ({data.events.length})
            </button>
            <button role="tab" aria-selected={tab === 'llm'} type="button" className={tab === 'llm' ? 'btn-primary' : 'btn-secondary'} onClick={() => setTab('llm')}>
              Mensajes LLM ({llm.length})
            </button>
          </div>
          {tab === 'traza' ? (
            <TraceConsole events={data.events} autoScroll={false} className="min-h-0 flex-1" />
          ) : (
            <div className="card scroll-thin min-h-0 flex-1 space-y-2 overflow-auto p-3">
              {llm.map((e) => (
                <details key={e.seq} className="rounded-lg border border-line p-2 dark:border-night-line">
                  <summary className="cursor-pointer text-sm">
                    <span className="font-semibold">{e.contenido?.agente}</span> · {e.titulo}{' '}
                    <span className="muted tabular text-xs">
                      {e.modelo} · {e.tokens_in}→{e.tokens_out} tok · {usd(e.costo_usd)} · {ms(e.ms)}
                    </span>
                  </summary>
                  <div className="mt-2 space-y-2">
                    {(e.contenido?.messages ?? []).map((m: { role: string; content: string; tool_calls?: unknown }, i: number) => (
                      <div key={i}>
                        <p className="font-mono text-[11px] font-semibold uppercase text-violet-tx dark:text-violet">{m.role}</p>
                        <pre className="whitespace-pre-wrap break-words rounded bg-panel p-2 font-mono text-[11px] dark:bg-night">
                          {m.content || JSON.stringify(m.tool_calls ?? '', null, 2)}
                        </pre>
                      </div>
                    ))}
                    <p className="font-mono text-[11px] font-semibold uppercase text-green-tx dark:text-green">respuesta</p>
                    <JsonView value={e.contenido?.respuesta} />
                  </div>
                </details>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
