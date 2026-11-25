import { Background, Controls, MarkerType, ReactFlow, ReactFlowProvider, useNodesInitialized, useReactFlow, useStore, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEffect, useMemo } from 'react'
import { usePlatformStore } from '../../store/usePlatformStore'
import type { FlowEdgeDef, FlowNodeDef } from '../../types'
import { AgentNode, type AgentNodeData } from './AgentNode'
import { StepEdge } from './StepEdge'

const nodeTypes = { agent: AgentNode }
const edgeTypes = { step: StepEdge }

interface Props {
  nodes: FlowNodeDef[]
  edges: FlowEdgeDef[]
  status?: Record<string, 'idle' | 'active' | 'done' | 'error'>
  visited?: string[]
  badges?: Record<string, string | null>
  flash?: Record<string, string | null>
  onNodeClick?: (id: string) => void
  clickable?: (id: string) => boolean
  height?: number | string
  fitKey?: string
}

function Inner({ nodes, edges, status = {}, visited = [], badges = {}, flash = {}, onNodeClick, clickable, fitKey }: Props) {
  const dark = usePlatformStore((s) => s.dark)
  const rf = useReactFlow()
  const initialized = useNodesInitialized()
  const width = useStore((s) => s.width)
  const height = useStore((s) => s.height)
  const visitedSet = useMemo(() => new Set(visited), [visited])

  const rfNodes: Node[] = useMemo(
    () =>
      nodes.map((n) => ({
        id: n.id,
        type: 'agent',
        position: { x: n.x, y: n.y },
        draggable: false,
        data: { label: n.label, sub: n.sub, kind: n.kind, status: status[n.id] ?? 'idle', badge: badges[n.id] ?? null, flash: flash[n.id] ?? null, onSelect: onNodeClick && (clickable?.(n.id) ?? true) ? () => onNodeClick(n.id) : undefined } satisfies AgentNodeData,
      })),
    [nodes, status, badges, flash, clickable, onNodeClick],
  )
  const rfEdges: Edge[] = useMemo(
    () =>
      edges.map((e) => {
        const v = visitedSet.has(`${e.source}->${e.target}`)
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle ?? 'right',
          targetHandle: e.targetHandle ?? 'left',
          type: 'step',
          label: e.label,
          animated: v,
          data: { kind: e.kind, visited: v },
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: v ? '#E63946' : '#9AA8BB' },
          zIndex: v ? 5 : 0,
        }
      }),
    [edges, visitedSet],
  )

  useEffect(() => {
    if (initialized && width > 0 && height > 0) void rf.fitView({ padding: 0.12, duration: 0 })
  }, [fitKey, height, initialized, rf, width])

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      minZoom={0.2}
      maxZoom={1.6}
      nodesConnectable={false}
      elementsSelectable={false}
      nodesFocusable={false}
      edgesFocusable={false}
      zoomOnScroll={false}
      preventScrolling={false}
      colorMode={dark ? 'dark' : 'light'}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={20} size={1} color={dark ? '#273244' : '#DCE3EC'} />
      <Controls showInteractive={false} position="bottom-right" aria-label="Controles del diagrama" />
    </ReactFlow>
  )
}

export function FlowCanvas(props: Props) {
  return (
    <div style={{ height: props.height ?? '100%' }} className="w-full" role="group" aria-label="Diagrama del flujo de agentes">
      <ReactFlowProvider>
        <Inner {...props} />
      </ReactFlowProvider>
    </div>
  )
}
