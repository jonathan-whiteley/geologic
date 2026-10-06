"""Logs, registers, and deploys the Content Strategist agent as a serving endpoint."""
import os
import sys

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _here = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _here = os.path.abspath(os.getcwd())
_root = os.path.abspath(os.path.join(_here, ".."))
sys.path.insert(0, os.path.join(_root, "src"))

import mlflow
from mlflow.models.resources import DatabricksServingEndpoint
from databricks import agents
from geologic.config import settings as S

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment("/Shared/geologic-drafting")
with mlflow.start_run(run_name="content_strategist"):
    info = mlflow.pyfunc.log_model(
        name="agent", python_model=os.path.join(_root, "agents", "strategist_agent.py"),
        code_paths=[os.path.join(_root, "src", "geologic")],
        pip_requirements=["databricks-sdk", "openai", "httpx", "mlflow>=3.1"],
        resources=[DatabricksServingEndpoint(endpoint_name=S.judge_endpoint)])
mv = mlflow.register_model(info.model_uri, S.fq("content_strategist"))
agents.deploy(S.fq("content_strategist"), mv.version, endpoint_name=S.strategist_endpoint, scale_to_zero=True)
print("deployed", S.strategist_endpoint, mv.version)
