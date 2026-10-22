import { useCallback } from 'react'
import {
  Background,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  Handle,
  Position,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { toPng, toSvg } from 'html-to-image'
import { ListChecks, DoorOpen, Bot, Scale, ShieldCheck, Globe, Zap, Workflow, ScanEye, Search, ClipboardList, Sparkles, Database, ScrollText, BarChart3, MessageSquareText, LayoutDashboard } from 'lucide-react'

type Layer = 'uc' | 'gateway' | 'search' | 'ingest' | 'pipeline' | 'lakebase' | 'genie' | 'app'

/** Every color is an --arch-* variable (index.css), so Spooky mode themes the canvas and the export resolves it. */
function tone(v: string, label: string) {
  return { fg: `rgb(var(${v}))`, ring: `rgb(var(${v}) / 0.40)`, tint: `rgb(var(${v}) / 0.10)`, label }
}

const LAYER: Record<Layer, { fg: string; ring: string; tint: string; label: string }> = {
  uc: tone('--arch-slate', 'Unity Catalog'),
  // Navy flips to lavender in Spooky mode (see --arch-navy) so it reads on the dark canvas.
  gateway: tone('--arch-navy', 'AI Gateway'),
  search: tone('--arch-search', 'Vector Search'),
  ingest: tone('--arch-ingest', 'Zerobus Ingest'),
  pipeline: tone('--arch-pipeline', 'Lakeflow SDP'),
  lakebase: tone('--arch-lakebase', 'Lakebase'),
  genie: tone('--arch-genie', 'Genie'),
  app: tone('--arch-app', 'Databricks App'),
}

interface CardData {
  title: string
  sub: string
  icon: React.ReactNode
  layer: Layer
}

function CardNode({ data }: NodeProps) {
  const d = data as unknown as CardData
  const tone = LAYER[d.layer]
  return (
    <div
      style={{
        background: 'rgb(var(--surface-default))',
        border: `1.5px solid ${tone.ring}`,
        borderRadius: 10,
        padding: '12px 14px',
        minWidth: 180,
        maxWidth: 200,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.08)',
        fontFamily: 'var(--font-sans)',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        cursor: 'grab',
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: tone.tint,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <div style={{ color: tone.fg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {d.icon}
        </div>
      </div>
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 12.5,
            fontWeight: 600,
            color: tone.fg,
            letterSpacing: '-0.01em',
            lineHeight: 1.1,
            wordWrap: 'break-word',
          }}
        >
          {d.title}
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'rgb(var(--arch-muted))',
            marginTop: 3,
            lineHeight: 1.25,
            wordWrap: 'break-word',
          }}
        >
          {d.sub}
        </div>
      </div>
      <Handle type="target" position={Position.Left} isConnectable={false} style={hiddenHandle} />
      <Handle type="source" position={Position.Right} isConnectable={false} style={hiddenHandle} />
      <Handle id="bottom-source" type="source" position={Position.Bottom} isConnectable={false} style={hiddenHandle} />
      <Handle id="bottom-target" type="target" position={Position.Bottom} isConnectable={false} style={hiddenHandle} />
      <Handle id="top-source" type="source" position={Position.Top} isConnectable={false} style={hiddenHandle} />
      <Handle id="top-target" type="target" position={Position.Top} isConnectable={false} style={hiddenHandle} />
      <Handle id="left-source" type="source" position={Position.Left} isConnectable={false} style={hiddenHandle} />
      <Handle id="right-target" type="target" position={Position.Right} isConnectable={false} style={hiddenHandle} />
    </div>
  )
}

const hiddenHandle: React.CSSProperties = {
  background: 'transparent',
  border: 0,
  width: 1,
  height: 1,
  pointerEvents: 'none',
}

function HeaderNode({ data }: NodeProps) {
  const d = data as unknown as { label: string; width?: number }
  return (
    <div
      style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'rgb(var(--arch-faint))',
        padding: '8px 0 10px',
        borderBottom: '1.5px solid rgb(var(--arch-line))',
        width: d.width ?? 200,
        textAlign: 'center',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {d.label}
    </div>
  )
}

function BandNode({ data }: NodeProps) {
  const d = data as unknown as { label: string; width: number }
  const tone = LAYER.uc
  return (
    <div
      style={{
        width: d.width,
        padding: '12px 16px',
        background: tone.tint,
        border: `1.5px solid ${tone.ring}`,
        borderRadius: 10,
        textAlign: 'center',
        fontSize: 12.5,
        fontWeight: 600,
        color: tone.fg,
        letterSpacing: '-0.01em',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {d.label}
    </div>
  )
}

const EXTENSIONS = [
  'AI referral sessions and conversions from web analytics',
  'AI crawler hits from server logs',
  'Imported GEO tool data',
]

function ExtensionsNode() {
  return (
    <div
      style={{
        width: 240,
        padding: '12px 14px',
        background: 'rgb(var(--surface-default))',
        border: '1.5px dashed rgb(var(--arch-faint))',
        borderRadius: 10,
        fontFamily: 'var(--font-sans)',
        cursor: 'grab',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: 'rgb(var(--text-primary))' }}>Production extensions</span>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'rgb(var(--arch-muted))',
            border: '1px solid rgb(var(--arch-line))',
            borderRadius: 999,
            padding: '1px 7px',
          }}
        >
          not demoed
        </span>
      </div>
      <ul style={{ margin: '8px 0 0', paddingLeft: 16, fontSize: 11, lineHeight: 1.4, color: 'rgb(var(--arch-muted))', listStyle: 'disc' }}>
        {EXTENSIONS.map((e) => (
          <li key={e}>{e}</li>
        ))}
      </ul>
      <p style={{ margin: '8px 0 0', fontSize: 11, lineHeight: 1.35, color: 'rgb(var(--arch-muted))', fontStyle: 'italic' }}>
        All join in Unity Catalog to prompts, answers, claims and sources.
      </p>
    </div>
  )
}

const nodeTypes = { card: CardNode, header: HeaderNode, band: BandNode, extensions: ExtensionsNode }

const HEADER_Y = -40

const ICON = { size: 16, strokeWidth: 2 }

function card(
  id: string,
  x: number,
  y: number,
  layer: Layer,
  title: string,
  sub: string,
  icon: React.ReactNode,
): Node {
  return {
    id,
    type: 'card',
    position: { x, y },
    data: { title, sub, icon, layer },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  }
}

function header(id: string, x: number, label: string, width: number): Node {
  return { id, type: 'header', position: { x, y: HEADER_Y }, data: { label, width }, draggable: false, selectable: false }
}

const COL = { measure: 0, web: 250, fix: 540, issues: 790, impact: 1080, app: 1360 }
const ROW = (i: number) => 40 + i * 120

const INITIAL_NODES: Node[] = [
  header('hdr-measure', COL.measure, 'Measure', 450),
  header('hdr-fix', COL.fix, 'Fix', 450),
  header('hdr-impact', COL.impact, 'Impact', 200),
  header('hdr-app', COL.app, 'App', 240),
  // Measure: tracked prompts through AI Gateway to four engines, judged and checked against facts
  card('prompts', COL.measure, ROW(0), 'uc', '30 tracked prompts', 'With est. monthly searches', <ListChecks {...ICON} />),
  card('gateway', COL.measure, ROW(1), 'gateway', 'AI Gateway', 'One governed door; usage and cost logged', <DoorOpen {...ICON} />),
  card('engines', COL.measure, ROW(2), 'gateway', 'Claude · ChatGPT · Gemini · Meta AI', '120 answers', <Bot {...ICON} />),
  card('judge', COL.measure, ROW(3), 'gateway', 'LLM judge', 'Mentions, rank, citations, claims', <Scale {...ICON} />),
  card('claims', COL.measure, ROW(4), 'uc', 'Claims checked against brand_facts', 'Correct, Outdated, Wrong', <ShieldCheck {...ICON} />),
  card('web', COL.web, ROW(2), 'search', 'Simulated web', 'Direct Vector Access index (re-embedded on approve)', <Globe {...ICON} />),
  // Fix: signals become moments and prompts; issues become grounded, verified fixes
  card('zerobus', COL.fix, ROW(0), 'ingest', 'Zerobus Ingest', 'Social posts and reviews stream into Delta', <Zap {...ICON} />),
  card('sdp', COL.fix, ROW(1), 'pipeline', 'Lakeflow SDP', 'Classify, quarantine by policy', <Workflow {...ICON} />),
  card('vision', COL.fix, ROW(2), 'pipeline', 'Vision match', 'Photo to menu item', <ScanEye {...ICON} />),
  card('moment', COL.fix, ROW(3), 'search', 'Moment → prompt (Vector Search)', 'New prompts worth tracking', <Search {...ICON} />),
  card('issues', COL.issues, ROW(0), 'uc', 'Issues builder', 'Wrong, Outdated, Missing us, No answer page, Moment gap', <ClipboardList {...ICON} />),
  card('drafter', COL.issues, ROW(1), 'gateway', 'Grounded drafter + verifier', 'Section patches with checks', <Sparkles {...ICON} />),
  card('approvals', COL.issues, ROW(2), 'lakebase', 'Lakebase approvals and fix results', 'Approve, upsert, re-ask', <Database {...ICON} />),
  // Impact
  card('ledger', COL.impact, ROW(0), 'lakebase', 'Fix ledger (Lakebase)', 'Every fix and its before and after', <ScrollText {...ICON} />),
  card('metrics', COL.impact, ROW(2), 'uc', 'Metric views', 'Share of Model, accuracy, citations', <BarChart3 {...ICON} />),
  card('genie', COL.impact, ROW(3), 'genie', 'Genie', 'Ask in plain English, see the SQL', <MessageSquareText {...ICON} />),
  // App
  card('app', COL.app, ROW(1), 'app', 'Databricks App', 'GEOlogic: Measure, Fix, Impact', <LayoutDashboard {...ICON} />),
  { id: 'extensions', type: 'extensions', position: { x: COL.app, y: ROW(3) - 20 }, data: {} },
  // Unity Catalog band
  {
    id: 'uc',
    type: 'band',
    position: { x: 0, y: ROW(5) },
    data: { label: 'Unity Catalog: governance, lineage, usage and cost logged by AI Gateway', width: COL.app + 240 },
    draggable: false,
    selectable: false,
  },
]

function edge(
  source: string,
  target: string,
  opts: { color?: string; label?: string; animated?: boolean; dashed?: boolean; sourceHandle?: string; targetHandle?: string } = {},
): Edge {
  const dashed = opts.dashed ?? false
  return {
    id: `${source}->${target}`,
    source,
    target,
    sourceHandle: opts.sourceHandle,
    targetHandle: opts.targetHandle,
    type: 'smoothstep',
    animated: opts.animated ?? false,
    label: opts.label,
    labelStyle: {
      fontSize: 10,
      fill: 'rgb(var(--arch-muted))',
      fontFamily: 'var(--font-mono)',
    },
    labelBgStyle: { fill: 'rgb(var(--surface-default))' },
    labelBgPadding: [4, 2],
    style: {
      stroke: opts.color ?? 'rgb(var(--arch-edge))',
      strokeWidth: 1.5,
      strokeDasharray: dashed ? '5 5' : undefined,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: opts.color ?? 'rgb(var(--arch-edge))',
      width: 16,
      height: 16,
    },
  }
}

const DOWN = { sourceHandle: 'bottom-source', targetHandle: 'top-target' }

const INITIAL_EDGES: Edge[] = [
  // Measure
  edge('prompts', 'gateway', { color: LAYER.gateway.fg, animated: true, ...DOWN }),
  edge('gateway', 'engines', { color: LAYER.gateway.fg, animated: true, ...DOWN }),
  edge('web', 'engines', { color: LAYER.search.fg, animated: true, label: 'Top hits', sourceHandle: 'left-source', targetHandle: 'right-target' }),
  edge('engines', 'judge', { color: LAYER.gateway.fg, animated: true, ...DOWN }),
  edge('judge', 'claims', { color: LAYER.gateway.fg, animated: true, ...DOWN }),
  // Fix
  edge('zerobus', 'sdp', { color: LAYER.pipeline.fg, animated: true, ...DOWN }),
  edge('sdp', 'vision', { color: LAYER.pipeline.fg, animated: true, ...DOWN }),
  edge('vision', 'moment', { color: LAYER.search.fg, animated: true, ...DOWN }),
  edge('moment', 'prompts', { color: LAYER.search.fg, dashed: true, label: 'Track', sourceHandle: 'left-source', targetHandle: 'right-target' }),
  edge('claims', 'issues', { color: LAYER.uc.fg, animated: true }),
  edge('issues', 'drafter', { color: LAYER.gateway.fg, animated: true, ...DOWN }),
  edge('drafter', 'approvals', { color: LAYER.lakebase.fg, animated: true, ...DOWN }),
  edge('approvals', 'web', { color: LAYER.search.fg, dashed: true, label: 'Upsert + re-ask', sourceHandle: 'left-source', targetHandle: 'right-target' }),
  // Impact and App
  edge('approvals', 'ledger', { color: LAYER.lakebase.fg, animated: true }),
  edge('claims', 'metrics', { color: LAYER.uc.fg, animated: true }),
  edge('metrics', 'genie', { color: LAYER.genie.fg, animated: true, ...DOWN }),
  edge('ledger', 'app', { color: LAYER.lakebase.fg, animated: true }),
  edge('metrics', 'app', { color: LAYER.uc.fg, animated: true }),
  edge('genie', 'app', { color: LAYER.genie.fg, animated: true, label: 'Answers' }),
]

function Toolbar() {
  const flow = useReactFlow()

  const onExport = useCallback(
    async (kind: 'png' | 'svg') => {
      const flowEl = document.querySelector('.react-flow') as HTMLElement | null
      if (!flowEl) return
      flow.fitView({ padding: 0.12, duration: 0 })
      await new Promise((r) => setTimeout(r, 80))
      const exporter = kind === 'png' ? toPng : toSvg
      const dataUrl = await exporter(flowEl, {
        // The exporter paints a canvas, so resolve the theme variable to a concrete color first.
        backgroundColor: `rgb(${getComputedStyle(document.documentElement).getPropertyValue('--arch-canvas').trim()})`,
        cacheBust: true,
        pixelRatio: 2,
        filter: (n: HTMLElement) => !n.classList?.contains?.('geo-arch-toolbar'),
      })
      const a = document.createElement('a')
      a.href = dataUrl
      a.download = `geologic-architecture.${kind}`
      a.click()
    },
    [flow],
  )

  return (
    <div
      className="geo-arch-toolbar"
      style={{
        position: 'absolute',
        top: 12,
        right: 12,
        zIndex: 10,
        display: 'flex',
        gap: 6,
        background: 'rgb(var(--surface-default) / 0.96)',
        padding: 6,
        borderRadius: 10,
        border: '1px solid rgb(var(--arch-line))',
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        backdropFilter: 'blur(8px)',
      }}
    >
      <ToolBtn onClick={() => flow.zoomIn({ duration: 200 })}>Zoom In</ToolBtn>
      <ToolBtn onClick={() => flow.zoomOut({ duration: 200 })}>Zoom Out</ToolBtn>
      <ToolBtn onClick={() => flow.fitView({ padding: 0.12, duration: 250 })}>Fit</ToolBtn>
      <ToolDivider />
      <ToolBtn onClick={() => onExport('png')}>PNG</ToolBtn>
      <ToolBtn onClick={() => onExport('svg')}>SVG</ToolBtn>
    </div>
  )
}

function ToolBtn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        height: 28,
        padding: '0 10px',
        border: 0,
        background: 'transparent',
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 500,
        color: 'rgb(var(--text-primary))',
        cursor: 'pointer',
        fontFamily: 'var(--font-sans)',
        transition: 'background 0.2s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgb(var(--gray-100))'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
      }}
    >
      {children}
    </button>
  )
}

function ToolDivider() {
  return <span style={{ width: 1, background: 'rgb(var(--arch-line))', margin: '4px 2px' }} />
}

function LegendFooter() {
  const layers = (Object.keys(LAYER) as Layer[]).map(key => ({ key, label: LAYER[key].label }))

  return (
    <div
      style={{
        borderTop: '1px solid rgb(var(--arch-line))',
        background: 'rgb(var(--surface-default))',
        padding: '12px 16px',
        display: 'flex',
        gap: 16,
        flexWrap: 'wrap',
        alignItems: 'center',
        fontSize: 12,
      }}
    >
      <span
        style={{
          fontSize: 10.5,
          fontWeight: 600,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'rgb(var(--arch-faint))',
        }}
      >
        Layers
      </span>
      {layers.map((l) => (
        <span
          key={l.key}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            color: 'rgb(var(--text-primary))',
          }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: 3,
              background: LAYER[l.key].fg,
              display: 'block',
            }}
          />
          {l.label}
        </span>
      ))}
    </div>
  )
}

function FlowInner() {
  const [nodes, _setNodes, onNodesChange] = useNodesState(INITIAL_NODES)
  const [edges, _setEdges, onEdgesChange] = useEdgesState(INITIAL_EDGES)

  return (
    <div style={{ position: 'relative', height: 'calc(100vh - 280px)', minHeight: 560 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.4}
        maxZoom={1.6}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={false}
        panOnScroll={false}
        zoomOnScroll
      >
        <Background gap={24} size={1} color='rgb(var(--arch-dot))' />
      </ReactFlow>
      <Toolbar />
    </div>
  )
}

export default function ArchitecturePage() {
  return (
    <div style={{ maxWidth: 1500 }}>
      <div className="space-y-4 mb-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Architecture</p>
          <h1 className="text-2xl font-semibold">System Architecture</h1>
          <p className="text-text-secondary">Measure what four AI engines say, fix the sources, prove the lift: all on Databricks, governed by Unity Catalog. Drag nodes · scroll to zoom · export to PNG/SVG.</p>
        </div>
      </div>
      <div
        style={{
          background: 'rgb(var(--arch-canvas))',
          border: '1px solid rgb(var(--arch-line))',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        }}
      >
        <ReactFlowProvider>
          <FlowInner />
        </ReactFlowProvider>
        <p
          style={{
            margin: 0,
            padding: '10px 16px',
            borderTop: '1px solid rgb(var(--arch-line))',
            background: 'rgb(var(--surface-default))',
            fontSize: 12,
            color: 'rgb(var(--arch-muted))',
          }}
        >
          Bring your GEO tool's data, or run your own probe. Either way, it lands in Unity Catalog.
        </p>
        <LegendFooter />
      </div>
    </div>
  )
}
