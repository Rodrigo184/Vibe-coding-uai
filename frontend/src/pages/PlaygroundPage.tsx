import { useQuery } from '@tanstack/react-query'
import { MousePointerClick, RotateCcw, X } from 'lucide-react'
import { useEffect, useMemo, useRef } from 'react'
import { api } from '../api/client'
import { ChatPanel } from '../components/chat/ChatPanel'
import { useGlobalChat } from '../components/chat/useChat'
import { Badge, EmptyState, ESTADO_COLOR, JsonView, ms, usd, VEREDICTO_COLOR } from '../components/common'
import { FlowCanvas } from '../components/flow/FlowCanvas'
import { TraceConsole } from '../components/trace/TraceConsole'
import { PIPELINE_FLOW } from '../lib/flowLayout'
import { canvasNode, usePlatformStore } from '../store/usePlatformStore'
import type { FinalContent, TraceEvent } from '../types'

function NodeDetail({ nodeId, events, onClose }: { nodeId: string; events: TraceEvent[]; onClose: () => void }) {
  const llm = usePlatformStore((s) => s.lastLlmByNode[nodeId])
  const nodeEvents = events.filter((e) => canvasNode(e.nodo) === nodeId && e.tipo !== 'llm_call')
  const label = PIPELINE_FLOW.nodes.find((n) => n.id === nodeId)?.label ?? nodeId
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-line px-3 py-2 dark:border-night-line">
        <h2 className="text-sm font-semibold">
          {label} <span className="muted font-normal">· este turno</span>
        </h2>
        <button type="button" className="btn-icon" onClick={onClose} aria-label="Cerrar detalle del nodo">
          <X size={16} aria-hidden />
        </button>
      </div>
      <div className="scroll-thin min-h-0 flex-1 space-y-3 overflow-auto p-3">
        {llm ? (
          <>
            <div className="flex flex-wrap gap-1 text-[11px]">
              <Badge color="teal">{llm.contenido?.agente}</Badge>
              {llm.modelo && <Badge>{llm.modelo}</Badge>}
              <Badge>
                {llm.tokens_in}→{llm.tokens_out} tok
              </Badge>
              <Badge>{usd(llm.costo_usd)}</Badge>
            </div>
            <p className="label">Prompt renderizado (última llamada)</p>
            {(llm.contenido?.messages ?? []).map((m: { role: string; content: string; tool_calls?: unknown }, i: number) => (
              <div key={i}>
                <p className="mb-0.5 font-mono text-[11px] font-semibold uppercase text-violet-tx dark:text-violet">{m.role}</p>
                <pre className="whitespace-pre-wrap break-words rounded-lg bg-panel p-2 font-mono text-[11.5px] leading-relaxed dark:bg-night">
                  {m.content || (m.tool_calls ? JSON.stringify(m.tool_calls, null, 2) : '')}
                </pre>
              </div>
            ))}
            <p className="label">Respuesta del modelo</p>
            <JsonView value={llm.contenido?.respuesta} />
          </>
        ) : nodeEvents.length ? (
          <>
            <p className="muted text-xs">Este nodo no llama a un modelo: corre en código. Eventos del turno:</p>
            {nodeEvents.map((e) => (
              <div key={e.seq} className="rounded-lg border border-line p-2 dark:border-night-line">
                <p className="text-xs font-semibold">
                  {e.tipo} · {e.titulo}
                </p>
                {e.contenido && <JsonView value={e.contenido} collapsed={JSON.stringify(e.contenido).length > 400} />}
              </div>
            ))}
          </>
        ) : (
          <EmptyState title="Sin actividad en este turno" icon={<MousePointerClick size={18} aria-hidden />}>
            Envía un mensaje y vuelve a hacer clic en el nodo.
          </EmptyState>
        )}
      </div>
    </div>
  )
}

function TurnSummary({ events }: { events: TraceEvent[] }) {
  const final = [...events].reverse().find((e) => e.tipo === 'final')?.contenido as FinalContent | undefined
  const decision = [...events].reverse().find((e) => e.nodo === 'router' && e.tipo === 'decision')
  const judge = [...events].reverse().find((e) => e.tipo === 'judge' && e.nodo === 'evaluador')
  const reglas = events.filter((e) => e.tipo === 'rule')
  if (!final && !decision)
    return (
      <EmptyState title="Detalle del turno" icon={<MousePointerClick size={18} aria-hidden />}>
        Haz clic en cualquier nodo del flow para ver el prompt renderizado de ese agente en este turno.
      </EmptyState>
    )
  return (
    <div className="scroll-thin h-full space-y-4 overflow-auto p-3 text-sm">
      <h2 className="text-sm font-semibold">Resumen del turno</h2>
      {final && (
        <dl className="grid grid-cols-2 gap-2">
          {[
            ['Estado', <Badge key="e" color={ESTADO_COLOR[final.estado]}>{final.estado.replace('_', ' ')}</Badge>],
            ['Agente', final.agente ?? '—'],
            ['Veredicto', final.veredicto ? <Badge key="v" color={VEREDICTO_COLOR[final.veredicto]}>{final.veredicto}</Badge> : '—'],
            ['Costo', usd(final.costo_usd)],
            ['Latencia', ms(final.latencia_ms)],
            ['Llamadas LLM', final.llamadas_llm],
          ].map(([k, v]) => (
            <div key={String(k)} className="rounded-lg bg-panel p-2 dark:bg-night">
              <dt className="muted text-[11px] uppercase tracking-wide">{k}</dt>
              <dd className="tabular font-semibold">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {decision && (
        <div>
          <p className="label">Router</p>
          <p className="text-[13px]">{decision.titulo}</p>
          {decision.contenido?.motivo && <p className="muted text-xs">{decision.contenido.motivo}</p>}
        </div>
      )}
      {reglas.length > 0 && (
        <div>
          <p className="label">Reglas</p>
          <ul className="space-y-1">
            {reglas.map((r) => (
              <li key={r.seq} className="flex items-start gap-1.5 text-xs">
                <Badge color={r.contenido?.ok === false ? 'red' : 'green'}>{r.contenido?.ok === false ? r.contenido?.accion : 'ok'}</Badge>
                <span>
                  <span className="font-mono">{r.contenido?.nombre}</span> <span className="muted">{r.contenido?.detalle}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {judge && (
        <div>
          <p className="label">Evaluador</p>
          <p className="text-[13px]">{judge.titulo}</p>
          {judge.contenido?.evidencia && <p className="muted text-xs">{judge.contenido.evidencia}</p>}
        </div>
      )}
    </div>
  )
}

export default function PlaygroundPage() {
  const chat = useGlobalChat()
  const { clienteId, sesionId, setCliente, nuevaSesion, nodeStatus, visitedEdges, agenteElegido, toolFlash, selectedNode, selectNode } = usePlatformStore()
  const { data: clientes } = useQuery({ queryKey: ['clientes'], queryFn: api.clientes })
  const selectRef = useRef<HTMLSelectElement>(null)
  const traceRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const sendRef = useRef(chat.send)
  sendRef.current = chat.send
  useEffect(() => {
    // "Re-ejecutar" desde un run: mismo mensaje en una sesión nueva
    let pendiente: string | null = null
    try {
      pendiente = sessionStorage.getItem('aep-reejecutar')
      sessionStorage.removeItem('aep-reejecutar')
    } catch {
      /* almacenamiento bloqueado */
    }
    if (pendiente) sendRef.current(pendiente)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT')
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        selectRef.current?.focus()
      } else if (!typing && (e.key === 't' || e.key === 'T')) {
        e.preventDefault()
        traceRef.current?.focus()
        traceRef.current?.scrollIntoView({ block: 'nearest' })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const badges = useMemo(() => ({ especialista: agenteElegido && agenteElegido !== 'planner' ? agenteElegido : null, planner: agenteElegido === 'planner' ? 'planner' : null }), [agenteElegido])
  const flash = useMemo(() => ({ tools: toolFlash }), [toolFlash])
  const clienteActual = clientes?.find((c) => c.cliente_id === clienteId)

  const header = (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2 border-b border-line p-3 dark:border-night-line">
      <div className="col-span-2 flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Chat de prueba</h2>
        <button type="button" className="btn-ghost" disabled={chat.busy} onClick={nuevaSesion} title="Abre un historial nuevo para este cliente">
          <RotateCcw size={14} aria-hidden /> Nueva sesión
        </button>
      </div>
      <div className="min-w-0">
        <label htmlFor="cliente" className="label">
          Cliente
        </label>
        <select id="cliente" name="cliente" ref={selectRef} className="input" value={clienteId} disabled={chat.busy} onChange={(e) => setCliente(e.target.value)}>
          {(clientes ?? [{ cliente_id: clienteId, nombre: clienteId, tienda: null, canal: null, en_negocio: true }]).map((c) => (
            <option key={c.cliente_id} value={c.cliente_id}>
              {c.cliente_id} · {c.nombre}
              {c.tienda ? ` (${c.tienda}, ${c.canal})` : ''}
            </option>
          ))}
        </select>
      </div>
      <div>
        <span className="label">Sesión</span>
        <span className="flex h-[38px] items-center rounded-lg bg-panel px-2 font-mono text-xs dark:bg-night">{sesionId}</span>
      </div>
      {clienteActual?.nombre && <p className="muted col-span-2 text-xs">El perfil de {clienteActual.nombre} se conserva entre sesiones.</p>}
    </div>
  )

  return (
    <div className="grid min-h-0 flex-1 gap-3 p-3 lg:grid-cols-[minmax(340px,400px)_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)] xl:grid-cols-[380px_minmax(0,1fr)_300px]">
      <div className="h-[min(590px,max(400px,70svh))] min-w-0 lg:h-full lg:min-h-0">
        <ChatPanel messages={chat.messages} busy={chat.busy} onSend={chat.send} onConfirm={chat.confirm} header={header} inputRef={inputRef} />
      </div>
      <div className="flex min-h-0 min-w-0 flex-col gap-3">
        <section className="card flex h-[380px] min-h-[300px] flex-[3] flex-col overflow-hidden lg:h-auto" aria-label="Flow en vivo">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2 dark:border-night-line">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold">Flow en vivo</h2>
              {chat.busy && <Badge color="red">En ejecución</Badge>}
            </div>
            <select aria-label="Inspeccionar nodo" name="nodo" className="input !w-auto !py-1.5" value={selectedNode ?? ''} onChange={(e) => selectNode(e.target.value || null)}>
              <option value="">Inspeccionar nodo…</option>
              {PIPELINE_FLOW.nodes.map((node) => <option key={node.id} value={node.id}>{node.label}</option>)}
            </select>
          </div>
          <div className="min-h-0 flex-1">
            <FlowCanvas
              nodes={PIPELINE_FLOW.nodes}
              edges={PIPELINE_FLOW.edges}
              status={nodeStatus}
              visited={visitedEdges}
              badges={badges}
              flash={flash}
              onNodeClick={selectNode}
              fitKey="pipeline"
            />
          </div>
        </section>
        <TraceConsole ref={traceRef} events={chat.events} className="min-h-[240px] flex-[2]" />
      </div>
      <aside className={`card min-h-0 min-w-0 overflow-hidden ${selectedNode ? 'fixed inset-y-3 right-3 z-50 w-[min(420px,calc(100vw-24px))] shadow-pop xl:static xl:w-auto xl:shadow-card' : 'hidden xl:block'}`} aria-label="Detalle">
        {selectedNode ? <NodeDetail nodeId={selectedNode} events={chat.events} onClose={() => selectNode(null)} /> : <TurnSummary events={chat.events} />}
      </aside>
    </div>
  )
}
