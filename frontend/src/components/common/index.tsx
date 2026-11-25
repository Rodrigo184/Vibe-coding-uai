import { Check, Copy, Inbox, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'

export const COLOR_CLASSES: Record<string, { dot: string; soft: string; text: string; border: string }> = {
  ink: { dot: 'bg-ink dark:bg-night-text', soft: 'bg-ink/10 dark:bg-white/10', text: 'text-ink dark:text-night-text', border: 'border-ink dark:border-night-text' },
  teal: { dot: 'bg-teal', soft: 'bg-teal/15', text: 'text-teal-tx dark:text-teal', border: 'border-teal' },
  amber: { dot: 'bg-amber', soft: 'bg-amber/15', text: 'text-amber-tx dark:text-amber', border: 'border-amber' },
  violet: { dot: 'bg-violet', soft: 'bg-violet/15', text: 'text-violet-tx dark:text-violet', border: 'border-violet' },
  red: { dot: 'bg-red', soft: 'bg-red/15', text: 'text-red-tx dark:text-red', border: 'border-red' },
  green: { dot: 'bg-green', soft: 'bg-green/15', text: 'text-green-tx dark:text-green', border: 'border-green' },
  muted: { dot: 'bg-muted', soft: 'bg-muted/15', text: 'text-muted dark:text-night-muted', border: 'border-muted' },
}

export function Badge({ color = 'muted', children, title }: { color?: string; children: ReactNode; title?: string }) {
  const c = COLOR_CLASSES[color] ?? COLOR_CLASSES.muted
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${c.soft} ${c.text}`}>
      {children}
    </span>
  )
}

export function Dot({ color = 'muted', className = '' }: { color?: string; className?: string }) {
  return <span aria-hidden className={`inline-block h-2 w-2 shrink-0 rounded-full ${(COLOR_CLASSES[color] ?? COLOR_CLASSES.muted).dot} ${className}`} />
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-line bg-white px-1.5 py-0.5 font-mono text-[11px] text-muted shadow-sm dark:border-night-line dark:bg-night-card dark:text-night-muted">
      {children}
    </kbd>
  )
}

export function CopyButton({ text, label = 'Copiar', className = '' }: { text: string | (() => string); label?: string; className?: string }) {
  const [ok, setOk] = useState(false)
  return (
    <button
      type="button"
      className={`btn-ghost ${className}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(typeof text === 'function' ? text() : text)
          setOk(true)
          setTimeout(() => setOk(false), 1500)
        } catch {
          /* portapapeles bloqueado */
        }
      }}
    >
      {ok ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
      <span>{ok ? 'Copiado' : label}</span>
    </button>
  )
}

export function JsonView({ value, collapsed = false, className = '' }: { value: unknown; collapsed?: boolean; className?: string }) {
  const [open, setOpen] = useState(!collapsed)
  const txt = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  if (!open)
    return (
      <button type="button" className="font-mono text-xs text-teal-tx underline-offset-2 hover:underline dark:text-teal" onClick={() => setOpen(true)}>
        {'{…}'} ver JSON ({txt.length} car.)
      </button>
    )
  return (
    <pre className={`scroll-thin max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-panel p-2 font-mono text-[11.5px] leading-relaxed dark:bg-night ${className}`}>
      {txt}
    </pre>
  )
}

export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="rounded-full bg-panel p-3 text-muted dark:bg-night dark:text-night-muted">{icon ?? <Inbox size={20} aria-hidden />}</div>
      <p className="font-semibold">{title}</p>
      {children && <div className="muted max-w-md text-sm">{children}</div>}
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer, wide = false }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current
    if (!open || !dialog) return
    dialog.showModal()
    return () => dialog.close()
  }, [open])
  if (!open) return null
  return (
    <dialog ref={ref} aria-label={title} onCancel={(e) => { e.preventDefault(); onClose() }} onClick={(e) => { if (e.target === e.currentTarget) onClose() }} className={`card fixed inset-0 m-auto max-h-[90svh] w-[calc(100%-2rem)] overflow-hidden overscroll-contain p-0 ${wide ? 'max-w-4xl' : 'max-w-lg'} text-ink shadow-pop backdrop:bg-ink/50 dark:text-night-text`}>
      <div className="flex max-h-[90svh] flex-col">
        <div className="flex items-center justify-between border-b border-line px-4 py-3 dark:border-night-line">
          <h2 className="text-base font-semibold">{title}</h2>
          <button type="button" className="btn-icon" aria-label="Cerrar" onClick={onClose}>
            <X size={18} aria-hidden />
          </button>
        </div>
        <div className="scroll-thin overflow-auto px-4 py-3">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-4 py-3 dark:border-night-line">{footer}</div>}
      </div>
    </dialog>
  )
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <span aria-hidden className="inline-block animate-spin rounded-full border-2 border-current border-t-transparent" style={{ width: size, height: size }} />
}

export function Toast({ msg, kind = 'ok', onDone }: { msg: string | null; kind?: 'ok' | 'error'; onDone: () => void }) {
  useEffect(() => {
    if (!msg) return
    const t = setTimeout(onDone, 4000)
    return () => clearTimeout(t)
  }, [msg, onDone])
  if (!msg) return null
  return (
    <div role="status" aria-live="polite" className={`fixed bottom-4 right-4 z-50 max-w-sm rounded-lg px-4 py-3 text-sm font-medium text-white shadow-pop ${kind === 'ok' ? 'bg-green-tx' : 'bg-red-tx'}`}>
      {msg}
    </div>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-line dark:border-night-line">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          type="button"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
            value === t.id ? 'border-teal-dk text-ink dark:border-teal dark:text-night-text' : 'border-transparent text-muted hover:text-ink dark:text-night-muted dark:hover:text-night-text'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

export const clp = (n: number | null | undefined) => (n == null ? '—' : '$' + Math.round(n).toLocaleString('es-CL'))
export const usd = (n: number | null | undefined) => (n == null ? '—' : `$${n < 0.01 ? n.toFixed(4) : n.toFixed(3)}`)
export const ms = (n: number | null | undefined) => (n == null ? '—' : n >= 1000 ? `${(n / 1000).toFixed(1)} s` : `${n} ms`)
export const pct = (n: number | null | undefined) => (n == null ? '—' : `${Math.round(n * 100)} %`)
export const fecha = (iso: string) => {
  try {
    return new Date(iso).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'medium' })
  } catch {
    return iso
  }
}

export const ESTADO_COLOR: Record<string, string> = { ok: 'green', pendiente_confirmacion: 'amber', humano: 'violet', error: 'red', limite: 'red' }
export const VEREDICTO_COLOR: Record<string, string> = { publicar: 'green', regenerar: 'amber', humano: 'violet' }
export const TIPO_COLOR: Record<string, string> = {
  supervisor: 'ink', router: 'ink', especialista: 'teal', hibrido: 'amber', planner: 'violet', memoria: 'violet', evaluador: 'red',
}
