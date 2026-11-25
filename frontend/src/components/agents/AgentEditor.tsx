import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Copy, Eye, RefreshCw, RotateCcw, Save, ShieldCheck, Trash2, TriangleAlert } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { flowDesdeTipo } from '../../lib/flowLayout'
import type { AgentDef } from '../../types'
import { ChatPanel } from '../chat/ChatPanel'
import { useLocalChat } from '../chat/useChat'
import { Badge, COLOR_CLASSES, Dot, Modal, Spinner, Tabs, TIPO_COLOR, Toast, fecha } from '../common'
import { FlowCanvas } from '../flow/FlowCanvas'
import { TraceConsole } from '../trace/TraceConsole'
import { LimitsForm } from './LimitsForm'
import { PromptEditor } from './PromptEditor'
import { SupervisorForm } from './SupervisorForm'
import { ToolPicker } from './ToolPicker'
import { VariablesTable } from './VariablesTable'

type Tab = 'general' | 'pipeline' | 'prompt' | 'tools' | 'limites' | 'flow' | 'probar'
type Problema = { nivel: 'error' | 'aviso'; campo: string; mensaje: string }

const COLORES = ['ink', 'teal', 'amber', 'violet', 'red', 'green']
const PUEDE_PROBAR = ['especialista', 'hibrido', 'planner']

export function AgentEditor({ agentId }: { agentId: string }) {
  const { data: remote, isLoading, error } = useQuery({ queryKey: ['agent', agentId], queryFn: () => api.agent(agentId) })
  const [draft, setDraft] = useState<AgentDef | null>(null)
  const [tab, setTab] = useState<Tab>('general')
  const [problemas, setProblemas] = useState<Problema[] | null>(null)
  const [render, setRender] = useState<{ system: string; user: string; faltantes: string[] } | null>(null)
  const [toast, setToast] = useState<{ msg: string; kind: 'ok' | 'error' } | null>(null)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const qc = useQueryClient()
  const nav = useNavigate()

  useEffect(() => {
    if (remote) {
      setDraft(structuredClone(remote))
      setProblemas(null)
    }
  }, [remote])
  useEffect(() => setTab('general'), [agentId])

  const dirty = useMemo(() => !!draft && !!remote && JSON.stringify(draft) !== JSON.stringify(remote), [draft, remote])

  if (isLoading || !draft)
    return (
      <div className="card muted flex items-center gap-2 p-6">
        {error ? `No se pudo cargar el agente: ${(error as Error).message}` : <><Spinner /> cargando agente…</>}
      </div>
    )

  const up = (patch: Partial<AgentDef>) => setDraft({ ...draft, ...patch })
  const upPrompt = (patch: Partial<AgentDef['prompt']>) => setDraft({ ...draft, prompt: { ...draft.prompt, ...patch } })
  const esSupervisor = draft.tipo === 'supervisor'

  const tabs: { id: Tab; label: string }[] = [
    { id: 'general', label: 'General' },
    ...(esSupervisor ? [{ id: 'pipeline' as Tab, label: 'Pipeline' }] : []),
    { id: 'prompt', label: 'Prompt' },
    ...(!esSupervisor ? [{ id: 'tools' as Tab, label: `Tools (${draft.tools.length})` }] : []),
    { id: 'limites', label: 'Límites' },
    { id: 'flow', label: 'Flow' },
    ...(PUEDE_PROBAR.includes(draft.tipo) ? [{ id: 'probar' as Tab, label: 'Probar' }] : []),
  ]

  const validar = async () => {
    const r = await api.validateAgent(draft)
    setProblemas(r.problemas)
    return r
  }
  const guardar = async () => {
    setSaving(true)
    try {
      const r = await api.updateAgent(draft)
      setToast({ msg: r.mensaje, kind: 'ok' })
      setProblemas(null)
      qc.setQueryData(['agent', agentId], { ...r.agent, tiene_semilla: remote?.tiene_semilla })
      await qc.invalidateQueries({ queryKey: ['agents'] })
      await qc.invalidateQueries({ queryKey: ['health'] })
    } catch (e) {
      setToast({ msg: (e as Error).message, kind: 'error' })
      await validar()
    } finally {
      setSaving(false)
    }
  }
  const restaurar = async () => {
    const r = await api.restoreAgent(agentId)
    qc.setQueryData(['agent', agentId], { ...r.agent, tiene_semilla: true })
    await qc.invalidateQueries({ queryKey: ['agents'] })
    setToast({ msg: 'Semilla restaurada (nueva versión)', kind: 'ok' })
  }
  const duplicar = async () => {
    let n = 2
    const ids = new Set((qc.getQueryData<{ id: string }[]>(['agents']) ?? []).map((a) => a.id))
    while (ids.has(`${draft.id}_${n}`)) n++
    const nuevo = { ...draft, id: `${draft.id}_${n}`, nombre: `${draft.nombre} (copia)`, version: 1 }
    try {
      await api.createAgent(nuevo)
      await qc.invalidateQueries({ queryKey: ['agents'] })
      nav(`/agentes/${nuevo.id}`)
    } catch (e) {
      setToast({ msg: (e as Error).message, kind: 'error' })
    }
  }
  const eliminar = async () => {
    try {
      await api.deleteAgent(agentId)
      await qc.invalidateQueries({ queryKey: ['agents'] })
      nav('/agentes')
    } catch (e) {
      setToast({ msg: (e as Error).message, kind: 'error' })
    }
    setConfirmDelete(false)
  }
  const verConEjemplo = async () => setRender(await api.renderAgent(agentId, draft))

  const errores = problemas?.filter((p) => p.nivel === 'error') ?? []
  const c = COLOR_CLASSES[draft.color] ?? COLOR_CLASSES.teal

  return (
    <section className="card flex min-h-0 flex-col overflow-hidden" aria-label={`Editor de ${draft.nombre}`}>
      <div className="flex flex-wrap items-start gap-3 border-b border-line p-4 dark:border-night-line">
        <span className={`mt-1 h-9 w-1.5 rounded-full ${c.dot}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-bold">{draft.nombre}</h2>
            <Badge color={TIPO_COLOR[draft.tipo]}>{draft.tipo}</Badge>
            <span className="muted font-mono text-xs">
              {draft.id} · v{remote?.version}
            </span>
            {dirty && <Badge color="amber">cambios sin guardar</Badge>}
          </div>
          <p className="muted text-sm">{draft.tagline}</p>
          <p className="muted text-[11px]">actualizado {fecha(remote?.actualizado ?? '')}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button type="button" className="btn-secondary" onClick={validar}>
            <ShieldCheck size={15} aria-hidden /> Validar
          </button>
          <button type="button" className="btn-secondary" onClick={verConEjemplo}>
            <Eye size={15} aria-hidden /> Ver con ejemplo
          </button>
          {!esSupervisor && (
            <button type="button" className="btn-ghost" onClick={duplicar}>
              <Copy size={15} aria-hidden /> Duplicar
            </button>
          )}
          {remote?.tiene_semilla && (
            <button type="button" className="btn-ghost" onClick={restaurar}>
              <RotateCcw size={15} aria-hidden /> Restaurar semilla
            </button>
          )}
          {!esSupervisor && (
            <button type="button" className="btn-ghost text-red-tx dark:text-red" onClick={() => setConfirmDelete(true)} aria-label="Eliminar agente">
              <Trash2 size={15} aria-hidden />
            </button>
          )}
          <button type="button" className="btn-primary" onClick={guardar} disabled={!dirty || saving}>
            {saving ? <Spinner /> : <Save size={15} aria-hidden />} Guardar
          </button>
        </div>
      </div>

      {problemas && (
        <div role="status" className={`border-b px-4 py-2 text-sm ${errores.length ? 'border-red/30 bg-red/5' : 'border-green/30 bg-green/5'}`}>
          {problemas.length === 0 ? (
            <p className="flex items-center gap-1.5 font-medium text-green-tx dark:text-green">
              <CheckCircle2 size={15} aria-hidden /> Sin problemas: listo para guardar.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {problemas.map((p, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <TriangleAlert size={14} className={`mt-0.5 shrink-0 ${p.nivel === 'error' ? 'text-red-tx dark:text-red' : 'text-amber-tx dark:text-amber'}`} aria-hidden />
                  <span>
                    <strong className="font-mono text-xs">{p.campo}</strong> {p.mensaje} <span className="muted text-xs">({p.nivel})</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="px-4">
        <Tabs tabs={tabs} value={tab} onChange={setTab} label="Secciones del agente" />
      </div>

      <div className="scroll-thin min-h-0 flex-1 overflow-auto p-4">
        {tab === 'general' && (
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="ag-nombre" className="label">
                    nombre
                  </label>
                  <input id="ag-nombre" className="input" value={draft.nombre} onChange={(e) => up({ nombre: e.target.value })} />
                </div>
                <div>
                  <label htmlFor="ag-tipo" className="label">
                    tipo
                  </label>
                  <select id="ag-tipo" className="input" value={draft.tipo} disabled={esSupervisor} onChange={(e) => up({ tipo: e.target.value as AgentDef['tipo'] })}>
                    {['router', 'especialista', 'hibrido', 'planner', 'memoria', 'evaluador', 'supervisor'].map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor="ag-tag" className="label">
                  tagline
                </label>
                <input id="ag-tag" className="input" value={draft.tagline} onChange={(e) => up({ tagline: e.target.value })} />
              </div>
              <div>
                <label htmlFor="ag-desc" className="label">
                  descripción
                </label>
                <textarea id="ag-desc" rows={3} className="input" value={draft.descripcion} onChange={(e) => up({ descripcion: e.target.value })} />
              </div>
              {['especialista', 'hibrido', 'planner'].includes(draft.tipo) && (
                <div>
                  <label htmlFor="ag-dom" className="label">
                    dominio · bloque [DOMINIO] (lo lee el router)
                  </label>
                  <textarea id="ag-dom" rows={3} className="input" value={draft.dominio ?? ''} onChange={(e) => up({ dominio: e.target.value })} />
                </div>
              )}
              {['especialista', 'hibrido', 'planner'].includes(draft.tipo) && (
                <div>
                  <label htmlFor="ag-ej" className="label">
                    ejemplo para el router
                  </label>
                  <input id="ag-ej" className="input" value={draft.constantes.ejemplo ?? ''} onChange={(e) => up({ constantes: { ...draft.constantes, ejemplo: e.target.value } })} />
                </div>
              )}
              <div className="flex flex-wrap items-center gap-4">
                <fieldset className="flex items-center gap-1.5">
                  <legend className="label">color</legend>
                  {COLORES.map((col) => (
                    <button
                      key={col}
                      type="button"
                      aria-label={`Color ${col}`}
                      aria-pressed={draft.color === col}
                      onClick={() => up({ color: col })}
                      className={`h-7 w-7 rounded-full border-2 ${draft.color === col ? 'border-ink dark:border-white' : 'border-transparent'}`}
                    >
                      <Dot color={col} className="!h-5 !w-5" />
                    </button>
                  ))}
                </fieldset>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input type="checkbox" className="h-4 w-4 accent-teal" checked={draft.activo} onChange={(e) => up({ activo: e.target.checked })} />
                  activo
                </label>
              </div>
            </div>
            <div className="space-y-4">
              <Ficha titulo="Usar cuando" items={draft.usar_cuando} color="green" />
              <Ficha titulo="Evitar cuando" items={draft.evitar_cuando} color="red" />
              {draft.riesgos.length > 0 && (
                <div>
                  <p className="label">Riesgos y guardrails</p>
                  <ul className="space-y-1.5 text-sm">
                    {draft.riesgos.map((r, i) => (
                      <li key={i} className="rounded-lg bg-panel p-2 dark:bg-night">
                        <span className="font-medium">{r.riesgo}</span>
                        <span className="muted block text-xs">→ {r.guardrail}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <Ficha titulo="Métricas" items={draft.metricas} color="teal" />
            </div>
          </div>
        )}

        {tab === 'pipeline' && esSupervisor && <SupervisorForm agent={draft} onChange={(constantes) => up({ constantes })} />}

        {tab === 'prompt' && (
          <div className="space-y-4">
            <div>
              <p className="label">system</p>
              <PromptEditor label="Prompt system" value={draft.prompt.system} onChange={(v) => upPrompt({ system: v })} minHeight="220px" />
            </div>
            <div>
              <p className="label">user</p>
              <PromptEditor label="Prompt user" value={draft.prompt.user} onChange={(v) => upPrompt({ user: v })} minHeight="90px" />
            </div>
            <VariablesTable agent={draft} onChange={(variables, constantes) => setDraft({ ...draft, constantes: constantes ?? draft.constantes, prompt: { ...draft.prompt, variables } })} />
            {(draft.prompt.salida_schema || ['router', 'evaluador', 'memoria', 'planner'].includes(draft.tipo)) && (
              <SchemaEditor value={draft.prompt.salida_schema} onChange={(s) => upPrompt({ salida_schema: s })} />
            )}
            <div>
              <p className="label">salida esperada (documental)</p>
              <PromptEditor label="Salida esperada" value={draft.prompt.salida_esperada} onChange={(v) => upPrompt({ salida_esperada: v })} minHeight="70px" />
            </div>
          </div>
        )}

        {tab === 'tools' && <ToolPicker agent={draft} onChange={(tools, acciones_escritura) => up({ tools, acciones_escritura })} />}

        {tab === 'limites' && (
          <div className="max-w-2xl">
            <LimitsForm limits={draft.limits} onChange={(limits) => up({ limits })} />
          </div>
        )}

        {tab === 'flow' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="muted text-sm">Canvas de solo lectura generado desde agent.flow.</p>
              {!esSupervisor && (
                <button type="button" className="btn-secondary" onClick={() => up({ flow: flowDesdeTipo(draft) })}>
                  <RefreshCw size={14} aria-hidden /> Regenerar desde el tipo
                </button>
              )}
            </div>
            <div className="h-[460px] rounded-xl border border-line dark:border-night-line">
              <FlowCanvas nodes={draft.flow.nodes} edges={draft.flow.edges} fitKey={`${draft.id}-${draft.flow.nodes.length}`} />
            </div>
          </div>
        )}

        {tab === 'probar' && <Probar agent={draft} dirty={dirty} />}
      </div>

      <Modal open={!!render} onClose={() => setRender(null)} title={`Prompt renderizado con ejemplos · ${draft.id}`} wide>
        {render && (
          <div className="space-y-3">
            {render.faltantes.length > 0 && (
              <p className="text-sm text-amber-tx dark:text-amber">Sin valor de ejemplo: {render.faltantes.join(', ')}</p>
            )}
            <p className="label">system</p>
            <pre className="whitespace-pre-wrap break-words rounded-lg bg-panel p-3 font-mono text-xs leading-relaxed dark:bg-night">{render.system}</pre>
            <p className="label">user</p>
            <pre className="whitespace-pre-wrap break-words rounded-lg bg-panel p-3 font-mono text-xs leading-relaxed dark:bg-night">{render.user}</pre>
          </div>
        )}
      </Modal>
      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Eliminar agente"
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setConfirmDelete(false)}>
              Cancelar
            </button>
            <button type="button" className="btn-danger" onClick={eliminar}>
              <Trash2 size={15} aria-hidden /> Eliminar
            </button>
          </>
        }
      >
        <p className="text-sm">
          ¿Eliminar <strong>{draft.id}</strong>? Si el supervisor lo referencia, el backend lo impedirá. Puedes recuperarlo con <code>make seed</code> si es de semilla.
        </p>
      </Modal>
      <Toast msg={toast?.msg ?? null} kind={toast?.kind} onDone={() => setToast(null)} />
    </section>
  )
}

function Ficha({ titulo, items, color }: { titulo: string; items: string[]; color: string }) {
  if (!items.length) return null
  return (
    <div>
      <p className="label">{titulo}</p>
      <ul className="space-y-1 text-sm">
        {items.map((x, i) => (
          <li key={i} className="flex gap-2">
            <Dot color={color} className="mt-1.5" />
            {x}
          </li>
        ))}
      </ul>
    </div>
  )
}

function SchemaEditor({ value, onChange }: { value: Record<string, unknown> | null; onChange: (v: Record<string, unknown> | null) => void }) {
  const [txt, setTxt] = useState(() => (value ? JSON.stringify(value, null, 2) : ''))
  const [err, setErr] = useState<string | null>(null)
  return (
    <div>
      <p className="label">salida_schema (JSON schema estricto para chat_json)</p>
      <PromptEditor
        label="JSON schema de salida"
        lang="json"
        value={txt}
        minHeight="120px"
        onChange={(v) => {
          setTxt(v)
          if (!v.trim()) {
            setErr(null)
            return onChange(null)
          }
          try {
            onChange(JSON.parse(v))
            setErr(null)
          } catch (e) {
            setErr((e as Error).message)
          }
        }}
      />
      {err && (
        <p role="alert" className="mt-1 text-xs text-red-tx dark:text-red">
          JSON inválido: {err}
        </p>
      )}
    </div>
  )
}

function Probar({ agent, dirty }: { agent: AgentDef; dirty: boolean }) {
  const [cliente, setCliente] = useState(agent.id === 'planner' ? 'c-118' : 'c42')
  const chat = useLocalChat(agent.id, cliente)
  const { data: clientes } = useQuery({ queryKey: ['clientes'], queryFn: api.clientes })
  const sug = [String(agent.constantes.ejemplo ?? ''), ...(agent.prompt.variables.find((v) => v.nombre === 'mensaje')?.ejemplo ? [agent.prompt.variables.find((v) => v.nombre === 'mensaje')!.ejemplo] : [])].filter(Boolean)
  return (
    <div className="space-y-2">
      <p className="muted text-sm">
        Corre <strong>solo este agente</strong> (el router queda fijado en <code>{agent.id}</code>); útil para iterar el prompt.
        {dirty && <span className="text-amber-tx dark:text-amber"> Guarda primero: se prueba la versión guardada.</span>}
      </p>
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="h-[520px]">
          <ChatPanel
            messages={chat.messages}
            busy={chat.busy}
            onSend={chat.send}
            onConfirm={chat.confirm}
            sugerencias={[...new Set(sug)].slice(0, 3)}
            header={
              <div className="flex items-end gap-2 border-b border-line p-3 dark:border-night-line">
                <div className="flex-1">
                  <label htmlFor="probar-cli" className="label">
                    Cliente
                  </label>
                  <select id="probar-cli" className="input" value={cliente} onChange={(e) => setCliente(e.target.value)}>
                    {(clientes ?? []).map((c) => (
                      <option key={c.cliente_id} value={c.cliente_id}>
                        {c.cliente_id} · {c.nombre}
                      </option>
                    ))}
                  </select>
                </div>
                <button type="button" className="btn-secondary" onClick={chat.reset}>
                  <RotateCcw size={14} aria-hidden /> Reiniciar
                </button>
              </div>
            }
          />
        </div>
        <TraceConsole events={chat.events} className="h-[520px]" />
      </div>
    </div>
  )
}
