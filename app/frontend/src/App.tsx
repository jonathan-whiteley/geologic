import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AppLayout from './layouts/AppLayout'
import MeasureLayout from './layouts/MeasureLayout'
import OverviewPage from './pages/OverviewPage'
import PromptBankPage from './pages/PromptBankPage'
import PromptDetailPage from './pages/PromptDetailPage'
import FixPage from './pages/FixPage'
import ImpactPage from './pages/ImpactPage'
import ArchitecturePage from './pages/ArchitecturePage'
import { MonitorRedirect, QuestionRedirect } from './pages/Redirects'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1 } } })

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/measure" replace />} />
            <Route path="measure" element={<MeasureLayout />}>
              <Route index element={<OverviewPage />} />
              <Route path="prompts" element={<PromptBankPage />} />
              <Route path="prompts/:promptId" element={<PromptDetailPage />} />
            </Route>
            <Route path="fix" element={<FixPage />} />
            <Route path="impact" element={<ImpactPage />} />
            <Route path="architecture" element={<ArchitecturePage />} />
            {/* v1 and v2 bookmarks */}
            <Route path="measure/answers" element={<Navigate to="/measure" replace />} />
            <Route path="measure/questions" element={<Navigate to="/measure/prompts" replace />} />
            <Route path="measure/questions/:promptId" element={<QuestionRedirect />} />
            <Route path="monitor/*" element={<MonitorRedirect />} />
            <Route path="prioritize" element={<Navigate to="/fix" replace />} />
            <Route path="act" element={<Navigate to="/fix" replace />} />
            <Route path="prove" element={<Navigate to="/impact" replace />} />
            <Route path="signals" element={<Navigate to="/fix" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
