import { Bot, User } from 'lucide-react'
import type { ChatMessage } from '../../types'
import { Badge, ESTADO_COLOR, Spinner, VEREDICTO_COLOR, ms, usd } from '../common'
import { ConfirmActionCard } from './ConfirmActionCard'

export function MessageBubble({ m, onConfirm }: { m: ChatMessage; onConfirm: (run_id: string, ok: boolean, msgId: string) => void | Promise<void> }) {
  const isUser = m.rol === 'user'
  const f = m.final
  return (
    <div className={`flex gap-2 ${isUser ? 'flex-row-reverse' : ''}`}>
      <span
        aria-hidden
        className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${isUser ? 'bg-ink text-white dark:bg-night-text dark:text-ink' : 'bg-teal/15 text-teal-tx dark:text-teal'}`}
      >
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </span>
      <div className={`flex max-w-[85%] flex-col gap-1.5 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-[13.5px] leading-relaxed ${
            isUser ? 'rounded-tr-sm bg-ink text-white dark:bg-[#2a3747]' : 'rounded-tl-sm border border-line bg-white dark:border-night-line dark:bg-night-card'
          }`}
        >
          {m.pending ? (
            <span className="muted flex items-center gap-2">
              <Spinner /> pensando…
            </span>
          ) : (
            m.texto
          )}
        </div>
        {m.confirm && <ConfirmActionCard confirm={m.confirm} onConfirm={(ok) => onConfirm(m.confirm!.run_id, ok, m.id)} />}
        {f && !m.pending && (
          <div className="flex flex-wrap items-center gap-1 text-[11px]">
            {f.agente && <Badge color="teal">{f.agente}</Badge>}
            {f.veredicto && <Badge color={VEREDICTO_COLOR[f.veredicto] ?? 'muted'}>evaluador: {f.veredicto}</Badge>}
            {f.estado !== 'ok' && <Badge color={ESTADO_COLOR[f.estado] ?? 'muted'}>{f.estado.replace('_', ' ')}</Badge>}
            <span className="muted tabular">
              {usd(f.costo_usd)} · {ms(f.latencia_ms)} · {f.llamadas_llm} LLM
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
