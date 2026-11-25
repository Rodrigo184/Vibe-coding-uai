import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from '@xyflow/react'
import { memo } from 'react'

export interface StepEdgeData extends Record<string, unknown> {
  kind?: 'loop' | 'fallback'
  visited?: boolean
}

function StepEdgeImpl({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, label, data, markerEnd }: EdgeProps) {
  const d = (data ?? {}) as StepEdgeData
  const [path, lx, ly] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 12, offset: d.kind === 'loop' ? 28 : 18 })
  const color = d.visited ? '#E63946' : d.kind === 'fallback' ? '#C1242F' : d.kind === 'loop' ? '#7C6CF0' : '#9AA8BB'
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke: color,
          strokeWidth: d.visited ? 2.5 : 1.4,
          strokeDasharray: d.kind === 'fallback' || d.kind === 'loop' ? '5 4' : undefined,
          opacity: d.visited ? 1 : 0.75,
        }}
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{ transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)` }}
            className="nodrag nopan pointer-events-none absolute rounded bg-panel px-1 text-[10.5px] font-medium text-muted dark:bg-night dark:text-night-muted"
          >
            {String(label)}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

export const StepEdge = memo(StepEdgeImpl)
