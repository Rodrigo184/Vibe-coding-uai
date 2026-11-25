import { useParams } from 'react-router-dom'
import { RunDetail } from '../components/runs/RunDetail'
import { RunsTable } from '../components/runs/RunsTable'

export default function RunsPage() {
  const { id } = useParams()
  return <div className="flex min-h-0 flex-1 flex-col p-3">{id ? <RunDetail key={id} runId={id} /> : <RunsTable />}</div>
}
