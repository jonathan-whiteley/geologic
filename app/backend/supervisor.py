import os
import re

_DASH = re.compile(r"\s*[–—]\s*")


def final_text(output) -> str:
    """The Supervisor streams its plan, tool calls and subagent tables as separate items; show only its last message."""
    for item in reversed(output or []):
        if getattr(item, "type", None) == "message":
            text = "".join(getattr(c, "text", "") or "" for c in item.content or []).strip()
            if text and not text.startswith("<name>"):
                return _DASH.sub(", ", text)
    return ""


class Supervisor:
    def __init__(self, w):
        self.client = w.serving_endpoints.get_open_ai_client()
        self.endpoint = os.environ.get("GEOLOGIC_SUPERVISOR_ENDPOINT", "geologic-supervisor")

    def ask(self, question: str) -> str:
        r = self.client.responses.create(model=self.endpoint, input=[{"role": "user", "content": question}])
        return final_text(r.output) or r.output_text
