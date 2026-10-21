import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Sparkles, Radar, FileCheck2, TrendingUp, RotateCcw, Megaphone, Network, Loader2, Settings } from 'lucide-react'
import { api } from '../api/client'
import { ToastProvider, useToast } from '../components/Toast'
import GeniePanel from '../components/genie/GeniePanel'
import { GeniePanelProvider, useGeniePanel } from '../state/genie-panel'
import ThemeSwitch from '../components/ThemeSwitch'
import HalloweenDecor from '../components/HalloweenDecor'
import { BrandLockup } from '../components/BrandMark'

const navItems = [
  { to: '/measure', label: 'Measure', icon: Radar },
  { to: '/fix', label: 'Fix', icon: FileCheck2 },
  { to: '/impact', label: 'Impact', icon: TrendingUp },
]

function Shell() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { toggle, openPanel } = useGeniePanel()
  const { data: suggestions } = useQuery({ queryKey: ['suggestions'], queryFn: api.suggestions })
  const pendingCount = suggestions?.filter(s => s.state === 'pending_review').length ?? 0

  const [resetRunId, setResetRunId] = useState<number | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const settingsRef = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()

  // Close the settings menu on an outside click, Escape, or navigation.
  useEffect(() => {
    if (!showSettings) return
    const onDown = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) setShowSettings(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShowSettings(false)
    }
    document.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [showSettings])
  useEffect(() => setShowSettings(false), [pathname])

  const handleReset = async () => {
    setShowSettings(false)
    if (resetRunId) return
    if (!window.confirm('Reset the demo? This restores the starting pages, suggestions and probe results.')) return
    try {
      const { run_id } = await api.reset()
      setResetRunId(run_id)
    } catch (err) {
      toast(err instanceof Error ? err.message : "Couldn't start the reset. Try again.")
    }
  }

  // "/" opens Ask Genie (the panel focuses its composer) unless the user is typing somewhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && (['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName) || t.isContentEditable)) return
      e.preventDefault()
      openPanel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openPanel])

  // Poll the reset job until it finishes, then refresh every screen.
  useEffect(() => {
    if (!resetRunId) return
    let stopped = false
    let timer: number
    const tick = async () => {
      if (stopped) return
      try {
        const st = await api.resetStatus(resetRunId)
        const done = ['TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'].includes(st.life_cycle_state ?? '')
        if (done) {
          setResetRunId(null)
          await queryClient.invalidateQueries()
          toast(st.result_state === 'SUCCESS' ? 'Demo reset complete.' : 'Reset did not finish cleanly. Try again.')
          return
        }
      } catch {
        // transient polling error; keep trying
      }
      if (!stopped) timer = window.setTimeout(tick, 5000)
    }
    timer = window.setTimeout(tick, 5000)
    return () => { stopped = true; window.clearTimeout(timer) }
  }, [resetRunId, queryClient, toast])

  return (
    <div className="min-h-screen">
      <HalloweenDecor />
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <BrandLockup />
            <div className="h-8 w-px bg-gray-200" />
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl lce-gradient flex items-center justify-center shadow-glow-orange">
                <Sparkles className="w-4 h-4 text-white" />
              </div>
              <div className="leading-tight">
                <p className="text-lg font-bold tracking-tight"><span className="text-lce-orange">GEO</span>logic</p>
                <p className="text-xs text-text-secondary hidden md:block">littlecaesars.com · 62 pages</p>
              </div>
            </div>
          </div>

          <nav className="hidden lg:flex items-center bg-surface-secondary rounded-2xl p-1.5 gap-0.5">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${isActive ? 'bg-surface text-lce-orange shadow-soft' : 'text-text-secondary hover:text-text-primary'}`}
              >
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
                {item.to === '/fix' && pendingCount > 0 && (
                  <span className="ml-1 text-[11px] font-semibold bg-lce-orange text-white rounded-full px-1.5">{pendingCount}</span>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-1">
            <button className="btn btn-primary" onClick={toggle} title="Ask Genie (/)" aria-label="Ask Genie">
              <Sparkles className="w-4 h-4" />
              <span className="hidden sm:inline">Ask Genie</span>
            </button>

            {/* Settings: theme, Architecture, Reset demo */}
            <div className="relative" ref={settingsRef}>
              <button
                type="button"
                onClick={() => setShowSettings(v => !v)}
                aria-label="Settings"
                aria-haspopup="menu"
                aria-expanded={showSettings}
                title="Settings"
                className={`relative p-2.5 rounded-xl hover:bg-gray-100 transition-colors ${pathname.startsWith('/architecture') ? 'text-lce-orange' : 'text-text-secondary'}`}
              >
                <motion.div animate={{ rotate: showSettings ? 180 : 0 }} transition={{ duration: 0.4, ease: 'easeInOut' }}>
                  <Settings className="w-5 h-5" />
                </motion.div>
                {resetRunId && <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-500 animate-pulse-soft" />}
              </button>

              <AnimatePresence>
                {showSettings && (
                  <motion.div
                    role="menu"
                    initial={{ opacity: 0, y: -10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className="absolute top-full right-0 mt-2 w-56 bg-surface rounded-xl shadow-strong border border-gray-100 py-1 z-50 origin-top-right"
                  >
                    <div className="px-3 py-2.5">
                      <ThemeSwitch />
                    </div>
                    <div className="h-px bg-gray-100 my-1" />
                    <NavLink
                      to="/architecture"
                      role="menuitem"
                      className={({ isActive }) => `w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors text-sm font-medium ${isActive ? 'text-lce-orange' : 'text-text-primary'}`}
                    >
                      <Network className="w-4 h-4 text-text-secondary" />
                      Architecture
                    </NavLink>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleReset}
                      disabled={!!resetRunId}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors text-sm font-medium text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {resetRunId ? <Loader2 className="w-4 h-4 text-text-secondary animate-spin" /> : <RotateCcw className="w-4 h-4 text-text-secondary" />}
                      {resetRunId ? 'Resetting demo...' : 'Reset demo'}
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Navigation */}
      <nav className="lg:hidden sticky top-16 z-40 bg-surface border-b border-gray-100 overflow-x-auto">
        <div className="flex items-center gap-1 px-4 py-2">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-all ${isActive ? 'bg-lce-orange/10 text-lce-orange' : 'text-text-secondary hover:text-text-primary'}`}
            >
              <item.icon className="w-4 h-4" />
              <span>{item.label}</span>
              {item.to === '/fix' && pendingCount > 0 && (
                <span className="ml-1 text-[11px] font-semibold bg-lce-orange text-white rounded-full px-1.5">{pendingCount}</span>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <main className="relative z-10 max-w-[1600px] mx-auto px-6 py-6">
        {resetRunId && (
          <div role="status" className="mb-4 flex items-center gap-2 px-4 py-2.5 rounded-xl border border-amber-200 bg-amber-50 text-sm text-amber-800">
            <Loader2 className="w-4 h-4 animate-spin" />
            Resetting demo... Screens refresh automatically when it finishes.
          </div>
        )}
        <div className="mb-4 flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-lce-orange/10 rounded-full border border-lce-orange/20">
            <Megaphone className="w-4 h-4 text-lce-orange" />
            <span className="text-sm font-medium text-lce-orange-dark">Brand Marketing View</span>
          </div>
        </div>

        <Outlet />
      </main>

      <p className="text-center text-xs text-text-tertiary mt-10 pb-6">
        Built on Databricks · Zerobus · Lakeflow · AI Gateway · Agent Bricks · Vector Search · Lakebase · AI/BI · Genie
      </p>
    </div>
  )
}

export default function AppLayout() {
  return (
    <ToastProvider>
      <GeniePanelProvider>
        <Shell />
        <GeniePanel />
      </GeniePanelProvider>
    </ToastProvider>
  )
}
