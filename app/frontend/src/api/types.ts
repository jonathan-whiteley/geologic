// v3 contract (Tasks 9, 11, 12, 13). Field names match the backend responses exactly.

// Measure (Task 11)
export type OwnerClass = 'Owned' | 'Competitor' | 'Editorial' | 'Community' | 'Reference'
export type Tag = 'Correct' | 'Wrong' | 'Outdated' | 'Unverifiable'
export type Kpis = { answer_share: number | null; mention_rate: number | null; owned_citation_share: number | null; fact_accuracy: number | null;
  wrong_claims: number; outdated_claims: number; avg_rank: number | null; answers: number; engines: number; tracked_prompts: number; last_run_at: string | null }
export type BrandRow = { brand: string; logo: string; answer_share: number | null; avg_position: number | null; citation_share: number | null }
export type SourceType = { owner_class: OwnerClass; citations: number; share: number }
export type Domain = { domain: string; owner_class: OwnerClass; citations: number; prompts: number }
export type Gateway = { engines: { engine: string; answers: number }[]; answers: number; logged: number | null }
export type HeatCell = { cluster: string; engine: string; answer_share: number }
export type ModelSummary = { kpis: Kpis; brands: BrandRow[]; heatmap: HeatCell[]; source_types: SourceType[]; top_domains: Domain[]; gateway: Gateway }
export type PromptRow = { prompt_id: string; prompt_text: string; cluster: string; priority: 'Gold' | 'Silver' | 'Bronze'; branded: boolean;
  est_monthly_searches: number | null; engines_naming: number; engines_owned_cited: number; engines_answered: number; answer_share: number | null;
  wrong_claims: number; outdated_claims: number; moment_id: string | null; moment_title: string | null }
export type CitedDoc = { doc_id: string; domain: string; owner_class: OwnerClass; title: string; url: string; last_updated: string | null }
export type ClaimT = { claim_id: string; text: string | null; subject: string; attribute: string; stated_value: string | null; tag: Tag;
  fact_id: string | null; source_doc_id: string | null; issue_id: string | null }
export type AnswerT = { engine: string; status: string; answer: string | null; lce_mentioned: boolean | null; lce_rank: number | null;
  cited: CitedDoc[]; owned_retrieved: boolean; claims: ClaimT[] }
export type PromptDetail = PromptRow & { answers: AnswerT[] }
export type PromptSuggestion = { suggestion_id: string; prompt_text: string; cluster: string | null; source: 'candidate' | 'moment' | 'search'; moment_id: string | null }
export type SearchResp = { query: string; threshold: number; match: { prompt_id: string; prompt_text: string; score: number } | null;
  nearest: { id: string; prompt_text: string; kind: 'tracked' | 'suggested'; score: number } | null; scorecard: AnswerT[] | null }
export type TrackResp = { prompt_id: string; prompt_text: string; scorecard: AnswerT[]; elapsed_s: number }

// Fix (Task 12)
export type IssueType = 'wrong' | 'outdated' | 'missing_us' | 'no_answer_page' | 'moment_gap'
export type FixLite = { fix_id: string; tier: 'T0' | 'T1' | 'T2'; asset_type: string; state: string }
export type IssueRow = { issue_id: string; rank: number; issue_type: IssueType; title: string; cluster: string; action_lane: string;
  prompt_ids: string[]; missed_answers: number; moment_id: string | null; fixes: FixLite[] }
export type Check = { key: string; ok: boolean; label: string }
export type Sentence = { text: string; fact_ids: string[]; kind: 'fact' | 'copy' }
export type Fix = FixLite & { issue_id: string; title: string; lane: string; page_id: string | null; section_id: string | null; op: 'insert' | 'replace' | null;
  section_before: string | null; patch_text: string; sentences: Sentence[]; grounding_fact_ids: string[]; checks: Check[]; rationale: string | null;
  recipient: string | null; publish_step: number; error: string | null; reviewer: string | null }
export type FactRow = { fact_id: string; subject_name: string; attribute: string; value: string; valid_from: string; valid_to: string | null; current: boolean }
export type Passage = { doc_id: string; domain: string; owner_class: OwnerClass; last_updated: string | null; title: string; url: string; excerpt: string }
export type MomentT = { moment_id: string; title: string; kind: 'persona' | 'trend'; author: string | null; persona_name: string | null; reach: number | null;
  velocity: number | null; item_name: string; image_url: string | null; image_credit: string | null; image_match: number | null }
export type IssueDetailT = { issue: IssueRow & { source_doc_id: string | null; subject: string | null; attribute: string | null; stated_value: string | null };
  said: { claims: { engine: string; prompt_id: string; prompt_text: string; text: string | null; stated_value: string | null; tag: Tag }[];
          passage: Passage | null; memory: boolean; moment: MomentT | null;
          scorecards: { prompt_id: string; prompt_text: string; answers: AnswerT[] }[] };
  truth: { facts: FactRow[]; uc_table: string }; fixes: Fix[] }
export type LedgerSide = { mentioned: number; owned_cited: number; tag: Tag | null }
export type LedgerEntry = { fix_id: string; title: string; tier: string; asset_type: string; reviewer: string | null; approved_at: string | null;
  measured_at: string; epoch: number; rehearsal: boolean; engines_answered: number; engines_total: number; elapsed_s: number | null;
  prompts: { prompt_id: string; prompt_text: string | null; before: LedgerSide; after: LedgerSide;
             answers: { engine: string; status: string; before_answer: string | null; after_answer: string | null; before_cited: string[]; after_cited: string[] }[] }[] }
export type FixStatus = { state: string; publish_step: number; step_labels: string[]; error: string | null; elapsed_s: number | null;
  entry: LedgerEntry | null; fallback: { rehearsed_at: string; entry: LedgerEntry } | null }
export type FixSummary = { tiers: { T0: { ready: number }; T1: { to_review: number }; T2: { to_review: number } }; quarantined: number; review_mode: boolean }
export type Quarantine = { count: number; rule_id: string | null; reason: string | null; points: { enforcement_point: 'ingest' | 'suggest' | 'publish'; occurred_at: string }[] }

// v2 Impact shapes, still used by the v2 Impact page until Task 13 replaces it.
export type Impact = { weekly: { week_start: string; brand: string; answer_share: number }[]; health: { t0_auto: number; t1_approved_no_edit_pct: number | null; t2_reviews: number; blocked: number }; proof: Proof | null }
export type Proof = { suggestion_id: string; title: string; engine: string; before_answer: string | null; after_answer: string | null; before_cited: string[]; after_cited: string[]; share_before: number | null; share_after: number | null; accuracy_before: number | null; accuracy_after: number | null; reviewer: string | null; saved_at: string; prompt_text?: string | null }

// Genie
export type GenieColumn = { name: string; type: string }
export type GenieMessage = { status: string; partial: boolean; text: string; sql: string; description: string; columns: GenieColumn[]; rows: (string | null)[][]; row_count: number; truncated: boolean; suggested_questions: string[]; source: string | null; error: string | null }
