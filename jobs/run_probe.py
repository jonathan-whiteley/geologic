"""Runs the full or targeted probe against all configured engines and persists results."""
import argparse
import sys
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient
from geologic.config import settings as S
from geologic.clients import FmapiChat, VsRetriever
from geologic.probe.engine import EngineProxy
from geologic.probe.runner import run_probe
from geologic.probe.plan import chunk, is_current

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="full")
ap.add_argument("--prompt-ids", default="")
ap.add_argument("--trigger", default="schedule")
ap.add_argument("--set-baseline", default="false")
a = ap.parse_args()

spark = SparkSession.builder.getOrCreate()
spark.sql(f"CREATE TABLE IF NOT EXISTS {S.fq('probe_state')} "
          "(id INT, current_epoch INT, baseline_run_id STRING, latest_run_id STRING)")
if spark.table(S.fq("probe_state")).count() == 0:
    spark.sql(f"INSERT INTO {S.fq('probe_state')} VALUES (1, 1, NULL, NULL)")
epoch = spark.table(S.fq("probe_state")).first()["current_epoch"]

prompts = [r.asDict() for r in spark.table(S.fq("prompt_bank")).collect()]
# 12b Step 5: probe tracked candidate prompts too
if spark.catalog.tableExists(S.fq("tracked_prompts")):
    prompts += [r.asDict() for r in spark.sql(
        f"SELECT c.* FROM {S.fq('prompt_candidates')} c "
        f"JOIN (SELECT DISTINCT prompt_id FROM {S.fq('tracked_prompts')}) t USING (prompt_id)").collect()]

if a.mode == "targeted":
    wanted = set(filter(None, a.prompt_ids.split(",")))
    prompts = [p for p in prompts if p["prompt_id"] in wanted]
menu = [r.asDict() for r in spark.table(S.fq("menu_items")).collect()]
deals = [r.asDict() for r in spark.table(S.fq("deals")).collect()]
official = {r["doc_id"] for r in spark.table(S.fq("web_corpus")).where("is_official").select("doc_id").collect()}

w = WorkspaceClient()
chat = FmapiChat.from_workspace(w)
index = VectorSearchClient(disable_notice=True).get_index(S.vs_endpoint, S.corpus_index)
engines = [EngineProxy(fam, ep, VsRetriever(index), chat) for fam, ep in S.engines.items()]
run_id = f"run_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
started = datetime.now(timezone.utc)

with ThreadPoolExecutor(max_workers=4) as pool:
    parts = pool.map(
        lambda ps: run_probe(ps, engines, chat, S.judge_endpoint, menu, deals, run_id, epoch, official),
        chunk(prompts, 4),
    )
rows = [r for part in parts for r in part]

# Review Focus 4: if a reset bumped the epoch while we ran, drop these results
if not is_current(epoch, spark.table(S.fq("probe_state")).first()["current_epoch"]):
    print(f"epoch changed during run {run_id}; discarding {len(rows)} rows")
    sys.exit(0)

schema = (
    "run_id STRING, epoch INT, prompt_id STRING, engine STRING, status STRING, answer STRING, "
    "cited_doc_ids ARRAY<STRING>, cites_official BOOLEAN, lce_mentioned BOOLEAN, lce_rank INT, "
    "brands_mentioned ARRAY<STRING>, sentiment STRING, "
    "claims ARRAY<STRUCT<item: STRING, price: STRING, verdict: STRING>>, accuracy_score DOUBLE"
)
for r in rows:
    r["claims"] = [{"item": str(c.get("item")), "price": str(c.get("price")), "verdict": c["verdict"]}
                   for c in r["claims"]]
spark.createDataFrame(rows, schema).write.mode("append").saveAsTable(S.fq("probe_responses"))
spark.createDataFrame(
    [(run_id, epoch, a.mode, a.trigger, [p["prompt_id"] for p in prompts], started, datetime.now(timezone.utc), "ok")],
    "run_id STRING, epoch INT, run_type STRING, trigger STRING, prompt_ids ARRAY<STRING>, "
    "started_at TIMESTAMP, finished_at TIMESTAMP, status STRING",
).write.mode("append").saveAsTable(S.fq("probe_runs"))
baseline = f", baseline_run_id = '{run_id}'" if a.set_baseline == "true" else ""
spark.sql(f"UPDATE {S.fq('probe_state')} SET latest_run_id = '{run_id}'{baseline} WHERE id = 1")
errors = sum(r["status"] != "ok" for r in rows)
print(f"{run_id}: {len(rows)} responses, {errors} not ok")
