import { CheckCircle2, ShieldAlert, XCircle } from 'lucide-react'
import { useState } from 'react'
import type { ChatMessage } from '../../types'
import { Spinner } from '../common'

export function ConfirmActionCard({ confirm, onConfirm }: { confirm: NonNullable<ChatMessage['confirm']>; onConfirm: (ok: boolean) => void | Promise<void> }) {
  const [sending, setSending] = useState<null | boolean>(null)
  const done = confirm.resultado
  const submit = async (approved: boolean) => {
    setSending(approved)
    try {
      await onConfirm(approved)
    } finally {
      setSending(null)
    }
  }
  return (
    <div className={`w-full rounded-xl border-2 p-3 ${done ? 'border-line dark:border-night-line' : 'border-amber bg-amber/5'}`} role="group" aria-label="Acción que requiere confirmación">
      <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-tx dark:text-amber">
        <ShieldAlert size={14} aria-hidden /> Acción de escritura · {confirm.tool}
      </div>
      <p className="text-[13.5px] font-medium">{confirm.descripcion}</p>
      <details className="mt-1">
        <summary className="muted cursor-pointer text-xs">argumentos</summary>
        <pre className="mt-1 overflow-auto rounded bg-panel p-2 font-mono text-[11px] dark:bg-night">{JSON.stringify(confirm.args, null, 2)}</pre>
      </details>
      {done ? (
        <p className={`mt-2 flex items-center gap-1.5 text-sm font-semibold ${done === 'confirmada' ? 'text-green-tx dark:text-green' : 'text-red-tx dark:text-red'}`}>
          {done === 'confirmada' ? <CheckCircle2 size={16} aria-hidden /> : <XCircle size={16} aria-hidden />}
          {done === 'confirmada' ? 'Confirmada y ejecutada' : done === 'cancelada' ? 'Cancelada: no se ejecutó' : 'Acción sin resultado confirmado'}
        </p>
      ) : (
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className="btn-primary"
            disabled={sending !== null}
            onClick={() => void submit(true)}
          >
            {sending === true ? <Spinner /> : <CheckCircle2 size={15} aria-hidden />} Confirmar
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={sending !== null}
            onClick={() => void submit(false)}
          >
            {sending === false ? <Spinner /> : <XCircle size={15} aria-hidden />} Cancelar
          </button>
        </div>
      )}
    </div>
  )
}
