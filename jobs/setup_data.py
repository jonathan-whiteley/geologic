"""Creates the schema, volume, the appended tables (sql/tables.sql) and all reference tables. Safe to re-run:
reference tables are overwritten; tables.sql is CREATE TABLE IF NOT EXISTS, so appended data is kept."""
import sys
import os
from datetime import date, datetime, timezone

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from geologic import jobargs; jobargs.apply()

from pyspark.sql import SparkSession
from geologic.config import settings as S
from geologic.brands import brand_for_doc
from geologic.datagen import reference as r, corpus as c
from geologic.datagen.prompts_ext import prompt_candidates, monthly_volume
from geologic.exclusions import assert_persona_invariant
from geologic.sqlfiles import run_file

spark = SparkSession.builder.getOrCreate()
now = datetime.now(timezone.utc)
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {S.catalog}.{S.schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {S.fq('assets')}")
n = run_file(os.path.join(_src, "..", "sql", "tables.sql"), spark.sql, catalog=S.catalog, schema=S.schema)
print(f"  OK  tables.sql: {n} statements")

BRAND_FACTS = ("fact_id STRING, subject STRING, subject_name STRING, attribute STRING, value STRING, value_num DOUBLE, "
               "applies_to STRING, valid_from DATE, valid_to DATE, source_url STRING, page_id STRING")
WEB_CORPUS = ("doc_id STRING, source_type STRING, publisher STRING, title STRING, body STRING, published_at TIMESTAMP, "
              "is_official BOOLEAN, page_id STRING, last_updated DATE, domain STRING, url STRING, owner_class STRING")
PROMPTS = ("prompt_id STRING, prompt_text STRING, cluster STRING, priority STRING, branded BOOLEAN, base_volume INT, "
           "calendar_tags ARRAY<STRING>, source STRING, tracked_at TIMESTAMP")
PROMPT_SUGGESTIONS = ("suggestion_id STRING, prompt_text STRING, cluster STRING, base_volume INT, calendar_tags ARRAY<STRING>, "
                      "branded BOOLEAN, source STRING, status STRING, moment_id STRING")


def write(name, rows, schema=None, cdf=False):
    if schema:   # explicit schema: build tuples in column order (no inference, NULL-only columns keep their type)
        cols = [col.split()[0] for col in schema.split(", ")]
        df = spark.createDataFrame([tuple(row[k] for k in cols) for row in rows], schema)
    else:
        df = spark.createDataFrame(rows)
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(S.fq(name))
    if cdf:
        spark.sql(f"ALTER TABLE {S.fq(name)} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")


assert_persona_invariant(r.personas())
pages = r.site_pages()
write("menu_items", r.menu_items())
write("deals", r.deals())
write("brand_facts", r.brand_facts(), BRAND_FACTS)
write("site_pages", pages)
write("site_pages_baseline", pages)
corpus = c.web_corpus(pages)
write("web_corpus", corpus, WEB_CORPUS, cdf=True)
write("web_corpus_baseline", corpus, WEB_CORPUS)

tracked, cands = r.tracked_prompts(), prompt_candidates()
write("prompts", [{**p, "tracked_at": now} for p in tracked], PROMPTS)
write("prompt_suggestions", [{**p, "suggestion_id": p["prompt_id"], "source": "candidate", "status": "suggested", "moment_id": None}
                             for p in cands], PROMPT_SUGGESTIONS)
end = date.today().replace(day=1)
write("question_volume_monthly", [v for p in tracked + cands for v in monthly_volume(p, end)],
      "prompt_id STRING, month DATE, est_volume INT")

write("demand_calendar", r.demand_calendar(now))
write("personas", r.personas())
write("exclusion_rules", r.exclusion_rules())
write("menu_search", [{"item_id": m["item_id"], "search_text": f"{m['name']}. {', '.join(m['aliases'])}. {m['category']}. {m['visual']}"} for m in r.menu_items()], cdf=True)
write("doc_brand", [{"doc_id": d["doc_id"], "brand": brand_for_doc(d)} for d in corpus if brand_for_doc(d)], "doc_id STRING, brand STRING")
print("setup_data complete")
