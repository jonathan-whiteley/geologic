import type { CitedDoc } from '../api/types'
import { ownerChip } from '../lib/owners'

/** A cited source: domain colored by owner class, linking to the page. */
export default function CitationChip({ doc }: { doc: Pick<CitedDoc, 'domain' | 'owner_class' | 'url' | 'title' | 'doc_id'> }) {
  const cls = `inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[11px] ${ownerChip(doc.owner_class)}`
  if (!doc.url) return <span className={cls} title={doc.title}>{doc.domain || doc.doc_id}</span>
  return (
    <a href={doc.url} target="_blank" rel="noreferrer" className={`${cls} hover:underline`} title={doc.owner_class ? `${doc.title} · ${doc.owner_class}` : doc.title}
      onClick={e => e.stopPropagation()}>
      {doc.domain || doc.doc_id}
    </a>
  )
}
