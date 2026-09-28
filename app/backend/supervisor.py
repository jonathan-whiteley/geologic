import os

class Supervisor:
    def __init__(self, w):
        self.client = w.serving_endpoints.get_open_ai_client()
        self.endpoint = os.environ.get("GEOLOGIC_SUPERVISOR_ENDPOINT", "geologic-supervisor")

    def ask(self, question: str) -> str:
        r = self.client.responses.create(model=self.endpoint, input=[{"role": "user", "content": question}])
        return r.output_text
