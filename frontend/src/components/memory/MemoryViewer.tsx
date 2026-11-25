import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, Plus, Save, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Badge, EmptyState, Modal, Spinner, Toast, clp } from '../common'

export function MemoryViewer({ clienteId }: { clienteId: string }) {
  const { data, isLoading, refetch } = useQuery({ queryKey: ['memory', clienteId], queryFn: () => api.memory(clienteId) })
  const [rows, setRows] = useState<{ clave: string; valor: string; fuente: string; fecha: string }[]>([])
  const [toast, setToast] = useState<{ msg: string; kind: 'ok' | 'error' } | null>(null)
  const [borrar, setBorrar] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const qc = useQueryClient()

  useEffect(() => setRows(data?.perfil ?? []), [data])

  if (isLoading || !data) return <p className="muted flex items-center gap-2 p-4"><Spinner /> cargando memoria…</p>

  const dirty = JSON.stringify(rows.map((r) => [r.clave, r.valor])) !== JSON.stringify((data.perfil ?? []).map((r) => [r.clave, r.valor]))
  const guardar = async () => {
    const r = await api.putPerfil(clienteId, Object.fromEntries(rows.filter((x) => x.clave).map((x) => [x.clave, x.valor])))
    setToast(r.descartados.length ? { msg: `Descartados por seguridad: ${r.descartados.join('; ')}`, kind: 'error' } : { msg: 'Perfil guardado', kind: 'ok' })
    refetch()
  }
  const cerrar = async (sid: string) => {
    setBusy(sid)
    try {
      const r = await api.cerrarSesion(clienteId, sid)
      setToast({ msg: `Episodio guardado: ${r.episodio}`, kind: 'ok' })
      refetch()
    } catch (e) {
      setToast({ msg: (e as Error).message, kind: 'error' })
    } finally {
      setBusy(null)
    }
  }
  const borrarTodo = async () => {
    await api.deleteMemory(clienteId)
    setBorrar(false)
    setToast({ msg: 'Memoria del cliente borrada (derecho al olvido)', kind: 'ok' })
    await qc.invalidateQueries({ queryKey: ['memory', clienteId] })
  }

  return (
    <div className="space-y-3">
      {data.cliente && (
        <section className="card flex flex-wrap items-center gap-x-6 gap-y-2 p-4 text-sm">
          <div>
            <p className="label">Cliente (datos del negocio)</p>
            <p className="font-semibold">{data.cliente.nombre}</p>
          </div>
          <div>
            <p className="label">Tienda · canal</p>
            <p>
              {data.cliente.tienda} · {data.cliente.canal}
            </p>
          </div>
          <div>
            <p className="label">Edad verificada</p>
            <Badge color={data.cliente.edad_verificada ? 'green' : 'amber'}>{data.cliente.edad_verificada ? 'sí' : 'no'}</Badge>
          </div>
          <div>
            <p className="label">Cupo crédito</p>
            <p className="tabular">{clp(data.cliente.cupo_credito)}</p>
          </div>
          <button type="button" className="btn-danger ml-auto" onClick={() => setBorrar(true)}>
            <Trash2 size={15} aria-hidden /> Borrar memoria del cliente
          </button>
        </section>
      )}
      <div className="grid gap-3 xl:grid-cols-2">
        <section className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-2 dark:border-night-line">
            <h2 className="text-sm font-semibold">
              Perfil <span className="muted font-normal">· HASH cliente:{clienteId}:perfil</span>
            </h2>
            <div className="flex gap-1">
              <button type="button" className="btn-ghost !min-h-[30px] text-xs" onClick={() => setRows([...rows, { clave: '', valor: '', fuente: 'editado en la UI', fecha: '' }])}>
                <Plus size={13} aria-hidden /> Hecho
              </button>
              <button type="button" className="btn-primary !min-h-[30px] text-xs" disabled={!dirty} onClick={guardar}>
                <Save size={13} aria-hidden /> Guardar
              </button>
            </div>
          </div>
          {rows.length === 0 ? (
            <EmptyState title="Sin hechos guardados" />
          ) : (
            <div className="overflow-x-auto">
              <table className="table-base">
                <thead>
                  <tr>
                    <th>Clave</th>
                    <th>Valor</th>
                    <th>Fuente</th>
                    <th>Fecha</th>
                    <th><span className="sr-only">Quitar</span></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      <td>
                        <input aria-label="Clave" className="input !py-1 font-mono text-xs" value={r.clave} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, clave: e.target.value } : x)))} />
                      </td>
                      <td>
                        <input aria-label={`Valor de ${r.clave}`} className="input !py-1 text-xs" value={r.valor} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, valor: e.target.value } : x)))} />
                      </td>
                      <td className="muted max-w-[180px] truncate text-xs" title={r.fuente}>
                        {r.fuente}
                      </td>
                      <td className="muted whitespace-nowrap text-xs tabular">{r.fecha}</td>
                      <td>
                        <button type="button" className="btn-icon h-8 w-8" aria-label={`Quitar ${r.clave}`} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                          <Trash2 size={14} aria-hidden />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="card overflow-hidden">
          <div className="border-b border-line px-4 py-2 dark:border-night-line">
            <h2 className="text-sm font-semibold">
              Episodios <span className="muted font-normal">· LIST cliente:{clienteId}:episodios (más reciente arriba)</span>
            </h2>
          </div>
          {data.episodios.length === 0 ? (
            <EmptyState title="Sin episodios">Cierra una sesión para que el extractor la resuma en un episodio.</EmptyState>
          ) : (
            <ol className="divide-y divide-line dark:divide-night-line">
              {[...data.episodios].reverse().map((e, i) => (
                <li key={i} className="px-4 py-2 text-sm">
                  <span className="muted mr-2 font-mono text-xs">{e.fecha}</span>
                  {e.resumen}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
      <section className="card overflow-hidden">
        <div className="border-b border-line px-4 py-2 dark:border-night-line">
          <h2 className="text-sm font-semibold">
            Sesiones activas <span className="muted font-normal">· LIST sesion:{'{id}'}:historial (TTL 24 h, últimos 20 turnos)</span>
          </h2>
        </div>
        {data.sesiones.length === 0 ? (
          <EmptyState title="Sin sesiones activas" />
        ) : (
          <div className="grid gap-3 p-3 lg:grid-cols-2">
            {data.sesiones.map((s) => (
              <div key={s.sesion_id} className="rounded-lg border border-line dark:border-night-line">
                <div className="flex items-center justify-between border-b border-line px-3 py-1.5 dark:border-night-line">
                  <span className="font-mono text-xs font-semibold">{s.sesion_id}</span>
                  <button type="button" className="btn-secondary !min-h-[30px] text-xs" onClick={() => cerrar(s.sesion_id)} disabled={busy === s.sesion_id}>
                    {busy === s.sesion_id ? <Spinner /> : <Archive size={13} aria-hidden />} Cerrar sesión
                  </button>
                </div>
                <ol className="scroll-thin max-h-60 space-y-1 overflow-auto p-3 text-xs">
                  {s.turnos.map((t, i) => (
                    <li key={i}>
                      <span className={`font-semibold ${t.rol === 'user' ? 'text-ink dark:text-night-text' : 'text-teal-tx dark:text-teal'}`}>{t.rol}:</span> {t.texto}
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        )}
      </section>
      <Modal
        open={borrar}
        onClose={() => setBorrar(false)}
        title="Borrar memoria del cliente"
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setBorrar(false)}>
              Cancelar
            </button>
            <button type="button" className="btn-danger" onClick={borrarTodo}>
              <Trash2 size={15} aria-hidden /> Borrar todo
            </button>
          </>
        }
      >
        <p className="text-sm">
          Se borrarán el perfil, los episodios y todas las sesiones de <strong>{clienteId}</strong>. Esta acción es <strong>irreversible</strong> (derecho al olvido). Los datos del
          negocio (pedidos, cobros) no se tocan.
        </p>
      </Modal>
      <Toast msg={toast?.msg ?? null} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  )
}
