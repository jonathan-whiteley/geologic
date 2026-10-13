import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles, Radar, FileCheck2, TrendingUp, RotateCcw, Megaphone, Network, Loader2 } from 'lucide-react'
import { api } from '../api/client'
import { ToastProvider, useToast } from '../components/Toast'

const navItems = [
  { to: '/measure', label: 'Measure', icon: Radar },
  { to: '/fix', label: 'Fix', icon: FileCheck2 },
  { to: '/prove', label: 'Prove', icon: TrendingUp },
]

function Shell() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: suggestions } = useQuery({ queryKey: ['suggestions'], queryFn: api.suggestions })
  const pendingCount = suggestions?.filter(s => s.state === 'pending_review').length ?? 0

  const [resetRunId, setResetRunId] = useState<number | null>(null)

  const handleReset = async () => {
    if (resetRunId) return
    if (!window.confirm('Reset the demo? This restores the starting pages, suggestions and probe results.')) return
    try {
      const { run_id } = await api.reset()
      setResetRunId(run_id)
    } catch (err) {
      toast(err instanceof Error ? err.message : "Couldn't start the reset. Try again.")
    }
  }

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
    <div className="min-h-screen bg-surface-secondary">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <img src="/lce-logo.svg" alt="Little Caesars" className="h-12 w-auto" />
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
                  `flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${isActive ? 'bg-white text-lce-orange shadow-soft' : 'text-text-secondary hover:text-text-primary'}`}
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
            <NavLink to="/architecture" title="Architecture"
              className={({ isActive }) => `btn btn-ghost ${isActive ? 'text-lce-orange' : ''}`}>
              <Network className="w-4 h-4" />
              <span className="hidden xl:inline">Architecture</span>
            </NavLink>
            <button onClick={handleReset} className="btn btn-ghost" title="Reset demo" disabled={!!resetRunId}>
              {resetRunId ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
              <span className="hidden xl:inline">Reset</span>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Navigation */}
      <nav className="lg:hidden sticky top-16 z-40 bg-white border-b border-gray-100 overflow-x-auto">
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
      <main className="max-w-[1600px] mx-auto px-6 py-6">
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
        Built on Databricks · Zerobus · Lakeflow · Agent Bricks · Vector Search · Lakebase · AI/BI · Genie
      </p>
    </div>
  )
}

export default function AppLayout() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  )
}
