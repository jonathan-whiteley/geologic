"""Reset job: new epoch, the demo-start fix queue, the baseline probe, pages, prompts and their vectors. fix_results stays."""
import os
import sys

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from geologic import jobargs; jobargs.apply()

from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from geologic.lakebase import apply_job_defaults, from_env
from geologic.publish_flow import DeltaResetStore, reset

spark = SparkSession.builder.getOrCreate(); w = WorkspaceClient()
apply_job_defaults(w)
with from_env(w)() as conn:
    print("reset to epoch", reset(DeltaResetStore(spark, conn, w)))
