"""Runs the full or targeted probe against all configured engines and persists answers and code-tagged claims."""
import argparse
import sys
import os
import uuid
from datetime import date, datetime, timezone

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from geologic import jobargs; jobargs.apply()

from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from geologic.config import settings as S
from geologic.clients import DvaRetriever, Embedder, FmapiChat
from geologic.datagen.reference import categories, subject_vocabulary
from geologic.probe.engine import EngineProxy
from geologic.probe.plan import is_current, run_health
from geologic.probe.runner import ANSWER_SCHEMA, CLAIM_SCHEMA, ProbeContext, run_probe

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="full")
ap.add_argument("--prompt-ids", default="")
ap.add_argument("--trigger", default="schedule")
ap.add_argument("--set-baseline", default="false")
a = ap.parse_args()

spark = SparkSession.builder.getOrCreate()
if spark.table(S.fq("probe_state")).count() == 0:
    spark.sql(f"INSERT INTO {S.fq('probe_state')} VALUES (1, 1, NULL, NULL)")
epoch = spark.table(S.fq("probe_state")).first()["current_epoch"]

prompts = [r.asDict() for r in spark.table(S.fq("prompts")).collect()]
if a.mode == "targeted":
    wanted = set(filter(None, a.prompt_ids.split(",")))
    prompts = [p for p in prompts if p["prompt_id"] in wanted]
facts = [r.asDict() for r in spark.table(S.fq("brand_facts")).collect()]      # valid_from/valid_to arrive as datetime.date
owned = frozenset(r["doc_id"] for r in spark.table(S.fq("web_corpus")).where("owner_class = 'Owned'").select("doc_id").collect())

w = WorkspaceClient()
chat = FmapiChat.from_workspace(w)
retriever = DvaRetriever(w, S.sources_index, Embedder.from_workspace(w, S.embedding_endpoint))
engines = [EngineProxy(fam, ep, retriever, chat) for fam, ep in S.engines.items()]
ctx = ProbeContext(chat, S.judge_endpoint, facts, categories(), subject_vocabulary(), owned, date.today())   # id: name (aliases)
run_id = f"run_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
started = datetime.now(timezone.utc)

answers, claims = run_probe(prompts, engines, ctx, run_id, epoch)

# Review Focus 4 (v2): if a reset bumped the epoch while we ran, drop these results
if not is_current(epoch, spark.table(S.fq("probe_state")).first()["current_epoch"]):
    print(f"epoch changed during run {run_id}; discarding {len(answers)} answers and {len(claims)} claims")
    sys.exit(0)


def write(rows, schema, table):
    cols = [c.split()[0] for c in schema.split(", ")]   # tuples in column order: no inference, NULL-only columns keep their type
    spark.createDataFrame([tuple(r[k] for k in cols) for r in rows], schema).write.mode("append").saveAsTable(S.fq(table))


health = run_health(answers, list(S.engines))
status = "ok" if health.healthy else "degraded"
if answers:
    write(answers, ANSWER_SCHEMA, "probe_responses")
if claims:
    write(claims, CLAIM_SCHEMA, "claims")
spark.createDataFrame(
    [(run_id, epoch, a.mode, a.trigger, [p["prompt_id"] for p in prompts], started, datetime.now(timezone.utc), status)],
    "run_id STRING, epoch INT, run_type STRING, trigger STRING, prompt_ids ARRAY<STRING>, "
    "started_at TIMESTAMP, finished_at TIMESTAMP, status STRING",
).write.mode("append").saveAsTable(S.fq("probe_runs"))
print(f"{run_id}: {len(answers)} answers, {health.not_ok} not ok, {len(claims)} claims")
print(f"by engine and status: {health.summary()}")
if not health.healthy:
    # A degraded run is kept for the audit trail but never becomes the baseline or the latest run.
    print(f"{run_id} degraded: {health.not_ok} of {health.total} answers not ok, engines with no ok answer: "
          f"{list(health.dead_engines)}; probe_state left unchanged")
    sys.exit(1)
baseline = f", baseline_run_id = '{run_id}'" if a.set_baseline == "true" else ""
spark.sql(f"UPDATE {S.fq('probe_state')} SET latest_run_id = '{run_id}'{baseline} WHERE id = 1")
