from types import SimpleNamespace as N
from backend.supervisor import final_text, Supervisor, TOO_LONG, TIMEOUT_S


def msg(text):
    return N(type="message", content=[N(type="output_text", text=text)])


def test_final_text_keeps_only_last_answer_and_strips_dashes():
    out = [msg("I'll query the Signal Analyst."), N(type="function_call", content=None), msg("<name>signal_analyst</name>"),
           msg("||Cluster|Answer Share|"), msg("<name>geologic-supervisor</name>"), msg("Comparison is lowest — a clear gap.")]
    assert final_text(out) == "Comparison is lowest, a clear gap."


def test_final_text_empty_when_no_message():
    assert final_text([N(type="function_call", content=None)]) == ""


def test_final_text_keeps_numeric_ranges():  # finding 13
    assert final_text([msg("Feeds 3\u20134 people \u2014 great value.")]) == "Feeds 3-4 people, great value."


class APITimeoutError(Exception):  # same class name as openai's
    pass


class FakeResponses:
    def __init__(self, exc=None): self.exc, self.kwargs = exc, None
    def create(self, **kw):
        self.kwargs = kw
        if self.exc: raise self.exc
        return N(output=[msg("Comparison has the lowest Answer Share at 0.07.")], output_text="")


def test_ask_passes_timeout_and_returns_answer():  # finding 14
    r = FakeResponses()
    assert Supervisor(None, client=N(responses=r)).ask("q") == "Comparison has the lowest Answer Share at 0.07."
    assert r.kwargs["timeout"] == TIMEOUT_S


def test_ask_timeout_returns_friendly_text():
    assert Supervisor(None, client=N(responses=FakeResponses(APITimeoutError("slow")))).ask("q") == TOO_LONG
