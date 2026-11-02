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
import { Radio, Star, Bot, Zap, Workflow, Search, Sparkles, Database, LayoutDashboard, DoorOpen, Scale, BarChart3, MessageSquareText } from 'lucide-react'

type Layer = 'source' | 'ingest' | 'pipeline' | 'gateway' | 'search' | 'agent' | 'lakebase' | 'genie' | 'app' | 'uc'

const LAYER: Record<Layer, { fg: string; ring: string; tint: string; label: string }> = {
  source: { fg: '#64748B', ring: 'rgba(100,116,139,0.40)', tint: 'rgba(100,116,139,0.10)', label: 'Sources' },
  ingest: { fg: '#FF671B', ring: 'rgba(255,103,27,0.40)', tint: 'rgba(255,103,27,0.10)', label: 'Zerobus Ingest' },
  pipeline: { fg: '#0EA5E9', ring: 'rgba(14,165,233,0.40)', tint: 'rgba(14,165,233,0.10)', label: 'Lakeflow SDP' },
  gateway: { fg: '#0B2026', ring: 'rgba(11,32,38,0.40)', tint: 'rgba(11,32,38,0.10)', label: 'AI Gateway' },
  search: { fg: '#8B5CF6', ring: 'rgba(139,92,246,0.40)', tint: 'rgba(139,92,246,0.10)', label: 'Vector Search' },
  agent: { fg: '#EC4899', ring: 'rgba(236,72,153,0.40)', tint: 'rgba(236,72,153,0.10)', label: 'Agent Bricks' },
  lakebase: { fg: '#F59E0B', ring: 'rgba(245,158,11,0.40)', tint: 'rgba(245,158,11,0.10)', label: 'Lakebase' },
  genie: { fg: '#14B8A6', ring: 'rgba(20,184,166,0.40)', tint: 'rgba(20,184,166,0.10)', label: 'Genie' },
  app: { fg: '#10B981', ring: 'rgba(16,185,129,0.40)', tint: 'rgba(16,185,129,0.10)', label: 'Databricks App' },
  uc: { fg: '#64748B', ring: 'rgba(100,116,139,0.40)', tint: 'rgba(100,116,139,0.10)', label: 'Unity Catalog' },
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
        background: '#fff',
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
            color: '#71717A',
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
        color: '#A1A1AA',
        padding: '8px 0 10px',
        borderBottom: '1.5px solid #E4E4E7',
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

const nodeTypes = { card: CardNode, header: HeaderNode, band: BandNode }

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

const INITIAL_NODES: Node[] = [
  header('hdr-measure', 0, 'Measure', 670),
  header('hdr-fix', 730, 'Fix', 480),
  header('hdr-impact', 1240, 'Impact', 200),
  header('hdr-serve', 1520, 'Serve', 200),
  // Measure
  card('src-social', 0, 40, 'source', 'Social and athlete posts', 'Posts with photos', <Radio {...ICON} />),
  card('src-reviews', 0, 150, 'source', 'Reviews', 'Guest ratings and comments', <Star {...ICON} />),
  card('src-crawler', 0, 260, 'source', 'AI crawler hits', 'GPTBot, PerplexityBot, ClaudeBot', <Bot {...ICON} />),
  card('zerobus', 235, 150, 'ingest', 'Zerobus Ingest', 'Signals stream into Delta, no message bus', <Zap {...ICON} />),
  card('sdp', 470, 150, 'pipeline', 'Lakeflow SDP', 'Classify, match to menu, quarantine', <Workflow {...ICON} />),
  card('gateway', 0, 400, 'gateway', 'AI Gateway', 'One governed door: Claude, ChatGPT, Gemini, Meta AI; usage tracked', <DoorOpen {...ICON} />),
  card('judge', 270, 410, 'gateway', 'LLM judge', 'Mentions, rank, fact checks', <Scale {...ICON} />),
  // Fix
  card('vs', 730, 150, 'search', 'Vector Search', 'Pages, menu, questions', <Search {...ICON} />),
  card('agent', 1010, 150, 'agent', 'Agent Bricks', 'Content Strategist drafts, Brand Guardian checks', <Sparkles {...ICON} />),
  card('lakebase', 1010, 20, 'lakebase', 'Lakebase', 'Approvals, page versions, proof', <Database {...ICON} />),
  // Impact
  card('genie', 1240, 150, 'genie', 'Genie', 'Ask in plain English, see the SQL', <MessageSquareText {...ICON} />),
  card('metrics', 1240, 410, 'pipeline', 'Metric views', 'Share of Model, accuracy, citations', <BarChart3 {...ICON} />),
  // Serve
  card('app', 1520, 150, 'app', 'Databricks App', 'GEOlogic', <LayoutDashboard {...ICON} />),
  // Unity Catalog band
  {
    id: 'uc',
    type: 'band',
    position: { x: 0, y: 540 },
    data: { label: 'Unity Catalog: governance, lineage, inference tables', width: 1720 },
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
      fill: '#71717A',
      fontFamily: 'var(--font-mono)',
    },
    labelBgStyle: { fill: '#fff' },
    labelBgPadding: [4, 2],
    style: {
      stroke: opts.color ?? '#D4D4D8',
      strokeWidth: 1.5,
      strokeDasharray: dashed ? '5 5' : undefined,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: opts.color ?? '#D4D4D8',
      width: 16,
      height: 16,
    },
  }
}

const INITIAL_EDGES: Edge[] = [
  edge('src-social', 'zerobus', { color: LAYER.ingest.fg }),
  edge('src-reviews', 'zerobus', { color: LAYER.ingest.fg }),
  edge('src-crawler', 'zerobus', { color: LAYER.ingest.fg }),
  edge('zerobus', 'sdp', { color: LAYER.pipeline.fg, animated: true }),
  edge('sdp', 'vs', { color: LAYER.search.fg, animated: true }),
  edge('gateway', 'judge', { color: LAYER.gateway.fg, animated: true }),
  edge('judge', 'metrics', { color: LAYER.gateway.fg, animated: true }),
  edge('sdp', 'metrics', { color: LAYER.pipeline.fg, animated: true, sourceHandle: 'bottom-source' }),
  edge('vs', 'agent', { color: LAYER.agent.fg, animated: true, label: 'Retrieval' }),
  edge('agent', 'lakebase', { color: LAYER.lakebase.fg, animated: true, label: 'Drafts', sourceHandle: 'top-source', targetHandle: 'bottom-target' }),
  edge('lakebase', 'app', { color: LAYER.lakebase.fg, animated: true, label: 'Approvals', targetHandle: 'top-target' }),
  edge('metrics', 'genie', { color: LAYER.genie.fg, animated: true, sourceHandle: 'top-source', targetHandle: 'bottom-target' }),
  edge('genie', 'app', { color: LAYER.app.fg, animated: true, label: 'Answers' }),
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
        backgroundColor: '#FAFAFA',
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
        background: 'rgba(255,255,255,0.96)',
        padding: 6,
        borderRadius: 10,
        border: '1px solid #E4E4E7',
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
        color: '#1A1A1A',
        cursor: 'pointer',
        fontFamily: 'var(--font-sans)',
        transition: 'background 0.2s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = '#F5F5F5'
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
  return <span style={{ width: 1, background: '#E4E4E7', margin: '4px 2px' }} />
}

function LegendFooter() {
  const layers = (Object.keys(LAYER) as Layer[]).map(key => ({ key, label: LAYER[key].label }))

  return (
    <div
      style={{
        borderTop: '1px solid #E4E4E7',
        background: '#fff',
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
          color: '#A1A1AA',
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
            color: '#1A1A1A',
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
        <Background gap={24} size={1} color='#E8E8E8' />
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
          <p className="text-text-secondary">From signal to approved fix on Databricks, all governed by Unity Catalog. Drag nodes · scroll to zoom · export to PNG/SVG.</p>
        </div>
      </div>
      <div
        style={{
          background: '#FAFAFA',
          border: '1px solid #E4E4E7',
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
            borderTop: '1px solid #E4E4E7',
            background: '#fff',
            fontSize: 12,
            color: '#71717A',
          }}
        >
          In production, AI Gateway routes to the live OpenAI, Gemini and Anthropic APIs, or you land your GEO tracking vendor's data in Unity Catalog.
        </p>
        <LegendFooter />
      </div>
    </div>
  )
}
