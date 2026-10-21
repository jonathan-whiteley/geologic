-- Delta tables appended by probe, issue and pipeline jobs. setup_data runs this file first; every statement is idempotent.
CREATE TABLE IF NOT EXISTS {{schema}}.probe_state (id INT, current_epoch INT, baseline_run_id STRING, latest_run_id STRING);
CREATE TABLE IF NOT EXISTS {{schema}}.probe_runs (run_id STRING, epoch INT, run_type STRING, trigger STRING, prompt_ids ARRAY<STRING>,
  started_at TIMESTAMP, finished_at TIMESTAMP, status STRING);
CREATE TABLE IF NOT EXISTS {{schema}}.probe_responses (answer_id STRING, run_id STRING, epoch INT, prompt_id STRING, engine STRING,
  status STRING, answer STRING, retrieved_doc_ids ARRAY<STRING>, cited_doc_ids ARRAY<STRING>, cites_official BOOLEAN,
  lce_mentioned BOOLEAN, lce_rank INT, brands_mentioned ARRAY<STRING>, sentiment STRING, accuracy_score DOUBLE);
CREATE TABLE IF NOT EXISTS {{schema}}.claims (claim_id STRING, answer_id STRING, run_id STRING, epoch INT, prompt_id STRING,
  engine STRING, text STRING, subject STRING, attribute STRING, stated_value STRING, tag STRING, fact_id STRING, source_doc_id STRING);
CREATE TABLE IF NOT EXISTS {{schema}}.moments (moment_id STRING, kind STRING, title STRING, signal_ids ARRAY<STRING>, persona_id STRING,
  item_id STRING, reach BIGINT, velocity DOUBLE, image_match DOUBLE, questions ARRAY<STRING>, prompt_ids ARRAY<STRING>, detected_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS {{schema}}.issues (issue_id STRING, issue_type STRING, title STRING, cluster STRING, source_doc_id STRING,
  source_doc_ids ARRAY<STRING>, moment_id STRING, persona_id STRING, item_id STRING, subject STRING, attribute STRING,
  fact_id STRING, stated_fact_id STRING, stated_value STRING, prompt_ids ARRAY<STRING>, engines ARRAY<STRING>, missed_answers INT, action_lane STRING,
  planned ARRAY<STRUCT<asset_type: STRING, lane: STRING, page_id: STRING, section_id: STRING, op: STRING, recipient: STRING>>,
  claim_keys ARRAY<STRING>, score DOUBLE, rank INT, built_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS {{schema}}.answer_share_weekly (week_start DATE, brand STRING, answer_share DOUBLE);
CREATE TABLE IF NOT EXISTS {{schema}}.bronze_signals (signal_id STRING, source_type STRING, payload STRING, image_uri STRING,
  ingested_at BIGINT, producer STRING);
CREATE TABLE IF NOT EXISTS {{schema}}.image_descriptions (signal_id STRING, description STRING, matched_item_id STRING,
  match_score DOUBLE, described_at TIMESTAMP);
