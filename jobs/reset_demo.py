"""Reset job: restores pages, suggestions and the baseline probe under a new epoch."""
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
from geologic.lakebase import from_env, apply_job_defaults
from geologic.publish_flow import reset, DeltaResetStore

spark = SparkSession.builder.getOrCreate(); w = WorkspaceClient()
apply_job_defaults(w)
with from_env(w)() as conn:
    print("reset to epoch", reset(DeltaResetStore(spark, conn, w)))
