"""Deploys the GEOlogic read views from sql/views.sql, sql/insight_views.sql and sql/public_views.sql.

Each file lists its views in dependency order and the files run in the order below, so v_prompts and
v_latest_responses exist before the share views read them. {{schema}} renders to the target's
catalog.schema (task parameters --catalog/--schema, see geologic.jobargs).
"""
import os
import sys

# Serverless spark_python_task exec does not set __file__; cwd is script workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from geologic import jobargs; jobargs.apply()
from pyspark.sql import SparkSession
from geologic.config import settings as S
from geologic.sqlfiles import run_file

spark = SparkSession.builder.getOrCreate()
SQL_DIR = os.path.join(_src, "..", "sql")
for f in ("views.sql", "insight_views.sql", "public_views.sql"):
    n = run_file(os.path.join(SQL_DIR, f), spark.sql, catalog=S.catalog, schema=S.schema)
    print(f"  OK  {f}: {n} statements")
print("All views deployed.")
