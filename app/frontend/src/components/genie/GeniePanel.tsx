import { useEffect, useRef, type CSSProperties, type KeyboardEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { ArrowUp, RotateCcw, Sparkles, X } from 'lucide-react'
import { tabForPath, useGeniePanel } from '../../state/genie-panel'
import GenieTurn from './GenieTurn'

export const STARTERS = ['Which question cluster has the lowest Share of Model?', 'Which engine still gets our prices wrong?', 'What are the top 3 opportunities and why?']

const SUGGESTED: Record<string, string[]> = {
  Measure: ['Which question cluster has the lowest Share of Model?', "How does our Share of Model compare to Domino's by engine?", "Which publishers do engines cite most when they don't cite us?"],
  Fix: ['Which engine still gets our prices wrong?', 'What are the top 3 opportunities and why?', 'Which opportunities expire in the next 48 hours?'],
  Prove: STARTERS,
  Architecture: STARTERS,
}

/** Right-side Ask Genie slide-over, mounted once in AppLayout. Visibility flips at once on open (so the composer
 *  can take focus) and only after the slide-out on close (so a closed panel is out of the tab order). */
export default function GeniePanel() {
  const { open, closePanel, ask, turns, busy, newChat, contextLabel, draft, setDraft } = useGeniePanel()
  const { pathname } = useLocation()
  const suggestions = SUGGESTED[tabForPath(pathname)] ?? STARTERS
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (open && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [turns, open])

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus({ preventScroll: true })
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') closePanel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, closePanel])

  const canSend = !busy && !!draft.trim()
  const send = () => {
    if (!canSend) return
    ask(draft)
    setDraft('')
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <>
      <div
        onClick={closePanel}
        aria-hidden
        className={`fixed inset-0 z-[60] bg-black/30 transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      />
      <aside
        role="dialog"
        aria-label="Ask Genie"
        aria-hidden={!open}
        className={`fixed inset-y-0 right-0 z-[70] w-[480px] max-w-full flex flex-col bg-surface-secondary shadow-strong duration-300 ${open ? 'translate-x-0 visible transition-transform' : 'translate-x-full invisible transition-[transform,visibility]'}`}
      >
        <div className="bg-lce-black text-white px-5 py-4 flex items-center gap-3 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-lce-orange flex items-center justify-center shrink-0">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold">Ask Genie</p>
            <p className="text-xs text-white/60 truncate" title={contextLabel}>Context: {contextLabel}</p>
          </div>
          {turns.length > 0 && (
            <button
              type="button"
              onClick={newChat}
              disabled={busy}
              className="inline-flex items-center gap-1.5 h-7 px-3 rounded-full border border-white/20 text-xs font-medium hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RotateCcw className="w-3 h-3" />
              New chat
            </button>
          )}
          <button type="button" onClick={closePanel} aria-label="Close Ask Genie" className="p-1.5 rounded-lg text-white/70 hover:text-white hover:bg-white/10">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-6">
          {turns.length === 0 ? (
            <div className="space-y-3">
              <p className="text-sm text-text-secondary">Answers in plain English, with the SQL behind them, on governed GEOlogic data.</p>
              {suggestions.map(q => (
                <button
                  key={q}
                  type="button"
                  onClick={() => ask(q)}
                  className="w-full text-left flex items-center gap-2.5 rounded-xl border border-gray-200 bg-white px-3.5 py-2.5 text-sm hover:border-lce-orange/50 hover:bg-lce-cream transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5 text-lce-orange shrink-0" />
                  {q}
                </button>
              ))}
            </div>
          ) : (
            turns.map(t => <GenieTurn key={t.id} turn={t} busy={busy} onFollowUp={ask} />)
          )}
        </div>

        <div className="p-4 border-t border-gray-100 bg-white shrink-0">
          <div className="rounded-2xl border border-gray-200 bg-surface-secondary p-2 pl-4 flex items-end gap-2 focus-within:border-lce-orange focus-within:ring-2 focus-within:ring-lce-orange/20">
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              aria-label="Ask Genie a question"
              placeholder="Ask about Share of Model, wrong claims, opportunities..."
              className="flex-1 resize-none bg-transparent text-sm outline-none focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-text-tertiary max-h-40 py-2"
              style={{ fieldSizing: 'content' } as CSSProperties}
            />
            <button
              type="button"
              onClick={send}
              disabled={!canSend}
              aria-label="Send"
              className="w-9 h-9 shrink-0 rounded-xl lce-gradient text-white flex items-center justify-center disabled:opacity-50"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
