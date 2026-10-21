"""Drafts one fix per planned asset of every issue (Task 6 drafter, code verifier, code tiers), writes Lakebase `fixes`,
records the three enforcement points for each quarantined post, then snapshots the demo-start state Reset restores."""
import json
import os
import sys
from collections import Counter
from datetime import date

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from geologic import jobargs; jobargs.apply()

import mlflow
from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from geologic.config import settings as S
from geologic.clients import FmapiChat
from geologic.datagen.reference import SUBJECTS
from geologic.drafting import BLOCKING_CHECKS, draft_fix, finalize_fix, unsupported_claims
from geologic.exclusions import find_exclusion
from geologic.fixes import CLEAR_EPOCH_FIXES, UPSERT_FIX, build_requests, fix_values
from geologic.jsonld import build_for_page
from geologic.lakebase import apply_job_defaults, from_env
from geologic.tiering import assign_tier

spark = SparkSession.builder.getOrCreate()
rows = lambda q: [r.asDict(recursive=True) for r in spark.sql(q).collect()]
w = WorkspaceClient(); chat = FmapiChat.from_workspace(w); apply_job_defaults(w)
today = date.today(); mlflow.set_experiment(S.experiment)
facts = rows(f"SELECT * FROM {S.fq('brand_facts')}"); rules = rows(f"SELECT * FROM {S.fq('exclusion_rules')}")
pages = {p["page_id"]: p for p in rows(f"SELECT * FROM {S.fq('site_pages')}")}
sources = rows(f"SELECT * FROM {S.fq('web_corpus')}"); prompts = rows(f"SELECT * FROM {S.fq('prompts')}")
claims = rows(f"SELECT * FROM {S.fq('v_latest_claims')}"); people = rows(f"SELECT * FROM {S.fq('personas')}")
issues = rows(f"SELECT * FROM {S.fq('issues')} ORDER BY rank")
quarantined = rows(f"SELECT signal_id, text, persona_id, quarantine_rule_id FROM {S.fq('silver_signals')} WHERE quarantined")
menu = rows(f"SELECT name, aliases FROM {S.fq('menu_items')}")
# Names plus aliases: an alias ("Hot-N-Ready") makes a sentence factual for the verifier, like the full name does.
item_names = sorted({n for m in menu for n in [m["name"], *(m.get("aliases") or [])] if n})
# Persona rows, not names: creators match on full name and handle only, and the association exemption keys on persona_id.
persona_rows = people
judge_names = tuple(item_names) + tuple(p["display_name"] for p in people)
judge = lambda text, g: unsupported_claims(text, g, chat, S.judge_endpoint, SUBJECTS, names=judge_names)
AUDIT = ("INSERT INTO audit_events (actor, action, object_ref, exclusion_rule_id, enforcement_point) VALUES (%s,%s,%s,%s,%s) "
         "ON CONFLICT DO NOTHING")


def finalize(draft, req, use_judge):
    return finalize_fix(draft, req, facts, rules, today, item_names=item_names, persona_names=persona_rows,
                        judge=judge if use_judge else None)


def blocked(draft, req, reason):
    """A draft the verifier could not read (jsonld.validate raises on non-object JSON): recorded blocked, never a crash."""
    return {"patch": draft["patch"], "sentences": draft.get("sentences") or [], "rationale": draft.get("rationale") or "",
            "tier": assign_tier(req["asset_type"], names_person=False, checks_ok=False), "state": "blocked",
            "checks": [{"key": "schema", "ok": False, "label": reason}], "grounding_fact_ids": [], "exclusion_rule_id": None}


failed = []
with from_env(w)() as conn:
    epoch = conn.execute("SELECT epoch FROM demo_state WHERE id = 1").fetchone()[0]
    for q in quarantined:   # three enforcement points for the excluded repost; it never becomes a fix row
        conn.execute(AUDIT, ("pipeline", "quarantined", q["signal_id"], q["quarantine_rule_id"], "ingest"))
        conn.execute(AUDIT, ("brand_guardian", "blocked", q["signal_id"], find_exclusion(q["text"], q.get("persona_id"), [], rules),
                             "suggest"))
        conn.execute(AUDIT, ("publish_job", "blocked", q["signal_id"], find_exclusion(q["text"], None, [], rules), "publish"))
    conn.execute(CLEAR_EPOCH_FIXES, (epoch,))
    for issue in issues:
        for req in build_requests(issue, pages=pages, sources=sources, facts=facts, prompts=prompts, claims=claims,
                                  personas=people, today=today):
            with mlflow.start_span(name=f"draft {req['fix_id']} {req['asset_type']}") as span:
                try:
                    if req["asset_type"] == "jsonld":
                        draft = build_for_page(pages[req["page_id"]], facts, today)
                        try:
                            final = finalize(draft, req, use_judge=False)
                        except AttributeError as e:
                            final = blocked(draft, req, f"JSON-LD could not be read: {e}")
                    else:
                        draft = draft_fix(req, chat, S.judge_endpoint)
                        final = finalize(draft, req, use_judge=True)
                        bad = [c["label"] for c in final["checks"] if c["key"] in BLOCKING_CHECKS and not c["ok"]]
                        if bad:   # one redraft with the failed checks as feedback; keep the result with fewer failures
                            d2 = draft_fix(req, chat, S.judge_endpoint, feedback=bad)
                            f2 = finalize(d2, req, use_judge=True)
                            if sum(c["key"] in BLOCKING_CHECKS and not c["ok"] for c in f2["checks"]) < len(bad):
                                final = f2
                except Exception as e:
                    print("draft failed", req["fix_id"], repr(e)); failed.append(req["fix_id"]); continue
                conn.execute(UPSERT_FIX, fix_values(req, final, epoch, span.trace_id))
    conn.commit()
    if failed:
        print(f"FAILED drafts {failed}; demo-start snapshots NOT written.")
        sys.exit(1)
    cur = conn.execute("SELECT * FROM fixes WHERE epoch = %s", (epoch,))
    cols = [d.name for d in cur.description]; snap = cur.fetchall()

_TYPES = {"epoch": "INT", "issue_rank": "INT", "publish_step": "INT", "publish_run_id": "BIGINT",
          "reviewed_at": "TIMESTAMP", "created_at": "TIMESTAMP"}
_schema = ", ".join(f"{c} {_TYPES.get(c, 'STRING')}" for c in cols)   # explicit: all-NULL columns cannot be inferred
spark.createDataFrame([tuple(json.dumps(v) if isinstance(v, (list, dict)) else v for v in r) for r in snap], _schema) \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(S.fq("fixes_baseline"))
for t in ("site_pages", "web_corpus", "prompts", "prompt_suggestions"):
    spark.sql(f"CREATE OR REPLACE TABLE {S.fq(t + '_demo_start')} AS SELECT * FROM {S.fq(t)}")
tiers = Counter((r[cols.index("tier")], r[cols.index("state")]) for r in snap)
print(f"drafted {len(snap)} fixes for epoch {epoch}: {dict(sorted(tiers.items()))}")
