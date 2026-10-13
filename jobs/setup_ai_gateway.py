"""Configures AI Gateway (usage tracking + inference tables) on all engine endpoints. Best effort: logs WARN on failure."""
import re
import sys
import os

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import AiGatewayUsageTrackingConfig, AiGatewayInferenceTableConfig
from geologic.config import settings as S

w = WorkspaceClient()
for family, ep in {**S.engines, "Judge": S.judge_endpoint}.items():
    try:
        w.serving_endpoints.put_ai_gateway(
            name=ep, usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
            inference_table_config=AiGatewayInferenceTableConfig(catalog_name=S.catalog, schema_name=S.schema,
                                                                 table_name_prefix=f"gw_{re.sub(r'[^a-z0-9]+', '_', family.lower()).strip('_')}", enabled=True))
        print(f"AI Gateway on {ep}")
    except Exception as e:
        print(f"WARN AI Gateway not applied to {ep}: {e}")
