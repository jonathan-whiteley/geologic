import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AppLayout from './layouts/AppLayout'
import MonitorLayout from './layouts/MonitorLayout'
import AnswersPage from './pages/AnswersPage'
import SignalsPage from './pages/SignalsPage'
import PromptsPage from './pages/PromptsPage'
import PrioritizePage from './pages/PrioritizePage'
import ActPage from './pages/ActPage'
import ImpactPage from './pages/ImpactPage'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1 } } })

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/monitor/answers" replace />} />
            <Route path="monitor" element={<MonitorLayout />}>
              <Route index element={<Navigate to="answers" replace />} />
              <Route path="answers" element={<AnswersPage />} />
              <Route path="signals" element={<SignalsPage />} />
              <Route path="prompts" element={<PromptsPage />} />
              <Route path="prompts/:promptId" element={<PromptsPage />} />
            </Route>
            <Route path="prioritize" element={<PrioritizePage />} />
            <Route path="act" element={<ActPage />} />
            <Route path="impact" element={<ImpactPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
