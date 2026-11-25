import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { MemoryViewer } from '../components/memory/MemoryViewer'
import { usePlatformStore } from '../store/usePlatformStore'

export default function MemoryPage() {
  const clienteGlobal = usePlatformStore((s) => s.clienteId)
  const [cliente, setCliente] = useState(clienteGlobal)
  const { data: clientes = [] } = useQuery({ queryKey: ['clientes'], queryFn: api.clientes })
  return (
    <div className="space-y-3 p-3">
      <section className="card flex flex-wrap items-end gap-3 p-4">
        <div className="mr-auto">
          <h2 className="text-base font-semibold">Memoria</h2>
          <p className="muted text-sm">Corto plazo (historial), estructurada (perfil) y episódica. Lee antes de razonar, escribe después de responder.</p>
        </div>
        <div className="min-w-[220px]">
          <label htmlFor="mem-cli" className="label">
            Cliente
          </label>
          <select id="mem-cli" className="input" value={cliente} onChange={(e) => setCliente(e.target.value)}>
            {clientes.map((c) => (
              <option key={c.cliente_id} value={c.cliente_id}>
                {c.cliente_id} · {c.nombre}
              </option>
            ))}
          </select>
        </div>
      </section>
      <MemoryViewer key={cliente} clienteId={cliente} />
    </div>
  )
}
