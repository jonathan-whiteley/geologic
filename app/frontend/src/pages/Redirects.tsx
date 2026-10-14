import { Navigate, useParams, useSearchParams } from 'react-router-dom'

export function MonitorRedirect() {
  const { '*': rest = '' } = useParams()
  const m = rest.match(/^prompts\/([^/]+)/)
  if (m) return <Navigate to={`/measure/questions/${m[1]}`} replace />
  if (rest.startsWith('prompts')) return <Navigate to="/measure/questions" replace />
  return <Navigate to="/measure/answers" replace />
}

export function ActRedirect() {
  const [params] = useSearchParams()
  const opp = params.get('opp')
  return <Navigate to={opp ? `/fix?opp=${encodeURIComponent(opp)}` : '/fix'} replace />
}
