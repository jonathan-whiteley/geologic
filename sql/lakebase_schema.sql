CREATE TABLE IF NOT EXISTS suggestions (
  suggestion_id TEXT PRIMARY KEY,
  epoch INT NOT NULL,
  opp_id TEXT NOT NULL,
  opp_rank INT,
  title TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  page_id TEXT NOT NULL,
  diff_before TEXT,
  diff_after TEXT NOT NULL,
  rationale TEXT,
  tier TEXT NOT NULL CHECK (tier IN ('T0', 'T1', 'T2', 'BLOCKED')),
  state TEXT NOT NULL CHECK (state IN ('drafted', 'auto_published', 'pending_review', 'approved', 'publishing', 'rejected', 'published', 'blocked', 'rolled_back')),
  checks JSONB NOT NULL DEFAULT '[]',
  exclusion_rule_id TEXT,
  persona_id TEXT,
  prompt_ids TEXT[] NOT NULL DEFAULT '{}',
  agent_trace_id TEXT,
  reviewer TEXT,
  reviewed_at TIMESTAMPTZ,
  publish_run_id BIGINT,
  publish_step INT NOT NULL DEFAULT 0,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id BIGSERIAL PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  object_ref TEXT,
  exclusion_rule_id TEXT,
  enforcement_point TEXT CHECK (enforcement_point IN ('ingest', 'suggest', 'publish') OR enforcement_point IS NULL),
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (action, object_ref, enforcement_point)
);
CREATE TABLE IF NOT EXISTS cms_page_versions (
  page_id TEXT NOT NULL,
  version INT NOT NULL,
  body TEXT,
  jsonld TEXT,
  published_by TEXT NOT NULL,
  published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (page_id, version)
);
CREATE TABLE IF NOT EXISTS demo_state (id INT PRIMARY KEY CHECK (id = 1), epoch INT NOT NULL);
INSERT INTO demo_state VALUES (1, 1) ON CONFLICT DO NOTHING;

-- Proof of a published fix. Written by the app when a publish completes; Reset does not clear it,
-- so a rehearsal pre-bakes the Prove tab.
CREATE TABLE IF NOT EXISTS proof_results (
  suggestion_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  engine TEXT NOT NULL DEFAULT 'Claude',
  before_answer TEXT,
  after_answer TEXT,
  before_cited TEXT[] NOT NULL DEFAULT '{}',
  after_cited TEXT[] NOT NULL DEFAULT '{}',
  share_before DOUBLE PRECISION,
  share_after DOUBLE PRECISION,
  accuracy_before DOUBLE PRECISION,
  accuracy_after DOUBLE PRECISION,
  reviewer TEXT,
  saved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
