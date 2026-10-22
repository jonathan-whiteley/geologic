import { useEffect, useMemo, useRef, useState } from 'react'
import { fx } from '../lib/format'

export interface PizzaSlice { label: string; value: number; official: boolean }

// Both photos are normalized to the same geometry: 512px square, pizza centered, radius 200px.
// lce-pepperoni.webp is a Little Caesars menu photo kept out of the public repo (gitignored);
// pepperoni-cc0.webp (Wikimedia Commons, CC0) is the fallback.
const PHOTOS = ['/pizza/lce-pepperoni.webp', '/pizza/pepperoni-cc0.webp']
const C = 100
const R = 92 // pizza radius in viewBox units
const IMG = (512 / 200) * R
const PAD = 1.2 // degrees between slices
const OFFICIAL_CENTER = 180 // the photo's pulled slice points left
// Muted tints for the other sources, laid over a ghosted copy of the pizza.
const TINTS = ['#9FB3C8', '#A9BFA0', '#BBA9CF', '#D6BF94', '#B8B8C0', '#D4A99C']

const rad = (d: number) => (d * Math.PI) / 180
const pt = (r: number, d: number) => [C + r * Math.cos(rad(d)), C + r * Math.sin(rad(d))]

function wedge(r: number, a0: number, a1: number) {
  if (a1 - a0 <= 0.01) return ''
  const [x0, y0] = pt(r, a0)
  const [x1, y1] = pt(r, a1)
  return `M${C},${C} L${x0},${y0} A${r},${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1},${y1} Z`
}

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3)

export default function CitationPizza({ slices }: { slices: PizzaSlice[] }) {
  const ref = useRef<SVGSVGElement>(null)
  const [p, setP] = useState(0)
  const [active, setActive] = useState<number | null>(null)
  const [photo, setPhoto] = useState(0)

  const ordered = useMemo(() => [
    ...slices.filter(s => s.official),
    ...slices.filter(s => !s.official).sort((a, b) => b.value - a.value),
  ], [slices])
  const total = ordered.reduce((a, s) => a + s.value, 0) || 1
  const officialSweep = ordered[0]?.official ? (ordered[0].value / total) * 360 : 0
  const start = OFFICIAL_CENTER - officialSweep / 2
  const tintFor = (i: number) => TINTS[(i - (ordered[0]?.official ? 1 : 0)) % TINTS.length]

  // Fan the slices open once the card scrolls into view.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setP(1); return }
    let raf = 0
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return
      io.disconnect()
      const t0 = performance.now()
      const tick = (now: number) => {
        const t = Math.min(1, (now - t0) / 1100)
        setP(easeOut(t))
        if (t < 1) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    }, { threshold: 0.4 })
    io.observe(el)
    return () => { io.disconnect(); cancelAnimationFrame(raf) }
  }, [])

  // The pizza spins into place while the slices open from the owned slice outward.
  const spin = (1 - p) * -40
  let cum = 0
  const geo = ordered.map((s, i) => {
    const a0 = start + cum * p
    cum += (s.value / total) * 360
    const a1 = start + cum * p
    return { ...s, i, a0: a0 + PAD / 2, a1: a1 - PAD / 2, mid: (a0 + a1) / 2 }
  })

  const pizza = (
    <image href={PHOTOS[photo]} x={C - IMG / 2} y={C - IMG / 2} width={IMG} height={IMG}
      onError={() => setPhoto(n => Math.min(n + 1, PHOTOS.length - 1))} />
  )
  const shown = ordered[active ?? 0]
  const name = (s: PizzaSlice) => (s.official ? 'Little Caesars' : s.label)

  return (
    <div className="flex items-center gap-4">
      <svg ref={ref} viewBox="0 0 200 200" className="w-44 h-44 shrink-0 overflow-visible" role="img"
        aria-label={ordered.map(s => `${name(s)} ${fx(s.value, 0, '%')}`).join(', ')}>
        <defs>
          <filter id="pz-ghost"><feColorMatrix type="saturate" values="0.15" /></filter>
          <filter id="pz-shadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="3" stdDeviation="3.5" floodColor="#7A2E0E" floodOpacity="0.28" />
          </filter>
          {geo.map(g => (
            // The owned slice clips wide so the photo's pulled slice and cheese pull are not cut off.
            <clipPath key={g.label} id={`pz-clip-${g.i}`}><path d={wedge(g.official ? R * 1.35 : R, g.a0, g.a1)} /></clipPath>
          ))}
        </defs>
        <g style={{ transform: `rotate(${spin}deg)`, transformOrigin: '100px 100px' }}>
          {geo.map(g => {
            const on = active === g.i
            const lift = (g.official ? 3 * p : 0) + (on ? 7 : 0)
            return (
              <g key={g.label} tabIndex={0} aria-label={`${name(g)} ${fx(g.value, 0, '%')}`}
                className="pz-slice cursor-pointer outline-none"
                style={{
                  transform: `translate(${Math.cos(rad(g.mid)) * lift}px, ${Math.sin(rad(g.mid)) * lift}px)`,
                  opacity: active !== null && !on ? 0.5 : 1,
                }}
                onMouseEnter={() => setActive(g.i)} onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(g.i)} onBlur={() => setActive(null)}>
                {g.official ? (
                  <g clipPath={`url(#pz-clip-${g.i})`} filter="url(#pz-shadow)">{pizza}</g>
                ) : (
                  <>
                    <g clipPath={`url(#pz-clip-${g.i})`} filter="url(#pz-ghost)" opacity={on ? 0.55 : 0.28}>{pizza}</g>
                    <path d={wedge(R, g.a0, g.a1)} fill={tintFor(g.i)} opacity={on ? 0.75 : 0.55} />
                  </>
                )}
              </g>
            )
          })}
        </g>
      </svg>

      <div className="min-w-0 flex-1">
        {shown && (
          <div key={shown.label} className="pz-readout mb-3">
            <div className={`text-3xl font-bold tabular-nums leading-none ${shown.official ? 'text-lce-orange-dark' : 'text-text-primary'}`}>
              {fx(shown.value * Math.min(1, p * 1.15), 0, '%')}
            </div>
            <div className="text-xs text-text-secondary mt-1">
              {shown.official ? 'of citations point to Little Caesars pages' : `of citations come from ${shown.label.toLowerCase()} sources`}
            </div>
          </div>
        )}
        <ul className="space-y-1 text-xs">
          {ordered.map((s, i) => (
            <li key={s.label} onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
              className={`flex items-center gap-2 rounded-md px-1.5 py-0.5 transition-colors cursor-default ${active === i ? 'bg-surface-tertiary' : ''}`}>
              <i className="w-2.5 h-2.5 rounded-full block shrink-0" style={{ background: s.official ? '#FF671B' : tintFor(i) }} />
              <span className={`flex-1 truncate ${s.official ? 'font-medium text-lce-orange-dark' : 'text-text-secondary'}`}>{name(s)}</span>
              <span className="font-mono tabular-nums text-text-secondary">{fx(s.value, 0, '%')}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
