/** Global Ask Genie slide-over state: open or closed, one conversation, and the context sent with each ask. */
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { useGenieThread, type Turn } from '../lib/genie'

const TABS: [string, string][] = [
  ['/measure', 'Measure'],
  ['/fix', 'Fix'],
  ['/prove', 'Prove'],
  ['/architecture', 'Architecture'],
]

export function tabForPath(pathname: string): string {
  return TABS.find(([p]) => pathname === p || pathname.startsWith(`${p}/`))?.[1] ?? 'Measure'
}

type GeniePanelApi = {
  open: boolean
  openPanel(): void
  closePanel(): void
  toggle(): void
  ask(q: string): void
  turns: Turn[]
  busy: boolean
  newChat(): void
  contextLabel: string
  setFocus(label: string | null): void
}

const Ctx = createContext<GeniePanelApi | null>(null)

export function GeniePanelProvider({ children }: { children: ReactNode }) {
  const thread = useGenieThread()
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [focus, setFocusState] = useState<string | null>(null)
  const [focusPath, setFocusPath] = useState(pathname)

  // Clear the focus item on route change, during render so pages that set it on mount win.
  if (focusPath !== pathname) {
    setFocusPath(pathname)
    setFocusState(null)
  }

  const tab = tabForPath(pathname)
  const contextLabel = focus ? `${tab} · ${focus}` : tab
  const busy = thread.turns.some(t => t.status === 'pending')

  const live = useRef({ busy, contextLabel, ask: thread.ask })
  live.current = { busy, contextLabel, ask: thread.ask }

  const openPanel = useCallback(() => setOpen(true), [])
  const closePanel = useCallback(() => setOpen(false), [])
  const toggle = useCallback(() => setOpen(v => !v), [])
  const setFocus = useCallback((label: string | null) => setFocusState(label), [])

  const ask = useCallback((q: string) => {
    setOpen(true)
    const question = q.trim()
    // One message at a time per Genie conversation: a second ask while one is running only opens the panel.
    if (!question || live.current.busy) return
    void live.current.ask(question, live.current.contextLabel)
  }, [])

  const { turns, reset } = thread
  const value = useMemo<GeniePanelApi>(
    () => ({ open, openPanel, closePanel, toggle, ask, turns, busy, newChat: reset, contextLabel, setFocus }),
    [open, openPanel, closePanel, toggle, ask, turns, busy, reset, contextLabel, setFocus],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useGeniePanel(): GeniePanelApi {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useGeniePanel must be used inside <GeniePanelProvider>')
  return ctx
}
