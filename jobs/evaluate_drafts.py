"""MLflow GenAI evaluation of Content Strategist drafts (current epoch, red-team items excluded)."""
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
from mlflow.genai.scorers import Guidelines, scorer
from databricks.sdk import WorkspaceClient
from geologic.datagen.reference import menu_items
from geologic.jsonld import validate
from geologic.lakebase import from_env, apply_job_defaults

MENU = menu_items()
w = WorkspaceClient(); apply_job_defaults(w)
with from_env(w)() as c:
    rows = c.execute("SELECT asset_type, diff_before, diff_after FROM suggestions WHERE tier <> 'BLOCKED' "
                     "AND opp_id NOT LIKE 'redteam_%' AND epoch = (SELECT epoch FROM demo_state WHERE id = 1)").fetchall()
data = [{"inputs": {"asset_type": a, "before": b or ""}, "outputs": d} for a, b, d in rows]
print(f"evaluating {len(data)} drafts")


@scorer
def valid_jsonld(inputs, outputs):
    return inputs["asset_type"] != "jsonld" or validate(outputs, MENU) == []


mlflow.set_experiment("/Shared/geologic-drafting")
res = mlflow.genai.evaluate(data=data, scorers=[
    Guidelines(name="brand_voice", guidelines="Friendly, plain language, short sentences, no hype words."),
    Guidelines(name="no_competitors", guidelines="Must not mention Domino's, Pizza Hut, Papa Johns, or any other pizza chain."),
    Guidelines(name="no_people_claims", guidelines="Must not claim an athlete endorses a product unless the text is an image caption for an approved LCE endorser."),
    valid_jsonld,
])
print(json.dumps(res.metrics, indent=2, default=str))
