"""Asserts seeded truths S1-S7 against live Delta and Lakebase state (harness.check)."""
import os
import sys

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from geologic.config import settings as S
from geologic.harness import check
from geologic.lakebase import from_env, apply_job_defaults

spark = SparkSession.builder.getOrCreate()
q = lambda sql: [r.asDict(recursive=True) for r in spark.sql(sql).collect()]
w = WorkspaceClient(); apply_job_defaults(w)
opps = q(f"SELECT * FROM {S.fq('gold_opportunities')}")
opp_type = {o["opp_id"]: o["opp_type"] for o in opps}
with from_env(w)() as c:
    rows = c.execute("SELECT opp_id, page_id, tier FROM suggestions WHERE epoch = (SELECT epoch FROM demo_state WHERE id = 1)").fetchall()
    audits = c.execute("SELECT exclusion_rule_id, enforcement_point FROM audit_events").fetchall()
# Red-team suggestions use opp_ids that are not in gold, so their opp_type is None and never matches a truth.
state = {
    "opps": opps,
    "signals": q(f"SELECT s.signal_id, b.producer, s.persona_id, s.quarantined, s.quarantine_rule_id "
                 f"FROM {S.fq('silver_signals')} s JOIN {S.fq('bronze_signals')} b USING (signal_id)"),
    "suggestions": [{"opp_type": opp_type.get(o), "page_id": p, "tier": t} for o, p, t in rows],
    "audits": [{"exclusion_rule_id": r, "enforcement_point": p} for r, p in audits],
    "public_signal_ids": {r["signal_id"] for r in q(f"SELECT signal_id FROM {S.fq('v_public_signals')}")},
}
failures = check(state)
for x in failures:
    print("FAIL", x)
if failures:
    raise SystemExit(1)
print("answer key: all seeded truths pass")
