import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { api } from '../api/client'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import { STARTERS } from '../components/genie/GeniePanel'
import FixLedger from '../components/FixLedger'
import GeoFunnel from '../components/GeoFunnel'
import Indicators from '../components/Indicators'
import ShareTrend from '../components/ShareTrend'
import Movers from '../components/Movers'
import { useGeniePanel } from '../state/genie-panel'

export default function ImpactPage() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['impact'], queryFn: api.impact })
  const { ask } = useGeniePanel()

  if (isLoading) return <PageSkeleton statCards={0} />
  if (isError || !data) return <ErrorRetry message="Couldn't load Impact." onRetry={() => refetch()} />

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Impact</p>
        <h2 className="text-2xl font-semibold">Did the engines change their answer?</h2>
        <p className="text-text-secondary">Fixes move citations first; Share of Model follows.</p>
      </div>

      <FixLedger ledger={data.ledger} />
      <GeoFunnel funnel={data.funnel} />
      <Indicators d={data} />
      <ShareTrend weekly={data.weekly} markers={data.markers} />
      <Movers d={data} />

      <div className="card p-6 space-y-3">
        <div className="flex items-center gap-3">
          <div className="icon-tile"><Sparkles className="w-5 h-5" /></div>
          <div>
            <h3 className="font-semibold">What to ask next</h3>
            <p className="text-sm text-text-secondary">Genie answers with SQL on governed metric views</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {STARTERS.map(q => (
            <button key={q} type="button" onClick={() => ask(q)}
              className="rounded-full border border-lce-orange/30 bg-lce-cream px-3 py-1.5 text-sm text-lce-orange-dark hover:bg-orange-100">{q}</button>
          ))}
        </div>
      </div>
    </div>
  )
}
