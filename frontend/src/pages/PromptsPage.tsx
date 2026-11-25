import { useQueries, useQuery } from '@tanstack/react-query'
import { Download, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Badge, CopyButton, Dot, Spinner, TIPO_COLOR } from '../components/common'
import { download, exportMd, exportTxt } from '../lib/exportPrompts'
import type { AgentDef } from '../types'

function bloque(a: AgentDef) {
  return `### ${a.id} · ${a.tipo}\n--- SYSTEM ---\n${a.prompt.system}\n--- USER ---\n${a.prompt.user}`
}

export default function PromptsPage() {
  const { data: list = [] } = useQuery({ queryKey: ['agents'], queryFn: api.agents })
  const { data: tools = [] } = useQuery({ queryKey: ['tools'], queryFn: api.tools })
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.health })
  const activos = list.filter((a) => a.activo)
  const full = useQueries({ queries: activos.map((a) => ({ queryKey: ['agent', a.id], queryFn: () => api.agent(a.id) })) })
  const agents = full.map((q) => q.data).filter(Boolean) as AgentDef[]
  const loading = full.some((q) => q.isLoading)
  const [q, setQ] = useState('')
  const filtrados = useMemo(() => {
    const t = q.toLowerCase().trim()
    if (!t) return agents
    return agents.filter((a) => [a.id, a.nombre, a.prompt.system, a.prompt.user].some((x) => x.toLowerCase().includes(t)))
  }, [agents, q])
  const fecha = new Date().toISOString().slice(0, 10)

  return (
    <div className="space-y-3 p-3">
      <section className="card flex flex-wrap items-end gap-3 p-4">
        <div className="mr-auto">
          <h2 className="text-base font-semibold">Prompts de los agentes activos</h2>
          <p className="muted text-sm">Contenido docente de la semilla; edítalos desde Agentes. Exporta todo para la clase o el laboratorio.</p>
        </div>
        <div className="relative min-w-[240px]">
          <label htmlFor="pq" className="sr-only">
            Buscar en prompts
          </label>
          <Search size={15} className="muted pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden />
          <input id="pq" className="input pl-8" placeholder="Buscar en prompts…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex gap-1.5">
          <button type="button" className="btn-primary" disabled={loading} onClick={() => download(`prompts-agentes-${fecha}.txt`, exportTxt(agents, tools, health?.agents_version ?? null))}>
            <Download size={15} aria-hidden /> .txt
          </button>
          <button type="button" className="btn-secondary" disabled={loading} onClick={() => download(`prompts-agentes-${fecha}.md`, exportMd(agents), 'text/markdown')}>
            <Download size={15} aria-hidden /> .md
          </button>
          <button type="button" className="btn-secondary" disabled={loading} onClick={() => download(`prompts-agentes-${fecha}.json`, JSON.stringify(agents, null, 2), 'application/json')}>
            <Download size={15} aria-hidden /> .json
          </button>
        </div>
      </section>
      {loading && (
        <p className="muted flex items-center gap-2">
          <Spinner /> cargando prompts…
        </p>
      )}
      {filtrados.map((a) => (
        <article key={a.id} className="card overflow-hidden">
          <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2 dark:border-night-line">
            <Dot color={a.color} />
            <h3 className="font-semibold">{a.nombre}</h3>
            <Badge color={TIPO_COLOR[a.tipo]}>{a.tipo}</Badge>
            <span className="muted font-mono text-xs">
              {a.id} · v{a.version}
            </span>
            <span className="ml-auto flex gap-1">
              <CopyButton text={bloque(a)} label="Copiar" />
              <Link to={`/agentes/${a.id}`} className="btn-ghost">
                Editar
              </Link>
            </span>
          </header>
          <div className="grid gap-3 p-4 lg:grid-cols-[2fr_1fr]">
            <div className="space-y-2">
              <p className="label">system</p>
              <pre className="scroll-thin max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-panel p-3 font-mono text-[11.5px] leading-relaxed dark:bg-night">{a.prompt.system}</pre>
              <p className="label">user</p>
              <pre className="whitespace-pre-wrap break-words rounded-lg bg-panel p-3 font-mono text-[11.5px] leading-relaxed dark:bg-night">{a.prompt.user}</pre>
            </div>
            <div className="space-y-2">
              <p className="label">variables</p>
              <ul className="space-y-1 text-xs">
                {a.prompt.variables.map((v) => (
                  <li key={v.nombre}>
                    <code className="font-semibold text-violet-tx dark:text-violet">{`{{${v.nombre}}}`}</code> <span className="muted">· {v.origen} · {v.descripcion}</span>
                  </li>
                ))}
              </ul>
              {a.tools.length > 0 && (
                <>
                  <p className="label">tools</p>
                  <div className="flex flex-wrap gap-1">
                    {a.tools.map((t) => (
                      <Badge key={t} color={a.acciones_escritura.includes(t) ? 'amber' : 'green'}>
                        {t}
                      </Badge>
                    ))}
                  </div>
                </>
              )}
              <p className="label">salida esperada</p>
              <pre className="scroll-thin max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-panel p-2 font-mono text-[11px] dark:bg-night">{a.prompt.salida_esperada}</pre>
            </div>
          </div>
        </article>
      ))}
    </div>
  )
}
