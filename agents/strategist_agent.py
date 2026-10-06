"""MLflow ResponsesAgent exposing the Content Strategist to the Agent Bricks Supervisor.
Input: a user message containing JSON {"opp": {...}, "page": {...}}. Output: the draft JSON as text."""
import json
import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
from databricks.sdk import WorkspaceClient
from geologic.agents.strategist import draft_suggestion
from geologic.clients import FmapiChat
from geologic.config import settings as S
from geologic.datagen.reference import deals, menu_items

class StrategistAgent(ResponsesAgent):
    def __init__(self):
        self.chat = FmapiChat.from_workspace(WorkspaceClient())

    @mlflow.trace(span_type="AGENT")
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        text = request.input[-1].content if isinstance(request.input[-1].content, str) else request.input[-1].content[0]["text"]
        try:
            body = json.loads(text)
            out = json.dumps(draft_suggestion(body["opp"], body["page"], menu_items(), deals(), self.chat, S.judge_endpoint))
        except Exception as e:  # Supervisor gets a readable error instead of a 500
            out = json.dumps({"error": str(e)})
        return ResponsesAgentResponse(output=[self.create_text_output_item(text=out, id="draft")])

mlflow.models.set_model(StrategistAgent())
