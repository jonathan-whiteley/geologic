/** Conversation store: one Genie thread, kept across tab changes until New chat. */
import { useCallback, useRef, useState } from 'react'
import { genieAsk, genieMessage } from '../api/client'
import type { GenieMessage } from '../api/types'

export interface Turn {
  id: string
  question: string
  status: 'pending' | 'done' | 'error'
  phase?: string
  startedAt: number
  elapsedMs?: number
  /** When the table arrived (Genie keeps writing its summary after the SQL finishes). */
  tableMs?: number
  result?: GenieMessage
  error?: string
}

interface ThreadState {
  turns: Turn[]
  conversationId?: string
}

const POLL_MS = 1500
const TIMEOUT_MS = 180_000
const TERMINAL = ['COMPLETED', 'FAILED', 'CANCELLED', 'QUERY_RESULT_EXPIRED']
/** Consecutive failed polls to ride out (a network or proxy blip) before failing the turn. */
const MAX_POLL_FAILURES = 2

export function useGenieThread() {
  const [thread, setThread] = useState<ThreadState>({ turns: [] })
  const ref = useRef(thread)
  ref.current = thread

  const update = useCallback((id: string, patch: Partial<Turn>) => {
    setThread(prev => ({ ...prev, turns: prev.turns.map(t => (t.id === id ? { ...t, ...patch } : t)) }))
  }, [])

  const ask = useCallback(
    async (question: string, context?: string) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
      const startedAt = Date.now()
      setThread(prev => ({ ...prev, turns: [...prev.turns, { id, question, status: 'pending', startedAt }] }))
      try {
        const { conversation_id, message_id } = await genieAsk(question, ref.current.conversationId, context)
        // Always keep the returned id: the backend restarts a stale conversation under a new one.
        setThread(prev => ({ ...prev, conversationId: conversation_id }))
        let tableShown = false
        let failures = 0
        while (Date.now() - startedAt < TIMEOUT_MS) {
          await new Promise(r => setTimeout(r, POLL_MS))
          let m: GenieMessage
          try {
            m = await genieMessage(conversation_id, message_id)
            failures = 0
          } catch (e) {
            if (++failures > MAX_POLL_FAILURES) throw e
            continue
          }
          if (m.partial && m.columns.length && !tableShown) {
            tableShown = true
            update(id, { result: m, tableMs: Date.now() - startedAt })
          }
          if (TERMINAL.includes(m.status)) {
            const failed = m.status !== 'COMPLETED'
            update(id, {
              status: failed ? 'error' : 'done',
              result: m,
              elapsedMs: Date.now() - startedAt,
              error: failed ? m.error || `Genie returned ${m.status}` : undefined,
            })
            return
          }
          update(id, { phase: m.status })
        }
        update(id, { status: 'error', error: 'Genie did not answer within 3 minutes', elapsedMs: Date.now() - startedAt })
      } catch (e) {
        update(id, { status: 'error', error: `Sorry: ${e instanceof Error ? e.message : String(e)}`, elapsedMs: Date.now() - startedAt })
      }
    },
    [update],
  )

  const reset = useCallback(() => setThread({ turns: [] }), [])

  return { turns: thread.turns, ask, reset }
}
