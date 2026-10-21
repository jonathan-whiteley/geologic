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

// v2 Fix and Impact shapes, still used by the v2 Fix and Impact pages until Tasks 12 and 13 replace them.
export type Opportunity = { opp_id: string; rank: number; opp_type: string; title: string; reasoning: string; assets: string[]; expected_lift_low: number; expected_lift_high: number; question_volume: number; window_name: string | null; window_expires_at: string | null; status: 'open' | 'monitor'; persona_id: string | null }
export type Check = { ok: boolean; label: string }
export type Suggestion = { suggestion_id: string; opp_id: string; opp_rank: number; title: string; asset_type: string; page_id: string; diff_before: string | null; diff_after: string; rationale: string; tier: 'T0' | 'T1' | 'T2'; state: string; checks: Check[]; persona_id: string | null; agent_trace_id: string | null; publish_step: number; error: string | null }
export type PublishStatus = { state: string; publish_step: number; error: string | null; before?: { answer: string; cited: string[] }; after?: { answer: string; cited: string[] }; engine?: string; prompt_id?: string; prompt_text?: string | null; summary?: { share_before: number | null; share_after: number | null; accuracy_before: number | null; accuracy_after: number | null } | null }
export type Impact = { weekly: { week_start: string; brand: string; answer_share: number }[]; health: { t0_auto: number; t1_approved_no_edit_pct: number | null; t2_reviews: number; blocked: number }; proof: Proof | null }
export type Evidence = { opp_id: string; page_id: string | null; wrong_claims: { engine: string; item: string; price: string }[]; truth: { name: string; price: number } | null; cited_instead: { publisher: string; source_type: string; citations: number }[]; signal: { signal_id: string; author: string; text: string; persona_name: string | null; menu_item_name: string | null; image_url: string | null; image_credit: string | null } | null; live_page: { version: number; published_by: string; published_at: string } | null }
export type Proof = { suggestion_id: string; title: string; engine: string; before_answer: string | null; after_answer: string | null; before_cited: string[]; after_cited: string[]; share_before: number | null; share_after: number | null; accuracy_before: number | null; accuracy_after: number | null; reviewer: string | null; saved_at: string; prompt_text?: string | null }

// Genie
export type GenieColumn = { name: string; type: string }
export type GenieMessage = { status: string; partial: boolean; text: string; sql: string; description: string; columns: GenieColumn[]; rows: (string | null)[][]; row_count: number; truncated: boolean; suggested_questions: string[]; source: string | null; error: string | null }
