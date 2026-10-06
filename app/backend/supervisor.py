import os
from geologic.agents.strategist import _clean  # house-style dash cleanup ("3-4" stays a range)

TIMEOUT_S = 90
TOO_LONG = "That took too long. Try a narrower question."


def final_text(output) -> str:
    """The Supervisor streams its plan, tool calls and subagent tables as separate items; show only its last message."""
    for item in reversed(output or []):
        if getattr(item, "type", None) == "message":
            text = "".join(getattr(c, "text", "") or "" for c in item.content or []).strip()
            if text and not text.startswith("<name>"):
                return _clean(text)
    return ""


def _is_timeout(e: Exception) -> bool:
    return isinstance(e, TimeoutError) or "Timeout" in type(e).__name__  # openai.APITimeoutError, httpx timeouts


class Supervisor:
    def __init__(self, w, client=None):
        # No SDK retries: a retried timeout would keep the presenter waiting 3x TIMEOUT_S.
        self.client = client or w.serving_endpoints.get_open_ai_client().with_options(max_retries=0)
        self.endpoint = os.environ.get("GEOLOGIC_SUPERVISOR_ENDPOINT", "geologic-supervisor")

    def ask(self, question: str) -> str:
        try:
            r = self.client.responses.create(model=self.endpoint, input=[{"role": "user", "content": question}],
                                             timeout=TIMEOUT_S)
        except Exception as e:
            if _is_timeout(e):
                print(f"supervisor timed out after {TIMEOUT_S}s: {type(e).__name__}")
                return TOO_LONG
            raise
        return final_text(r.output) or _clean(r.output_text)
