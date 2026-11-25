import { Bot } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { AgentEditor } from '../components/agents/AgentEditor'
import { AgentList } from '../components/agents/AgentList'
import { EmptyState } from '../components/common'

export default function AgentsPage() {
  const { id } = useParams()
  return (
    <div className="grid min-h-0 flex-1 gap-3 p-3 lg:grid-cols-[300px_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)]">
      <div className="max-h-[360px] min-h-0 lg:max-h-none">
        <AgentList />
      </div>
      {id ? (
        <AgentEditor key={id} agentId={id} />
      ) : (
        <div className="card">
          <EmptyState title="Los agentes son datos, no código" icon={<Bot size={20} aria-hidden />}>
            Elige un agente para editar su prompt, variables, tools y límites, o crea uno nuevo. Al guardar, la versión sube y el próximo turno ya la usa, sin reiniciar el
            backend.
          </EmptyState>
        </div>
      )}
    </div>
  )
}
