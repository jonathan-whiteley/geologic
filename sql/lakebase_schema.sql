-- GEOlogic v3 workflow state (Lakebase database geologic_v3). Applied by scripts/apply_lakebase.py; idempotent.
CREATE TABLE IF NOT EXISTS fixes (
  fix_id TEXT PRIMARY KEY,
  epoch INT NOT NULL,
  issue_id TEXT NOT NULL,
  issue_type TEXT NOT NULL,
  issue_rank INT,
  title TEXT NOT NULL,
  lane TEXT NOT NULL,
  asset_type TEXT NOT NULL CHECK (asset_type IN ('jsonld', 'owned_patch', 'answer_page', 'moment_page', 'association',
                                                 'correction_email', 'community_reply')),
  tier TEXT NOT NULL CHECK (tier IN ('T0', 'T1', 'T2')),
  state TEXT NOT NULL CHECK (state IN ('pending_review', 'publishing', 'published', 'approved', 'rejected', 'blocked')),
  page_id TEXT,
  section_id TEXT,
  op TEXT CHECK (op IN ('insert', 'replace')),
  section_before TEXT,
  patch_text TEXT NOT NULL,
  sentences JSONB NOT NULL DEFAULT '[]',
  grounding_fact_ids TEXT[] NOT NULL DEFAULT '{}',
  checks JSONB NOT NULL DEFAULT '[]',
  rationale TEXT,
  recipient TEXT,
  persona_id TEXT,
  exclusion_rule_id TEXT,
  prompt_ids TEXT[] NOT NULL DEFAULT '{}',
  agent_trace_id TEXT,
  reviewer TEXT,
  reviewed_at TIMESTAMPTZ,
  publish_run_id BIGINT,
  publish_step INT NOT NULL DEFAULT 0,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- One row per (fix, target prompt, engine). Written when a re-ask finishes. Reset never deletes it, so a morning rehearsal
-- pre-bakes the Impact ledger and is the 90 s fallback.
CREATE TABLE IF NOT EXISTS fix_results (
  fix_id TEXT NOT NULL,
  prompt_id TEXT NOT NULL,
  engine TEXT NOT NULL,
  epoch INT NOT NULL,
  issue_id TEXT NOT NULL,
  title TEXT NOT NULL,
  tier TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  reviewer TEXT,
  approved_at TIMESTAMPTZ,
  measured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  elapsed_s DOUBLE PRECISION,
  prompt_text TEXT,
  status TEXT NOT NULL DEFAULT 'ok',
  before_mentioned BOOLEAN, after_mentioned BOOLEAN,
  before_owned_cited BOOLEAN, after_owned_cited BOOLEAN,
  before_owned_retrieved BOOLEAN, after_owned_retrieved BOOLEAN,
  before_position INT, after_position INT,
  before_claim_tags TEXT[] NOT NULL DEFAULT '{}', after_claim_tags TEXT[] NOT NULL DEFAULT '{}',
  before_answer TEXT, after_answer TEXT,
  before_cited TEXT[] NOT NULL DEFAULT '{}', after_cited TEXT[] NOT NULL DEFAULT '{}',
  PRIMARY KEY (fix_id, prompt_id, engine)
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
