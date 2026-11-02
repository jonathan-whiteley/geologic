import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AppLayout from './layouts/AppLayout'
import MeasureLayout from './layouts/MeasureLayout'
import AnswersPage from './pages/AnswersPage'
import PromptsPage from './pages/PromptsPage'
import FixPage from './pages/FixPage'
import ImpactPage from './pages/ImpactPage'
import ArchitecturePage from './pages/ArchitecturePage'
import { ActRedirect, MonitorRedirect } from './pages/Redirects'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1 } } })

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/measure/answers" replace />} />
            <Route path="measure" element={<MeasureLayout />}>
              <Route index element={<Navigate to="answers" replace />} />
              <Route path="answers" element={<AnswersPage />} />
              <Route path="questions" element={<PromptsPage />} />
              <Route path="questions/:promptId" element={<PromptsPage />} />
            </Route>
            <Route path="fix" element={<FixPage />} />
            <Route path="impact" element={<ImpactPage />} />
            <Route path="architecture" element={<ArchitecturePage />} />
            {/* v1 bookmarks */}
            <Route path="monitor/*" element={<MonitorRedirect />} />
            <Route path="prioritize" element={<Navigate to="/fix" replace />} />
            <Route path="act" element={<ActRedirect />} />
            <Route path="prove" element={<Navigate to="/impact" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
