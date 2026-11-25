import { useCallback, useState } from 'react'
import { chatSSE, confirmSSE } from '../../api/client'
import { usePlatformStore } from '../../store/usePlatformStore'
import type { ChatMessage, FinalContent, TraceEvent } from '../../types'

const uid = () => Math.random().toString(36).slice(2, 10)

interface Sink {
  addMessage: (m: ChatMessage) => void
  patchMessage: (id: string, p: Partial<ChatMessage>) => void
  pushEvent: (e: TraceEvent) => void
  setBusy: (b: boolean) => void
  resetFlow?: () => void
}

function handler(sink: Sink, msgId: string) {
  return (e: TraceEvent) => {
    sink.pushEvent(e)
    if (e.tipo === 'confirm_required') {
      sink.patchMessage(msgId, { confirm: { run_id: e.run_id, tool: e.contenido.tool, args: e.contenido.args, descripcion: e.contenido.descripcion } })
    }
    if (e.tipo === 'final') {
      const f = e.contenido as FinalContent
      sink.patchMessage(msgId, { texto: f.respuesta ?? '(sin respuesta)', final: f, pending: false })
    }
  }
}

async function send(sink: Sink, body: Parameters<typeof chatSSE>[0]) {
  sink.resetFlow?.()
  sink.addMessage({ id: uid(), rol: 'user', texto: body.mensaje })
  const msgId = uid()
  sink.addMessage({ id: msgId, rol: 'assistant', texto: '', pending: true })
  sink.setBusy(true)
  try {
    await chatSSE(body, handler(sink, msgId))
  } catch (err) {
    sink.patchMessage(msgId, { texto: `No se pudo conectar con el backend: ${(err as Error).message}`, pending: false })
  } finally {
    sink.setBusy(false)
  }
}

type Confirmation = NonNullable<ChatMessage['confirm']>

async function confirm(sink: Sink, run_id: string, ok: boolean, card: Confirmation | undefined, patchCard: (result: NonNullable<Confirmation['resultado']>) => void) {
  sink.resetFlow?.()
  const msgId = uid()
  sink.addMessage({ id: msgId, rol: 'assistant', texto: '', pending: true })
  sink.setBusy(true)
  try {
    const handleEvent = handler(sink, msgId)
    await confirmSSE(run_id, ok, (event) => {
      handleEvent(event)
      if (event.tipo !== 'final') return
      const expected = ok ? 'ejecutada' : 'cancelada'
      const matches = (event.contenido as FinalContent).acciones.some((action) =>
        action.estado === expected && action.tool === card?.tool && JSON.stringify(action.args) === JSON.stringify(card?.args),
      )
      patchCard(matches ? (ok ? 'confirmada' : 'cancelada') : 'fallida')
    })
  } catch (err) {
    sink.patchMessage(msgId, { texto: `Error al confirmar: ${(err as Error).message}`, pending: false })
  } finally {
    sink.setBusy(false)
  }
}

/** Chat conectado al store global (Playground). */
export function useGlobalChat() {
  const s = usePlatformStore()
  const sink: Sink = { addMessage: s.addMessage, patchMessage: s.patchMessage, pushEvent: s.pushEvent, setBusy: s.setBusy, resetFlow: s.resetFlow }
  return {
    messages: s.messages,
    events: s.events,
    busy: s.busy,
    send: (mensaje: string) => send(sink, { cliente_id: s.clienteId, sesion_id: s.sesionId, mensaje }),
    confirm: (run_id: string, ok: boolean, cardId: string) => {
      const card = usePlatformStore.getState().messages.find((x) => x.id === cardId)?.confirm
      return confirm(sink, run_id, ok, card, (resultado) => {
        if (card) s.patchMessage(cardId, { confirm: { ...card, resultado } })
      })
    },
  }
}

/** Chat local (pestaña "Probar" del editor): corre solo un agente. */
export function useLocalChat(forzarAgente: string, clienteId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [sesion, setSesion] = useState(() => `probar-${uid()}`)
  const sink: Sink = {
    addMessage: (m) => setMessages((xs) => [...xs, m]),
    patchMessage: (id, p) => setMessages((xs) => xs.map((x) => (x.id === id ? { ...x, ...p } : x))),
    pushEvent: (e) => setEvents((xs) => [...xs, e]),
    setBusy,
  }
  const reset = useCallback(() => {
    setMessages([])
    setEvents([])
    setSesion(`probar-${uid()}`)
  }, [])
  return {
    messages,
    events,
    busy,
    reset,
    send: (mensaje: string) => send(sink, { cliente_id: clienteId, sesion_id: sesion, mensaje, forzar_agente: forzarAgente }),
    confirm: (run_id: string, ok: boolean, cardId: string) => {
      const card = messages.find((x) => x.id === cardId)?.confirm
      return confirm(sink, run_id, ok, card, (resultado) => {
        if (card) sink.patchMessage(cardId, { confirm: { ...card, resultado } })
      })
    },
  }
}
