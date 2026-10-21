import type * as T from './types'

async function req<R>(path: string, init?: RequestInit): Promise<R> {
  const r = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw Object.assign(new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${r.status})`), { status: r.status })
  }
  return r.json()
}

export const api = {
  // Measure
  modelSummary: () => req<T.ModelSummary>('/model/summary'),
  prompts: () => req<T.PromptRow[]>('/prompts'),
  prompt: (id: string) => req<T.PromptDetail>(`/prompts/${encodeURIComponent(id)}`),
  promptSuggestions: () => req<T.PromptSuggestion[]>('/prompt-suggestions'),
  search: (q: string) => req<T.SearchResp>(`/search?q=${encodeURIComponent(q)}`),
  trackPrompt: (text: string, suggestionId?: string) =>
    req<T.TrackResp>('/prompts/track', { method: 'POST', body: JSON.stringify({ text, suggestion_id: suggestionId ?? null }) }),
  // Fix
  issues: (params?: { type?: string; cluster?: string }) => {
    const qs = new URLSearchParams()
    if (params?.type) qs.set('type', params.type)
    if (params?.cluster) qs.set('cluster', params.cluster)
    const q = qs.toString()
    return req<T.IssueRow[]>(`/issues${q ? `?${q}` : ''}`)
  },
  issue: (id: string) => req<T.IssueDetailT>(`/issues/${encodeURIComponent(id)}`),
  fixSummary: () => req<T.FixSummary>('/fix/summary'),
  quarantine: () => req<T.Quarantine>('/quarantine'),
  fixes: () => req<T.Fix[]>('/fixes'),
  approve: (id: string) => req<{ started: boolean }>(`/fixes/${encodeURIComponent(id)}/approve`, { method: 'POST' }),
  approveT0: () => req<{ run_id: number; fix_ids: string[] }>('/fixes/approve-t0', { method: 'POST' }),
  reject: (id: string) => req<{ state: string }>(`/fixes/${encodeURIComponent(id)}/reject`, { method: 'POST' }),
  edit: (id: string, patchText: string) =>
    req<T.Fix>(`/fixes/${encodeURIComponent(id)}/edit`, { method: 'POST', body: JSON.stringify({ patch_text: patchText }) }),
  fixStatus: (id: string) => req<T.FixStatus>(`/fixes/${encodeURIComponent(id)}/status`),
  // v2 Impact call, replaced in Task 13
  impact: () => req<T.Impact>('/impact'),
  // Demo controls
  reset: () => req<{ run_id: number }>('/demo/reset', { method: 'POST' }),
  resetStatus: (runId: number) => req<{ run_id: number; life_cycle_state: string | null; result_state: string | null }>(`/demo/reset/${runId}`),
  inject: (truth: string) => req<{ run_id: number }>(`/demo/inject/${truth}`, { method: 'POST' }),
}

export function genieAsk(question: string, conversationId?: string, context?: string) {
  return req<{ conversation_id: string; message_id: string }>('/genie/ask', {
    method: 'POST',
    body: JSON.stringify({ question, conversation_id: conversationId ?? null, context: context ?? null }),
  })
}

export function genieMessage(c: string, m: string) {
  return req<T.GenieMessage>(`/genie/message/${encodeURIComponent(c)}/${encodeURIComponent(m)}`)
}
