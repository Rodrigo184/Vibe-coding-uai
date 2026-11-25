import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Bot, Brain, CheckCircle2, CircleAlert, Database, FileInput, Gavel, ListChecks, Network, Send, ShieldCheck, User, Wrench } from 'lucide-react'
import { memo } from 'react'
import { KIND_COLOR } from '../../lib/flowLayout'
import type { NodeKind } from '../../types'
import { COLOR_CLASSES } from '../common'

export interface AgentNodeData extends Record<string, unknown> {
  label: string
  sub?: string
  kind: NodeKind
  status?: 'idle' | 'active' | 'done' | 'error'
  badge?: string | null
  flash?: string | null
  onSelect?: () => void
}

const ICONS: Record<NodeKind, typeof Bot> = {
  input: FileInput, output: Send, llm: Bot, tool: Wrench, memory: Database, rule: ShieldCheck, judge: Gavel, human: User, plan: ListChecks, supervisor: Network,
}

function AgentNodeImpl({ data }: NodeProps) {
  const d = data as AgentNodeData
  const color = KIND_COLOR[d.kind] ?? 'muted'
  const c = COLOR_CLASSES[color]
  const Icon = d.kind === 'memory' && d.label.toLowerCase().includes('extract') ? Brain : ICONS[d.kind] ?? Bot
  const st = d.status ?? 'idle'
  const ring =
    st === 'active'
      ? 'border-red ring-2 ring-red/40 animate-pulsering'
      : st === 'error'
        ? 'border-red'
        : st === 'done'
          ? 'border-green'
          : 'border-line dark:border-night-line'
  return (
    <div
      className={`relative w-[188px] rounded-xl border-2 bg-white px-3 py-2 shadow-card transition-colors dark:bg-night-card ${ring} ${d.onSelect ? 'hover:border-teal-dk dark:hover:border-teal' : ''}`}
    >
      {Object.values(Position).map((position) => (
        <span key={position} aria-hidden>
          <Handle id={position} type="target" position={position} className="!h-1.5 !w-1.5 !border-0 !bg-transparent" />
          <Handle id={position} type="source" position={position} className="!h-1.5 !w-1.5 !border-0 !bg-transparent" />
        </span>
      ))}
      {d.onSelect && (
        <button type="button" aria-label={`Inspeccionar ${d.label}`} onClick={d.onSelect} className="nodrag nopan absolute inset-0 z-10 cursor-pointer rounded-xl" />
      )}
      <div className="flex items-center gap-2">
        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${c.soft} ${c.text}`}>
          <Icon size={15} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-semibold leading-tight">{d.label}</div>
          {d.sub && <div className="muted truncate text-[11px] leading-tight">{d.sub}</div>}
        </div>
        {st === 'done' && <CheckCircle2 size={15} className="shrink-0 text-green-tx dark:text-green" aria-label="completado" />}
        {st === 'error' && <CircleAlert size={15} className="shrink-0 text-red-tx dark:text-red" aria-label="error" />}
      </div>
      {d.badge && (
        <div className="mt-1.5 truncate rounded-md bg-teal/15 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-teal-tx dark:text-teal">{d.badge}</div>
      )}
      {d.flash && (
        <div key={d.flash} className="mt-1.5 animate-blink truncate rounded-md bg-amber/20 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-amber-tx dark:text-amber">
          {d.flash}
        </div>
      )}
    </div>
  )
}

export const AgentNode = memo(AgentNodeImpl)
