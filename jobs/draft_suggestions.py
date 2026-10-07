"""Drafts suggestions for open opportunities, finalizes tier and checks, writes Lakebase, auto-publishes T0.
Also runs the S4 red-team check so exclusions show enforcement at suggest and publish."""
import json
import os
import sys

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

import mlflow
from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from geologic.config import settings as S
from geologic.clients import FmapiChat
from geologic.agents.strategist import draft_suggestion, finalize, DraftError
from geologic.drafting import (plan_drafts, initial_state, suggestion_id, red_team_items, UPSERT_SUGGESTION,
                               CLEAR_EPOCH_SUGGESTIONS, LIVE_SUGGESTION_IDS)
from geologic.lakebase import from_env, apply_job_defaults
from geologic.publish_flow import publish, DeltaStore

spark = SparkSession.builder.getOrCreate()
rows = lambda q: [r.asDict(recursive=True) for r in spark.sql(q).collect()]
w = WorkspaceClient(); chat = FmapiChat.from_workspace(w)
apply_job_defaults(w); conn_factory = from_env(w)
menu, deals = rows(f"SELECT * FROM {S.fq('menu_items')}"), rows(f"SELECT * FROM {S.fq('deals')}")
rules = rows(f"SELECT * FROM {S.fq('exclusion_rules')}")
pages = {p["page_id"]: p for p in rows(f"SELECT * FROM {S.fq('site_pages')}")}
opps = rows(f"SELECT * FROM {S.fq('gold_opportunities')}")
quarantined = rows(f"SELECT signal_id, persona_id, menu_item_id, text, quarantine_rule_id FROM {S.fq('silver_signals')} WHERE quarantined")
mlflow.set_experiment("/Shared/geologic-drafting")

with conn_factory() as conn:
    epoch = conn.execute("SELECT epoch FROM demo_state WHERE id = 1").fetchone()[0]
    for q in quarantined:  # enforcement point 1: ingest
        conn.execute("INSERT INTO audit_events (actor, action, object_ref, exclusion_rule_id, enforcement_point) VALUES "
                     "('pipeline', 'quarantined', %s, %s, 'ingest') ON CONFLICT DO NOTHING", (q["signal_id"], q["quarantine_rule_id"]))
    store = DeltaStore(spark, conn, w)
    already_live = {r[0] for r in conn.execute(LIVE_SUGGESTION_IDS)}  # read before the clear below
    conn.execute(CLEAR_EPOCH_SUGGESTIONS, (epoch,))  # a re-draft fully replaces the queue (no stale or duplicate rows)
    for item in plan_drafts(opps) + red_team_items(quarantined):
        page = pages.get(item["page_id"])
        if page is None:
            continue
        with mlflow.start_span(name=f"draft {item['opp_id']} {item['asset_type']}") as span:
            try:
                draft = ({"asset_type": item["asset_type"], "diff_before": page["body"], "diff_after": item["forced_text"], "rationale": "red team"}
                         if item.get("forced_text") else draft_suggestion(item, page, menu, deals, chat, S.judge_endpoint))
            except DraftError as e:
                print("draft failed", item["opp_id"], e); continue
            final = finalize(draft, item, rules, menu)
            trace_id = span.trace_id
        sid = suggestion_id(item["opp_id"], item["asset_type"], epoch)
        state = initial_state(final["tier"])
        conn.execute(UPSERT_SUGGESTION,
                     (sid, epoch, item["opp_id"], item["rank"], final["title"] or item["opp_type"], final["asset_type"], item["page_id"],
                      final["diff_before"], final["diff_after"], final["rationale"], final["tier"], state, json.dumps(final["checks"]),
                      final["exclusion_rule_id"], item.get("persona_id"), item.get("prompt_ids") or [], trace_id))
        if final["tier"] == "BLOCKED":  # enforcement point 2: suggest; then prove publish refuses it (point 3)
            conn.execute("INSERT INTO audit_events (actor, action, object_ref, exclusion_rule_id, enforcement_point) VALUES "
                         "('brand_guardian', 'blocked', %s, %s, 'suggest') ON CONFLICT DO NOTHING", (sid, final["exclusion_rule_id"]))
            publish({**final, "suggestion_id": sid, "state": "approved", "epoch": epoch, "page_id": item["page_id"],
                     "persona_id": item.get("persona_id"), "prompt_ids": []}, store, rules, epoch, reprobe=False)
        elif final["tier"] == "T0" and sid not in already_live:  # reruns never re-apply a live T0 row (text may differ)
            publish({**final, "suggestion_id": sid, "state": state, "epoch": epoch, "page_id": item["page_id"],
                     "persona_id": item.get("persona_id"), "prompt_ids": []}, store, rules, epoch, reprobe=False)
    conn.commit()
    snap = conn.execute("SELECT * FROM suggestions WHERE epoch = %s", (epoch,)).fetchall()
    cols = [d.name for d in conn.execute("SELECT * FROM suggestions LIMIT 0").description]
store.sync_index()
_TYPES = {"epoch": "INT", "opp_rank": "INT", "publish_step": "INT", "publish_run_id": "BIGINT",
          "reviewed_at": "TIMESTAMP", "created_at": "TIMESTAMP"}
_schema = ", ".join(f"{c} {_TYPES.get(c, 'STRING')}" for c in cols)  # explicit: all-NULL columns cannot be inferred
spark.createDataFrame([tuple(json.dumps(v) if isinstance(v, (list, dict)) else v for v in r) for r in snap], _schema) \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(S.fq("suggestions_baseline"))
spark.sql(f"CREATE OR REPLACE TABLE {S.fq('site_pages_demo_start')} AS SELECT * FROM {S.fq('site_pages')}")
spark.sql(f"CREATE OR REPLACE TABLE {S.fq('web_corpus_demo_start')} AS SELECT * FROM {S.fq('web_corpus')}")
print(f"drafted {len(snap)} suggestions for epoch {epoch}")
