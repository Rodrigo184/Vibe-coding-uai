import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { Badge, EmptyState, ESTADO_COLOR, Spinner, VEREDICTO_COLOR, fecha, ms, usd } from '../common'

export function RunsTable() {
  const [cliente, setCliente] = useState('')
  const [estado, setEstado] = useState('')
  const { data: runs = [], isLoading, refetch, isFetching } = useQuery({
    queryKey: ['runs', cliente, estado],
    queryFn: () => api.runs({ limit: 200, cliente_id: cliente, estado }),
    refetchInterval: 15000,
  })
  const nav = useNavigate()
  return (
    <section className="card flex min-h-0 flex-col overflow-hidden">
      <div className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3 dark:border-night-line">
        <div className="mr-auto">
          <h2 className="text-base font-semibold">Runs</h2>
          <p className="muted text-sm">Cada turno queda guardado 7 días en Redis con su traza completa.</p>
        </div>
        <div>
          <label htmlFor="f-cli" className="label">
            cliente
          </label>
          <select id="f-cli" className="input" value={cliente} onChange={(e) => setCliente(e.target.value)}>
            <option value="">todos</option>
            <option value="c42">c42</option>
            <option value="c-118">c-118</option>
            <option value="c77">c77</option>
          </select>
        </div>
        <div>
          <label htmlFor="f-est" className="label">
            estado
          </label>
          <select id="f-est" className="input" value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="">todos</option>
            {['ok', 'pendiente_confirmacion', 'humano', 'error', 'limite'].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <button type="button" className="btn-secondary" onClick={() => refetch()} aria-label="Actualizar runs">
          {isFetching ? <Spinner /> : <RefreshCw size={14} aria-hidden />}
        </button>
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-auto">
        {isLoading ? (
          <p className="muted flex items-center gap-2 p-4">
            <Spinner /> cargando…
          </p>
        ) : runs.length === 0 ? (
          <EmptyState title="Aún no hay runs">Conversa en el Playground o corre una evaluación.</EmptyState>
        ) : (
          <table className="table-base">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Cliente</th>
                <th>Mensaje</th>
                <th>Agente</th>
                <th>Veredicto</th>
                <th>Estado</th>
                <th className="text-right">Costo</th>
                <th className="text-right">Latencia</th>
                <th className="text-right">Ver.</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.run_id}
                  tabIndex={0}
                  onClick={() => nav(`/runs/${r.run_id}`)}
                  onKeyDown={(e) => e.key === 'Enter' && nav(`/runs/${r.run_id}`)}
                  className="cursor-pointer hover:bg-panel focus:bg-panel dark:hover:bg-night dark:focus:bg-night"
                >
                  <td className="whitespace-nowrap tabular text-xs">{fecha(r.creado)}</td>
                  <td className="font-mono text-xs">{r.cliente_id}</td>
                  <td className="max-w-[340px] truncate" title={r.mensaje}>
                    {r.mensaje}
                  </td>
                  <td>{r.agente ? <Badge color="teal">{r.agente}</Badge> : '—'}</td>
                  <td>{r.veredicto ? <Badge color={VEREDICTO_COLOR[r.veredicto] ?? 'muted'}>{r.veredicto}</Badge> : '—'}</td>
                  <td>
                    <Badge color={ESTADO_COLOR[r.estado]}>{r.estado.replace('_', ' ')}</Badge>
                  </td>
                  <td className="text-right tabular">{usd(r.costo_usd)}</td>
                  <td className="text-right tabular">{ms(r.latencia_ms)}</td>
                  <td className="text-right font-mono text-xs">v{r.version_agentes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
