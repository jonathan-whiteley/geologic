import { Navigate, useParams } from 'react-router-dom'

/** v1 and v2 bookmarks: /monitor/prompts/:id → the prompt detail, anything else under /monitor → Measure. */
export function MonitorRedirect() {
  const { '*': rest = '' } = useParams()
  const m = rest.match(/^prompts\/([^/]+)/)
  return <Navigate to={m ? `/measure/prompts/${m[1]}` : '/measure'} replace />
}

/** /measure/questions/:id → /measure/prompts/:id */
export function QuestionRedirect() {
  const { promptId = '' } = useParams()
  return <Navigate to={`/measure/prompts/${promptId}`} replace />
}
