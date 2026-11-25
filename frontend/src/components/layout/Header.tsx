import { useQuery } from '@tanstack/react-query'
import { CircleHelp, Moon, Sun, Workflow } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { api } from '../../api/client'
import { usePlatformStore } from '../../store/usePlatformStore'
import { Kbd, Modal } from '../common'

const TABS = [
  { to: '/', label: 'Playground', end: true },
  { to: '/agentes', label: 'Agentes' },
  { to: '/tools', label: 'Tools' },
  { to: '/runs', label: 'Runs' },
  { to: '/memoria', label: 'Memoria' },
  { to: '/evaluacion', label: 'Evaluación' },
  { to: '/prompts', label: 'Prompts' },
]

function Health() {
  const { data, isError } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 10000 })
  const redis = !!data?.redis && !isError
  const llm = data?.modo_llm
  const llmColor = llm === 'openai' ? 'bg-green' : llm === 'demo' ? 'bg-amber' : 'bg-red'
  const llmText = llm === 'openai' ? 'OpenAI' : llm === 'demo' ? 'OpenAI · demo' : 'OpenAI'
  return (
    <div className="flex items-center gap-3 text-xs" aria-label="Estado del sistema">
      <span className="flex items-center gap-1.5" title={redis ? 'Redis conectado' : 'Redis sin conexión'}>
        <span aria-hidden className={`h-2 w-2 rounded-full ${redis ? 'bg-green' : 'bg-red'}`} />
        Redis<span className="sr-only">{redis ? ' conectado' : ' sin conexión'}</span>
      </span>
      <span
        className="flex items-center gap-1.5"
        title={llm === 'demo' ? 'Sin OPENAI_API_KEY: LLM simulado determinístico (las tools, reglas y Redis son reales)' : llm === 'openai' ? 'OpenAI configurado' : 'Sin LLM'}
      >
        <span aria-hidden className={`h-2 w-2 rounded-full ${llmColor}`} />
        {llmText}
      </span>
      <span className="muted hidden tabular lg:inline" title="Versión de agentes (agents:version)">
        v{data?.agents_version ?? '—'}
      </span>
    </div>
  )
}

export function Header() {
  const { dark, toggleDark, helpOpen, setHelp } = usePlatformStore()
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-white/95 backdrop-blur dark:border-night-line dark:bg-night-card/95">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Saltar al contenido
      </a>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-white dark:bg-teal dark:text-ink">
            <Workflow size={17} aria-hidden />
          </span>
          <div className="leading-tight">
            <h1 className="text-[15px] font-bold">Agent Explorer Platform</h1>
            <p className="muted text-[11px]">Sesión 4 · Agent Tech · UAI + XeraX</p>
          </div>
        </div>
        <nav aria-label="Secciones" className="order-3 flex w-full flex-wrap gap-1 py-1 lg:order-none lg:w-auto lg:min-w-0 lg:flex-1 lg:flex-nowrap lg:overflow-x-auto xl:justify-center">
          {TABS.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-2 py-2 text-sm font-medium transition-colors xl:px-3 ${
                  isActive ? 'bg-ink text-white dark:bg-teal dark:text-ink' : 'text-muted hover:bg-panel hover:text-ink dark:text-night-muted dark:hover:bg-night dark:hover:text-night-text'
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <Health />
          <button type="button" className="btn-icon" onClick={toggleDark} aria-label={dark ? 'Activar modo claro' : 'Activar modo oscuro'}>
            {dark ? <Sun size={17} aria-hidden /> : <Moon size={17} aria-hidden />}
          </button>
          <button type="button" className="btn-icon" onClick={() => setHelp(true)} aria-label="Atajos de teclado y ayuda">
            <CircleHelp size={17} aria-hidden />
          </button>
        </div>
      </div>
      <Modal open={helpOpen} onClose={() => setHelp(false)} title="Atajos y glosario" wide>
        <div className="grid gap-6 md:grid-cols-2">
          <section>
            <h3 className="label">Atajos</h3>
            <ul className="space-y-2 text-sm">
              <li><Kbd>Enter</Kbd> enviar mensaje · <Kbd>Shift</Kbd>+<Kbd>Enter</Kbd> nueva línea</li>
              <li><Kbd>Ctrl/⌘</Kbd>+<Kbd>K</Kbd> cambiar de cliente</li>
              <li><Kbd>T</Kbd> enfocar la traza</li>
              <li><Kbd>?</Kbd> abrir esta ayuda · <Kbd>Esc</Kbd> cerrar</li>
            </ul>
            <h3 className="label mt-5">Colores del flow</h3>
            <ul className="space-y-1 text-sm">
              <li><span className="font-semibold text-teal-tx dark:text-teal">teal</span> LLM (router, especialistas)</li>
              <li><span className="font-semibold text-amber-tx dark:text-amber">ámbar</span> tools y reglas en código</li>
              <li><span className="font-semibold text-violet-tx dark:text-violet">violeta</span> memoria y planner</li>
              <li><span className="font-semibold text-red-tx dark:text-red">rojo</span> evaluador, humano y nodo activo</li>
              <li><span className="font-semibold text-green-tx dark:text-green">verde</span> entrada / salida / completado</li>
            </ul>
          </section>
          <section>
            <h3 className="label">Glosario</h3>
            <dl className="space-y-1.5 text-sm">
              {[
                ['Agente', 'sistema que decide el siguiente paso, actúa con herramientas, observa y repite hasta cumplir un objetivo.'],
                ['Tool calling', 'el modelo pide una herramienta con argumentos JSON; la aplicación la valida y ejecuta.'],
                ['Router', 'clasificador que elige al especialista.'],
                ['Especialista', 'agente de un solo dominio con pocas herramientas.'],
                ['Planner–Executor', 'un agente planifica, otros ejecutan, uno verifica.'],
                ['Memory loop', 'leer memoria antes de razonar y escribir después de responder.'],
                ['Híbrido', 'reglas en código antes y después del modelo; el modelo solo redacta.'],
                ['Guardrail', 'límite impuesto por la aplicación (permisos, presupuesto, reglas), nunca por el prompt.'],
                ['LLM-as-judge', 'un segundo modelo que califica la respuesta con una rúbrica.'],
                ['Traza', 'registro paso a paso de pensamientos, llamadas, observaciones, reglas y veredictos de un turno.'],
              ].map(([t, d]) => (
                <div key={t}>
                  <dt className="inline font-semibold">{t}: </dt>
                  <dd className="muted inline">{d}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </Modal>
    </header>
  )
}
