import { Send } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { ChatMessage } from '../../types'
import { EmptyState, Spinner } from '../common'
import { MessageBubble } from './MessageBubble'

export const SUGERENCIAS = ['me cobraron dos veces el pedido 8812', 'lo de siempre para el viernes', 'quiero 3 botellas de vino y pagar con la línea de crédito']

interface Props {
  messages: ChatMessage[]
  busy: boolean
  onSend: (m: string) => void
  onConfirm: (run_id: string, ok: boolean, msgId: string) => void | Promise<void>
  header?: ReactNode
  sugerencias?: string[]
  inputRef?: React.RefObject<HTMLTextAreaElement>
}

export function ChatPanel({ messages, busy, onSend, onConfirm, header, sugerencias = SUGERENCIAS, inputRef }: Props) {
  const [text, setText] = useState('')
  const listRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])
  const submit = (m = text) => {
    const v = m.trim()
    if (!v || busy) return
    onSend(v)
    setText('')
  }
  return (
    <section className="card flex h-full min-h-0 flex-col" aria-label="Chat">
      {header}
      <div ref={listRef} className="scroll-thin min-h-0 flex-1 space-y-3 overflow-auto px-3 py-3" aria-live="polite">
        {messages.length === 0 ? (
          <EmptyState title="Conversa con los agentes">
            Prueba una consulta. En el flow podrás seguir qué agente responde y qué herramientas usa.
          </EmptyState>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} m={m} onConfirm={onConfirm} />)
        )}
      </div>
      <div className="border-t border-line p-3 dark:border-night-line">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {sugerencias.map((s) => (
            <button
              key={s}
              type="button"
              disabled={busy}
              onClick={() => submit(s)}
              className="rounded-full border border-line bg-panel px-2.5 py-1 text-left text-xs text-ink transition-colors hover:border-teal-dk hover:bg-white disabled:opacity-50 dark:border-night-line dark:bg-night dark:text-night-text dark:hover:border-teal"
            >
              {s}
            </button>
          ))}
        </div>
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <label htmlFor="chat-input" className="sr-only">
            Mensaje
          </label>
          <textarea
            id="chat-input"
            name="mensaje"
            ref={inputRef}
            rows={2}
            maxLength={2000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                submit()
              }
            }}
            placeholder="Escribe un mensaje…"
            className="input min-h-[44px] resize-none"
          />
          <button type="submit" className="btn-primary h-[44px] px-4" disabled={busy || !text.trim()} aria-label="Enviar mensaje">
            {busy ? <Spinner /> : <Send size={16} aria-hidden />}
            <span className="hidden sm:inline">Enviar</span>
          </button>
        </form>
      </div>
    </section>
  )
}
