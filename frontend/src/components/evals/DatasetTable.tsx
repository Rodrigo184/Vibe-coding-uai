import { useQueryClient } from '@tanstack/react-query'
import { Download, Plus, Save, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { download } from '../../lib/exportPrompts'
import type { EvalCase } from '../../types'
import { Badge, Toast } from '../common'

const ETQ_COLOR = { normal: 'green', borde: 'amber', adversarial: 'red' } as const

export function DatasetTable({ cases, selected, onSelect }: { cases: EvalCase[]; selected: Set<string>; onSelect: (s: Set<string>) => void }) {
  const [rows, setRows] = useState<EvalCase[]>(cases)
  const [toast, setToast] = useState<{ msg: string; kind: 'ok' | 'error' } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const qc = useQueryClient()
  useEffect(() => setRows(cases), [cases])
  const dirty = JSON.stringify(rows) !== JSON.stringify(cases)
  const set = (i: number, p: Partial<EvalCase>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r)))
  const list = (s: string) =>
    s
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean)

  const guardar = async () => {
    try {
      await api.putDataset(rows)
      setToast({ msg: `Dataset guardado (${rows.length} casos)`, kind: 'ok' })
      qc.invalidateQueries({ queryKey: ['dataset'] })
    } catch (e) {
      setToast({ msg: (e as Error).message, kind: 'error' })
    }
  }
  const importar = async (f: File) => {
    try {
      const data = JSON.parse(await f.text())
      if (!Array.isArray(data)) throw new Error('el JSON debe ser una lista de casos')
      setRows(data)
      setToast({ msg: `${data.length} casos importados: revisa y guarda`, kind: 'ok' })
    } catch (e) {
      setToast({ msg: `No se pudo importar: ${(e as Error).message}`, kind: 'error' })
    }
  }
  const all = rows.length > 0 && rows.every((r) => selected.has(r.id))

  return (
    <section className="card flex min-h-0 flex-col overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2 dark:border-night-line">
        <h2 className="mr-auto text-sm font-semibold">
          Dataset <span className="muted font-normal">({rows.length} casos · {selected.size} seleccionados)</span>
        </h2>
        <button
          type="button"
          className="btn-ghost !min-h-[30px] text-xs"
          onClick={() =>
            setRows([
              ...rows,
              { id: `nuevo-${rows.length + 1}`, etiqueta: 'normal', cliente_id: 'c42', sesion_nueva: true, mensaje: '', agente_esperado: 'asistente', tools_esperadas: [], respuesta_esperada: '', reglas_a_verificar: [], debe_pedir_confirmacion: false },
            ])
          }
        >
          <Plus size={13} aria-hidden /> Caso
        </button>
        <button type="button" className="btn-ghost !min-h-[30px] text-xs" onClick={() => fileRef.current?.click()}>
          <Upload size={13} aria-hidden /> Importar
        </button>
        <input ref={fileRef} type="file" accept="application/json" className="hidden" onChange={(e) => e.target.files?.[0] && importar(e.target.files[0])} />
        <button type="button" className="btn-ghost !min-h-[30px] text-xs" onClick={() => download('dataset.json', JSON.stringify(rows, null, 2), 'application/json')}>
          <Download size={13} aria-hidden /> Exportar
        </button>
        <button type="button" className="btn-primary !min-h-[30px] text-xs" disabled={!dirty} onClick={guardar}>
          <Save size={13} aria-hidden /> Guardar
        </button>
      </div>
      <div className="scroll-thin max-h-[440px] overflow-auto">
        <table className="table-base text-xs">
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  aria-label="Seleccionar todos los casos"
                  className="h-4 w-4 accent-teal"
                  checked={all}
                  onChange={(e) => onSelect(new Set(e.target.checked ? rows.map((r) => r.id) : []))}
                />
              </th>
              <th>id</th>
              <th>etiqueta</th>
              <th>cliente</th>
              <th>mensaje</th>
              <th>agente esperado</th>
              <th>tools esperadas</th>
              <th>respuesta esperada</th>
              <th>reglas</th>
              <th title="debe pedir confirmación">conf.</th>
              <th><span className="sr-only">Quitar</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Seleccionar ${r.id}`}
                    className="h-4 w-4 accent-teal"
                    checked={selected.has(r.id)}
                    onChange={(e) => {
                      const s = new Set(selected)
                      if (e.target.checked) s.add(r.id)
                      else s.delete(r.id)
                      onSelect(s)
                    }}
                  />
                </td>
                <td className="min-w-[80px]">
                  <input aria-label="id" className="input !px-1.5 !py-1 font-mono text-xs" value={r.id} onChange={(e) => set(i, { id: e.target.value })} />
                </td>
                <td>
                  <select aria-label={`Etiqueta de ${r.id}`} className="input min-w-[112px] !px-1.5 !py-1 text-xs" value={r.etiqueta} onChange={(e) => set(i, { etiqueta: e.target.value as EvalCase['etiqueta'] })}>
                    <option>normal</option>
                    <option>borde</option>
                    <option>adversarial</option>
                  </select>
                  <span className="sr-only">
                    <Badge color={ETQ_COLOR[r.etiqueta]}>{r.etiqueta}</Badge>
                  </span>
                </td>
                <td>
                  <input aria-label={`Cliente de ${r.id}`} className="input w-[70px] !px-1.5 !py-1 font-mono text-xs" value={r.cliente_id} onChange={(e) => set(i, { cliente_id: e.target.value })} />
                </td>
                <td className="min-w-[240px]">
                  <textarea aria-label={`Mensaje de ${r.id}`} rows={2} className="input !px-1.5 !py-1 text-xs" value={r.mensaje} onChange={(e) => set(i, { mensaje: e.target.value })} />
                </td>
                <td className="min-w-[110px]">
                  <input
                    aria-label={`Agente esperado de ${r.id}`}
                    className="input !px-1.5 !py-1 font-mono text-xs"
                    value={Array.isArray(r.agente_esperado) ? r.agente_esperado.join(' | ') : r.agente_esperado ?? ''}
                    onChange={(e) => set(i, { agente_esperado: e.target.value.includes('|') ? e.target.value.split('|').map((x) => x.trim()) : e.target.value })}
                  />
                </td>
                <td className="min-w-[160px]">
                  <input aria-label={`Tools de ${r.id}`} className="input !px-1.5 !py-1 font-mono text-xs" value={r.tools_esperadas.join(', ')} onChange={(e) => set(i, { tools_esperadas: list(e.target.value) })} />
                </td>
                <td className="min-w-[240px]">
                  <textarea aria-label={`Respuesta esperada de ${r.id}`} rows={2} className="input !px-1.5 !py-1 text-xs" value={r.respuesta_esperada} onChange={(e) => set(i, { respuesta_esperada: e.target.value })} />
                </td>
                <td className="min-w-[140px]">
                  <input aria-label={`Reglas de ${r.id}`} className="input !px-1.5 !py-1 font-mono text-xs" value={r.reglas_a_verificar.join(', ')} onChange={(e) => set(i, { reglas_a_verificar: list(e.target.value) })} />
                </td>
                <td className="text-center">
                  <input type="checkbox" aria-label={`${r.id} debe pedir confirmación`} className="h-4 w-4 accent-amber" checked={r.debe_pedir_confirmacion} onChange={(e) => set(i, { debe_pedir_confirmacion: e.target.checked })} />
                </td>
                <td>
                  <button type="button" className="btn-icon h-8 w-8" aria-label={`Quitar ${r.id}`} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                    <Trash2 size={14} aria-hidden />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Toast msg={toast?.msg ?? null} kind={toast?.kind} onDone={() => setToast(null)} />
    </section>
  )
}
