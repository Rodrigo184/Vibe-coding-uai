import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { flowDesdeTipo } from '../../lib/flowLayout'
import type { AgentDef, AgentType } from '../../types'
import { Badge, Dot, Modal, Spinner, TIPO_COLOR } from '../common'
import { ToolPicker } from './ToolPicker'

export function AgentList() {
  const { data: agents = [], isLoading } = useQuery({ queryKey: ['agents'], queryFn: api.agents })
  const [wizard, setWizard] = useState(false)
  return (
    <aside className="card flex min-h-0 flex-col overflow-hidden" aria-label="Lista de agentes">
      <div className="flex items-center justify-between border-b border-line px-3 py-2 dark:border-night-line">
        <h2 className="text-sm font-semibold">Agentes ({agents.length})</h2>
        <button type="button" className="btn-primary !min-h-[32px] text-xs" onClick={() => setWizard(true)}>
          <Plus size={14} aria-hidden /> Nuevo agente
        </button>
      </div>
      <nav className="scroll-thin min-h-0 flex-1 overflow-auto p-1.5">
        {isLoading && (
          <p className="muted flex items-center gap-2 p-3 text-sm">
            <Spinner /> cargando…
          </p>
        )}
        {agents.map((a) => (
          <NavLink
            key={a.id}
            to={`/agentes/${a.id}`}
            className={({ isActive }) =>
              `flex items-start gap-2 rounded-lg px-2.5 py-2 transition-colors ${isActive ? 'bg-panel ring-1 ring-line dark:bg-night dark:ring-night-line' : 'hover:bg-panel dark:hover:bg-night'}`
            }
          >
            <Dot color={a.color} className="mt-1.5" />
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5">
                <span className="truncate text-sm font-semibold">{a.nombre}</span>
                {!a.activo && <Badge color="muted">inactivo</Badge>}
              </span>
              <span className="muted block truncate text-xs">{a.tagline}</span>
            </span>
            <span className="flex flex-col items-end gap-0.5">
              <Badge color={TIPO_COLOR[a.tipo]}>{a.tipo}</Badge>
              <span className="muted font-mono text-[10.5px]">v{a.version}</span>
            </span>
          </NavLink>
        ))}
      </nav>
      <NewAgentWizard open={wizard} onClose={() => setWizard(false)} />
    </aside>
  )
}

const TIPOS: { tipo: AgentType; label: string; desc: string; plantilla: string }[] = [
  { tipo: 'especialista', label: 'Especialista', desc: 'Un dominio, pocas tools, loop ReAct con tool calling. Ej.: logística.', plantilla: 'analista' },
  { tipo: 'hibrido', label: 'Híbrido', desc: 'Reglas en código antes y después; el modelo solo redacta.', plantilla: 'ventas' },
  { tipo: 'planner', label: 'Planner', desc: 'Planifica pasos con dependencias, ejecuta y verifica.', plantilla: 'planner' },
  { tipo: 'router', label: 'Router', desc: 'Clasifica y deriva (salida JSON).', plantilla: 'router' },
  { tipo: 'evaluador', label: 'Evaluador', desc: 'LLM-as-judge con rúbrica.', plantilla: 'evaluador' },
  { tipo: 'memoria', label: 'Memoria', desc: 'Extrae hechos y resume episodios.', plantilla: 'extractor' },
]

function NewAgentWizard({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [step, setStep] = useState(1)
  const [tipo, setTipo] = useState<AgentType>('especialista')
  const [id, setId] = useState('logistica')
  const [nombre, setNombre] = useState('Logística')
  const [dominio, setDominio] = useState('Despachos, envíos y horarios de entrega a domicilio. Excluye: cobros y reembolsos.')
  const [ejemplo, setEjemplo] = useState('¿cuánto demora el despacho a domicilio?')
  const [draft, setDraft] = useState<AgentDef | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const qc = useQueryClient()
  const nav = useNavigate()

  const close = () => {
    setStep(1)
    setDraft(null)
    setError(null)
    onClose()
  }
  const toStep3 = async () => {
    setError(null)
    if (!/^[a-z][a-z0-9_-]{1,40}$/.test(id)) return setError('El id debe ser un slug en minúsculas (a-z, 0-9, _ o -), p. ej. "logistica".')
    const t = TIPOS.find((x) => x.tipo === tipo)!
    const base = await api.agent(t.plantilla)
    setDraft({
      ...base,
      id,
      nombre,
      tagline: dominio.split('.')[0].toLowerCase(),
      dominio,
      descripcion: `Agente ${tipo} creado desde la UI a partir de la plantilla "${t.plantilla}".`,
      tools: tipo === 'especialista' ? ['consultar_stock', 'sugerir_sustitutos'] : base.tools,
      acciones_escritura: tipo === 'especialista' ? [] : base.acciones_escritura,
      constantes: { ...base.constantes, ejemplo },
      version: 1,
    })
    setStep(3)
  }
  const crear = async () => {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      await api.createAgent({ ...draft, flow: flowDesdeTipo(draft) })
      await qc.invalidateQueries({ queryKey: ['agents'] })
      close()
      nav(`/agentes/${draft.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title={`Nuevo agente · paso ${step} de 3`}
      wide={step === 3}
      footer={
        <>
          {step > 1 && (
            <button type="button" className="btn-secondary" onClick={() => setStep(step - 1)}>
              <ChevronLeft size={15} aria-hidden /> Atrás
            </button>
          )}
          {step === 1 && (
            <button type="button" className="btn-primary" onClick={() => setStep(2)}>
              Siguiente <ChevronRight size={15} aria-hidden />
            </button>
          )}
          {step === 2 && (
            <button type="button" className="btn-primary" onClick={toStep3}>
              Siguiente <ChevronRight size={15} aria-hidden />
            </button>
          )}
          {step === 3 && (
            <button type="button" className="btn-primary" onClick={crear} disabled={saving}>
              {saving ? <Spinner /> : <Plus size={15} aria-hidden />} Crear agente
            </button>
          )}
        </>
      }
    >
      {step === 1 && (
        <fieldset>
          <legend className="label">1 · Tipo de agente</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {TIPOS.map((t) => (
              <label key={t.tipo} className={`cursor-pointer rounded-lg border p-3 ${tipo === t.tipo ? 'border-teal-dk bg-teal/5 dark:border-teal' : 'border-line dark:border-night-line'}`}>
                <input type="radio" name="tipo" className="sr-only" checked={tipo === t.tipo} onChange={() => setTipo(t.tipo)} />
                <span className="flex items-center gap-2 font-semibold">
                  <Dot color={TIPO_COLOR[t.tipo]} /> {t.label}
                </span>
                <span className="muted mt-1 block text-xs">{t.desc}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
      {step === 2 && (
        <div className="space-y-3">
          <p className="label">2 · Nombre y dominio</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="nw-id" className="label">
                id (slug)
              </label>
              <input id="nw-id" className="input font-mono" value={id} onChange={(e) => setId(e.target.value.toLowerCase())} />
            </div>
            <div>
              <label htmlFor="nw-nombre" className="label">
                nombre
              </label>
              <input id="nw-nombre" className="input" value={nombre} onChange={(e) => setNombre(e.target.value)} />
            </div>
          </div>
          <div>
            <label htmlFor="nw-dom" className="label">
              dominio (qué cubre y qué excluye)
            </label>
            <textarea id="nw-dom" rows={3} className="input" value={dominio} onChange={(e) => setDominio(e.target.value)} />
            <p className="muted mt-1 text-xs">El router lo lee en la lista de especialistas: sé concreto.</p>
          </div>
          <div>
            <label htmlFor="nw-ej" className="label">
              mensaje de ejemplo
            </label>
            <input id="nw-ej" className="input" value={ejemplo} onChange={(e) => setEjemplo(e.target.value)} />
          </div>
          {error && (
            <p role="alert" className="text-sm text-red-tx dark:text-red">
              {error}
            </p>
          )}
        </div>
      )}
      {step === 3 && draft && (
        <div className="space-y-3">
          <p className="label">3 · Tools</p>
          <ToolPicker agent={draft} onChange={(tools, esc) => setDraft({ ...draft, tools, acciones_escritura: esc })} />
          <p className="muted text-xs">
            Después de crearlo, agrégalo a la lista de especialistas del <strong>supervisor</strong> para que el router pueda elegirlo (sin reiniciar el backend).
          </p>
          {error && (
            <p role="alert" className="text-sm text-red-tx dark:text-red">
              {error}
            </p>
          )}
        </div>
      )}
    </Modal>
  )
}
