import type * as T from './types'

async function req<R>(path: string, init?: RequestInit): Promise<R> {
  const r = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw Object.assign(new Error(body.detail ?? `Request failed (${r.status})`), { status: r.status })
  }
  return r.json()
}

export const api = {
  modelSummary: () => req<T.ModelSummary>('/model/summary'),
  prompt: (id: string) => req<T.PromptDetail>(`/model/prompts/${id}`),
  promptSearch: (q: string) => req<{ prompt_id: string }>(`/prompts/search?q=${encodeURIComponent(q)}`),
  promptExplorer: (id: string) => req<T.PromptExplorer>(`/prompts/${id}`),
  trackPrompt: (id: string) => req<{ tracked: boolean }>(`/prompts/${id}/track`, { method: 'POST' }),
  signals: () => req<T.SignalsResp>('/signals?limit=50'),
  opportunities: () => req<T.Opportunity[]>('/opportunities'),
  suggestions: () => req<T.Suggestion[]>('/suggestions'),
  approve: (id: string) => req<{ run_id: number }>(`/suggestions/${id}/approve`, { method: 'POST' }),
  reject: (id: string) => req<{ state: string }>(`/suggestions/${id}/reject`, { method: 'POST' }),
  status: (id: string) => req<T.PublishStatus>(`/suggestions/${id}/status`),
  impact: () => req<T.Impact>('/impact'),
  ask: (question: string) => req<{ answer: string }>('/ask', { method: 'POST', body: JSON.stringify({ question }) }),
  reset: () => req<{ run_id: number }>('/demo/reset', { method: 'POST' }),
  resetStatus: (runId: number) => req<{ run_id: number; life_cycle_state: string | null; result_state: string | null }>(`/demo/reset/${runId}`),
  inject: (truth: string) => req<{ run_id: number }>(`/demo/inject/${truth}`, { method: 'POST' }),
}
