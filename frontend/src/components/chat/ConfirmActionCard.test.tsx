import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmActionCard } from './ConfirmActionCard'

describe('ConfirmActionCard', () => {
  it('muestra la acción y confirma', () => {
    const onConfirm = vi.fn()
    render(<ConfirmActionCard confirm={{ run_id: 'r1', tool: 'solicitar_reembolso', args: { cobro_id: 'c2' }, descripcion: 'Solicitar el reembolso del cobro c2 ($23.490)' }} onConfirm={onConfirm} />)
    expect(screen.getByText(/reembolso del cobro c2/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Confirmar/ }))
    expect(onConfirm).toHaveBeenCalledWith(true)
  })
  it('muestra el resultado', () => {
    render(<ConfirmActionCard confirm={{ run_id: 'r1', tool: 't', args: {}, descripcion: 'd', resultado: 'cancelada' }} onConfirm={() => {}} />)
    expect(screen.getByText(/no se ejecutó/)).toBeInTheDocument()
  })
})
