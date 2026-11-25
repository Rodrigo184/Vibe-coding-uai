import { lazy, Suspense, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { Spinner } from './components/common'
import { Header } from './components/layout/Header'
import { usePlatformStore } from './store/usePlatformStore'

const PlaygroundPage = lazy(() => import('./pages/PlaygroundPage'))
const AgentsPage = lazy(() => import('./pages/AgentsPage'))
const ToolsPage = lazy(() => import('./pages/ToolsPage'))
const RunsPage = lazy(() => import('./pages/RunsPage'))
const MemoryPage = lazy(() => import('./pages/MemoryPage'))
const EvalsPage = lazy(() => import('./pages/EvalsPage'))
const PromptsPage = lazy(() => import('./pages/PromptsPage'))

export default function App() {
  const setHelp = usePlatformStore((s) => s.setHelp)
  const location = useLocation()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable || t.closest('.cm-editor'))
      if (!typing && e.key === '?') {
        e.preventDefault()
        setHelp(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setHelp])

  useEffect(() => {
    document.getElementById('main')?.focus({ preventScroll: true })
  }, [location.pathname])

  return (
    <div className="flex min-h-full flex-col lg:h-full">
      <Header />
      <main id="main" tabIndex={-1} className="flex min-h-0 flex-1 flex-col outline-none lg:overflow-auto">
        <Suspense
          fallback={
            <div className="muted flex flex-1 items-center justify-center gap-2 p-10">
              <Spinner /> Cargando…
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<PlaygroundPage />} />
            <Route path="/agentes" element={<AgentsPage />} />
            <Route path="/agentes/:id" element={<AgentsPage />} />
            <Route path="/tools" element={<ToolsPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/runs/:id" element={<RunsPage />} />
            <Route path="/memoria" element={<MemoryPage />} />
            <Route path="/evaluacion" element={<EvalsPage />} />
            <Route path="/prompts" element={<PromptsPage />} />
            <Route path="*" element={<PlaygroundPage />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
