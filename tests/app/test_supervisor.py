from types import SimpleNamespace as N
from backend.supervisor import final_text


def msg(text):
    return N(type="message", content=[N(type="output_text", text=text)])


def test_final_text_keeps_only_last_answer_and_strips_dashes():
    out = [msg("I'll query the Signal Analyst."), N(type="function_call", content=None), msg("<name>signal_analyst</name>"),
           msg("||Cluster|Answer Share|"), msg("<name>geologic-supervisor</name>"), msg("Comparison is lowest — a clear gap.")]
    assert final_text(out) == "Comparison is lowest, a clear gap."


def test_final_text_empty_when_no_message():
    assert final_text([N(type="function_call", content=None)]) == ""
