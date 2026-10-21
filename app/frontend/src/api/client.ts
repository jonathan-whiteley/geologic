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
  // Fix nav badge (typed fully in Task 12)
  fixes: () => req<{ fix_id: string; state: string }[]>('/fixes'),
  // v2 Fix and Impact calls, replaced in Tasks 12 and 13
  evidence: (id: string) => req<T.Evidence>(`/opportunities/${id}/evidence`),
  opportunities: () => req<T.Opportunity[]>('/opportunities'),
  suggestions: () => req<T.Suggestion[]>('/suggestions'),
  approve: (id: string) => req<{ run_id: number }>(`/suggestions/${id}/approve`, { method: 'POST' }),
  reject: (id: string) => req<{ state: string }>(`/suggestions/${id}/reject`, { method: 'POST' }),
  status: (id: string) => req<T.PublishStatus>(`/suggestions/${id}/status`),
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
