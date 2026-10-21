import type { Fix } from '../api/types'
import { MESSAGE_ASSETS } from '../lib/fixLabels'

function lines(text: string | null): string[] {
  return (text ?? '').split('\n').filter((l, i, a) => l.trim() !== '' || (i > 0 && i < a.length - 1))
}

function prettyJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

/** The proposed change: an insert under its anchor section, a replace (before struck, after added), a new page, JSON-LD, or a message. */
export default function SectionDiff({ fix }: { fix: Pick<Fix, 'asset_type' | 'op' | 'section_before' | 'patch_text' | 'page_id' | 'section_id'> }) {
  if (fix.asset_type === 'jsonld') {
    return <pre className="code">{prettyJson(fix.patch_text)}</pre>
  }
  if (MESSAGE_ASSETS.has(fix.asset_type)) {
    return <div className="code !font-sans !text-sm">{fix.patch_text}</div>
  }
  const target = [fix.page_id, fix.section_id].filter(Boolean).join(' · ')
  if (fix.op === 'insert') {
    return (
      <div className="space-y-1">
        {target && <p className="font-mono text-[11px] text-text-tertiary">{target}</p>}
        <div className="code">
          {lines(fix.section_before).map((l, i) => <span key={`b${i}`} className="block text-text-tertiary">{l || ' '}</span>)}
          {lines(fix.patch_text).map((l, i) => <span key={`a${i}`} className="add">+ {l}</span>)}
        </div>
      </div>
    )
  }
  if (fix.op === 'replace') {
    return (
      <div className="space-y-1">
        {target && <p className="font-mono text-[11px] text-text-tertiary">{target}</p>}
        <div className="code">
          {lines(fix.section_before).map((l, i) => <span key={`b${i}`} className="del">- {l}</span>)}
          {lines(fix.patch_text).map((l, i) => <span key={`a${i}`} className="add">+ {l}</span>)}
        </div>
      </div>
    )
  }
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold text-green-700">New page{fix.page_id ? ` · ${fix.page_id}` : ''}</p>
      <div className="code">
        {lines(fix.patch_text).map((l, i) => <span key={i} className="add">+ {l}</span>)}
      </div>
    </div>
  )
}
