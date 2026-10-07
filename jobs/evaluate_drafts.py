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
    Guidelines(name="brand_voice", guidelines=(
        "The text is a Little Caesars web page draft. It passes if it uses friendly, plain language a guest understands. "
        "Little Caesars brand phrases and plain value statements (for example 'great value' or 'Hot-N-Ready convenience') are on-brand "
        "and pass. Little Caesars product names (ExtraMostBestest, Deep!Deep! Dish, Crazy Bread, and so on) are proper names, never hype, "
        "and plain food descriptions such as 'loaded with pepperoni' are fine. "
        "FAQ structure and JSON-LD structure are acceptable formatting. It fails only for superlative or exaggerated hype "
        "(for example 'best ever', 'unbeatable', 'mind-blowing', 'revolutionary', excessive exclamation points) or for sentences "
        "so long they are hard to follow (roughly over 35 words).")),
    Guidelines(name="no_competitors", guidelines=(
        "The text is Little Caesars' own page content, so mentioning Little Caesars and its product names (Hot-N-Ready, Crazy Bread, "
        "ExtraMostBestest, Deep!Deep! Dish, Slices-N-Stix, and so on) is expected and passes. It fails only if it names or clearly "
        "refers to a competing chain (Domino's, Pizza Hut, Papa Johns, or any other non-Little Caesars brand).")),
    Guidelines(name="no_people_claims", guidelines="Must not claim an athlete endorses a product unless the text is an image caption for an approved LCE endorser."),
    valid_jsonld,
])
print(json.dumps(res.metrics, indent=2, default=str))
