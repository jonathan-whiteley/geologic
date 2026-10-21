"""Builds moments (each linked to the prompts it creates) and the v3 issue queue. Safe to re-run: moments and issues
are overwritten, new prompt suggestions are merged (existing ones are never touched).

1. Moments from silver_signals (quarantined signals never become moments). For each, the judge model writes 1 or 2
   customer questions from the post text; each links to the best tracked prompt in the top 5 of prompt_idx at the match
   threshold (cosine), else the best other suggestion at it (never its own), otherwise it becomes a new prompt suggestion
   (source moment), upserted into prompt_idx.
2. Issues from the latest ok answers, their claims, the tracked prompts, sources, owned pages, brand facts and the
   moments (geologic.issues). No prompt, no issue.
"""
import os
import sys
from collections import Counter
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
from geologic.clients import Embedder, FmapiChat, PromptIndex
from geologic.datagen.reference import is_branded
from geologic.issues import build_issues
from geologic.moments import build_moments, fallback_question, link_questions, parse_questions, question_messages
from geologic import vectors as V

spark = SparkSession.builder.getOrCreate()
rows = lambda q: [r.asDict(recursive=True) for r in spark.sql(q).collect()]
w = WorkspaceClient()
chat = FmapiChat.from_workspace(w)
emb = Embedder.from_workspace(w, S.embedding_endpoint)
index = PromptIndex(w, S.prompt_index, emb)
now = datetime.now(timezone.utc)


def table_schema(name):
    return spark.table(S.fq(name)).schema   # the DDL from sql/tables.sql (setup_data) or setup_data's explicit schema


def overwrite(name, records):
    schema = table_schema(name)
    data = [tuple(r.get(f.name) for f in schema.fields) for r in records]
    spark.createDataFrame(data, schema).write.mode("overwrite").saveAsTable(S.fq(name))


menu = rows(f"SELECT * FROM {S.fq('menu_items')}")
people = rows(f"SELECT * FROM {S.fq('personas')}")
names = {m["item_id"]: m["name"] for m in menu}
pnames = {p["persona_id"]: p["display_name"] for p in people}
moments = build_moments(rows(f"SELECT * FROM {S.fq('silver_signals')}"), people, menu)

hits = {}


def best(text, k=5):   # nearest tracked prompts and suggestions (cosine), cached: one embedding and one query per question
    if text not in hits:
        hits[text] = index.nearest(text, k) or []
    return hits[text]


new_sugg = {}
for m in moments:
    qs = []
    for attempt in range(2):
        try:
            qs = parse_questions(chat.complete(S.judge_endpoint, question_messages(m, names[m["item_id"]], pnames.get(m["persona_id"])),
                                               max_tokens=200, usage_context={"app": S.usage_app, "role": "moments"}))
        except Exception as e:   # a transient endpoint error falls back to the template question, never kills the build
            print(f"moment {m['moment_id']}: question attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:200]}")
        if qs:
            break
    qs = qs or [fallback_question(names[m["item_id"]])]
    ids, new = link_questions(qs, best, S.match_threshold)
    m["questions"], m["prompt_ids"], m["detected_at"] = qs, ids, now
    for sid, text in new:
        new_sugg.setdefault(sid, {"suggestion_id": sid, "prompt_text": text, "cluster": (best(text)[:1] or [{}])[0].get("cluster") or "product",
                                  "base_volume": None, "calendar_tags": [], "branded": is_branded(text), "source": "moment",
                                  "status": "suggested", "moment_id": m["moment_id"]})

overwrite("moments", moments)
if new_sugg:
    schema = table_schema("prompt_suggestions")
    df = spark.createDataFrame([tuple(s.get(f.name) for f in schema.fields) for s in new_sugg.values()], schema)
    df.createOrReplaceTempView("new_suggestions")
    spark.sql(f"MERGE INTO {S.fq('prompt_suggestions')} t USING new_suggestions s ON t.suggestion_id = s.suggestion_id "
              "WHEN NOT MATCHED THEN INSERT *")
    idx_rows = V.prompt_rows([], list(new_sugg.values()), emb.embed)
    V.upsert(w, S.prompt_index, idx_rows)
    print(f"prompt suggestions from moments: {len(new_sugg)} merged, {len(idx_rows)} upserted into {S.prompt_index}")

prompts = rows(f"SELECT prompt_id, prompt_text, cluster, priority, branded FROM {S.fq('prompts')}")
issues = build_issues(
    answers=rows(f"SELECT * FROM {S.fq('v_latest_responses')} WHERE status = 'ok'"),
    claims=rows(f"SELECT * FROM {S.fq('v_latest_claims')}"),
    prompts=prompts,
    sources=rows(f"SELECT doc_id, owner_class, domain, page_id, title, body FROM {S.fq('web_corpus')}"),
    pages=rows(f"SELECT page_id, primary_subject, updated_at FROM {S.fq('site_pages')}"),
    facts=rows(f"SELECT * FROM {S.fq('brand_facts')}"),
    moments=moments, personas=people, today=date.today())

planned_fields = table_schema("issues")["planned"].dataType.elementType.fieldNames()
for i in issues:
    i["planned"] = [tuple(f[k] for k in planned_fields) for f in i["planned"]]
    i["built_at"] = now
overwrite("issues", issues)

tracked = {p["prompt_id"] for p in prompts}
print(f"issues by type: {dict(Counter(i['issue_type'] for i in issues))}")
print(f"moments: {len(moments)}, linked to tracked prompts: {sum(1 for m in moments if set(m['prompt_ids']) & tracked)}")
for m in moments:
    print(f"  {m['moment_id']} {m['title']}: questions {m['questions']} -> {m['prompt_ids']}")
for i in issues:
    print(f"  #{i['rank']} {i['issue_type']:<15} {i['score']:.2f} {i['title']} {i['prompt_ids']}")
