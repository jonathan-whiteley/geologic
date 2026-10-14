import sys, pathlib
from types import SimpleNamespace as N
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from fastapi.testclient import TestClient
from main import app
from backend import deps
from backend.genie import GenieService, with_context, source_of

SQL = "SELECT `Cluster`, MEASURE(`Share of Model`) FROM jdub_demo.geologic.mv_answer_share GROUP BY ALL"

def started(conv="c1", mid="m1"):
    return N(response=N(conversation_id=conv, message_id=mid, id=mid))

def stmt(cols, rows, total=None):
    return N(statement_response=N(statement_id="st1", manifest=N(schema=N(columns=[N(name=c, type_name=N(value=t)) for c, t in cols]),
                                                                  total_row_count=total if total is not None else len(rows), truncated=False),
                                  result=N(data_array=rows)))

class FakeGenieApi:
    def __init__(self, message=None, result=None, followup_exc=None):
        self.message, self.result, self.followup_exc, self.calls = message, result, followup_exc, []
    def start_conversation(self, space_id, content):
        self.calls.append(("start", space_id, content)); return started("c2" if self.followup_exc else "c1")
    def create_message(self, space_id, conversation_id, content):
        self.calls.append(("followup", conversation_id, content))
        if self.followup_exc: raise self.followup_exc
        return started(conversation_id)
    def get_message(self, space_id, conversation_id, message_id):
        self.calls.append(("get", conversation_id, message_id)); return self.message
    def get_message_attachment_query_result(self, space_id, conversation_id, message_id, attachment_id):
        self.calls.append(("result", attachment_id)); return self.result

def svc(api):
    return GenieService(N(genie=api), "sp1")

def msg(status, attachments=(), error=None):
    return N(status=N(value=status), attachments=list(attachments), error=error)

QUERY = N(attachment_id="a1", text=None, suggested_questions=None, query=N(query=SQL, description="Lowest cluster", statement_id="st1"))

def test_ask_starts_then_follows_up_in_same_conversation():
    api = FakeGenieApi()
    assert svc(api).ask("q1") == {"conversation_id": "c1", "message_id": "m1"}
    assert svc(api).ask("and Domino's?", conversation_id="c1")["conversation_id"] == "c1"
    assert api.calls == [("start", "sp1", "q1"), ("followup", "c1", "and Domino's?")]

def test_stale_conversation_starts_fresh():  # Review Focus 4
    api = FakeGenieApi(followup_exc=RuntimeError("RESOURCE_DOES_NOT_EXIST"))
    out = svc(api).ask("q", conversation_id="old")
    assert [c[0] for c in api.calls] == ["followup", "start"] and out["conversation_id"] == "c2"

def test_context_prefix_and_cap():
    assert with_context("q", None) == "q"
    s = with_context("Why is this ranked here?", "Fix · " + "x" * 500)
    head, q = s.split("\n\n")
    assert head.startswith("Context: the user is on Fix · x") and q == "Question: Why is this ranked here?"
    assert len(head) <= 300 + len("Context: the user is on . Use it only if relevant.")

def test_rows_arrive_before_summary():
    api = FakeGenieApi(msg("ASKING_AI", [QUERY]), stmt([("cluster", "STRING"), ("share_of_model", "DOUBLE")], [["comparison", "0.07"]]))
    m = svc(api).get_message("c1", "m1")
    assert m["partial"] is True and m["text"] == "" and m["rows"] == [["comparison", "0.07"]]
    assert m["sql"] == SQL and m["source"] == "Genie · mv_answer_share"

def test_no_result_fetch_while_querying():
    api = FakeGenieApi(msg("EXECUTING_QUERY", [QUERY]))
    m = svc(api).get_message("c1", "m1")
    assert m["rows"] == [] and not any(c[0] == "result" for c in api.calls)

def test_completed_text_and_suggestions():
    text = N(attachment_id="a2", text=N(content="Comparison is lowest at 0.07."), query=None, suggested_questions=None)
    sq = N(attachment_id="a3", text=None, query=None, suggested_questions=N(questions=["Which engine is weakest on comparison?"]))
    api = FakeGenieApi(msg("COMPLETED", [QUERY, text, sq]), stmt([("cluster", "STRING")], [["comparison"]]))
    m = svc(api).get_message("c1", "m1")
    assert m["partial"] is False and m["text"] == "Comparison is lowest at 0.07."
    assert m["suggested_questions"] == ["Which engine is weakest on comparison?"] and m["columns"][0] == {"name": "cluster", "type": "STRING"}

def test_text_only_and_failed():  # Review Focus 4
    text = N(attachment_id="a2", text=N(content="I can only answer questions about GEOlogic data."), query=None, suggested_questions=None)
    m = svc(FakeGenieApi(msg("COMPLETED", [text]))).get_message("c1", "m1")
    assert (m["sql"], m["rows"], m["source"]) == ("", [], None)
    f = svc(FakeGenieApi(msg("FAILED", [], error=N(error="Warehouse unavailable")))).get_message("c1", "m1")
    assert f["error"] == "Warehouse unavailable"

def test_dashes_cleaned_from_text():
    text = N(attachment_id="a2", text=N(content="Comparison — lowest"), query=None, suggested_questions=None)
    assert "—" not in svc(FakeGenieApi(msg("COMPLETED", [text]))).get_message("c1", "m1")["text"]

def test_source_of():
    assert source_of("SELECT * FROM jdub_demo.geologic.v_kpis k JOIN `jdub_demo`.`geologic`.`gold_opportunities` o ON 1=1") == \
        "Genie · v_kpis, gold_opportunities"
    assert source_of("") is None

class FakeSvc:
    def __init__(self): self.calls = []
    def ask(self, q, conversation_id=None, context=None):
        self.calls.append((q, conversation_id, context)); return {"conversation_id": "c1", "message_id": "m1"}
    def get_message(self, c, m): return {"status": "COMPLETED", "conversation": c, "message": m}

def test_routes():
    S = FakeSvc(); app.dependency_overrides[deps.get_genie] = lambda: S
    try:
        cl = TestClient(app)
        assert cl.post("/api/genie/ask", json={"question": "  "}).status_code == 400
        r = cl.post("/api/genie/ask", json={"question": "q", "conversation_id": "c1", "context": "Fix · " + "y" * 400})
        assert r.json() == {"conversation_id": "c1", "message_id": "m1"}
        assert len(S.calls[0][2]) == 300
        assert cl.get("/api/genie/message/c1/m1").json()["status"] == "COMPLETED"
    finally:
        app.dependency_overrides.pop(deps.get_genie, None)

def test_unconfigured_is_503(monkeypatch):
    monkeypatch.delenv("GENIE_SPACE_ID", raising=False)
    monkeypatch.setattr(deps, "_genie", None)
    app.dependency_overrides.pop(deps.get_genie, None)
    assert TestClient(app).post("/api/genie/ask", json={"question": "q"}).status_code == 503

def test_source_of_skips_cte_names():  # G4: a WITH query like the live one
    sql = """WITH cluster_share AS (SELECT `Cluster`, MEASURE(`Share of Model`) AS s FROM jdub_demo.geologic.mv_answer_share GROUP BY ALL),
             ranked AS (SELECT *, RANK() OVER (ORDER BY s) AS r FROM cluster_share)
             SELECT * FROM ranked WHERE r = 1"""
    assert source_of(sql) == "Genie · mv_answer_share"
    assert source_of("with x as (select * from v_kpis) select * from x join gold_opportunities g on 1=1") == "Genie · v_kpis, gold_opportunities"

class NotFound(Exception):  # same class name as databricks.sdk.errors.NotFound
    pass

class ResourceDoesNotExist(NotFound):
    pass

def test_gone_conversation_errors_start_fresh():  # G5
    for exc in (NotFound("Conversation c9"), ResourceDoesNotExist("x"), type("BadRequest", (Exception,), {})("bad id"),
                type("InvalidParameterValue", (Exception,), {})("bad"), RuntimeError("Conversation not found")):
        api = FakeGenieApi(followup_exc=exc)
        assert svc(api).ask("q", conversation_id="old")["conversation_id"] == "c2", exc

def test_other_follow_up_errors_propagate():  # G5
    import pytest
    for exc in (RuntimeError("warehouse unavailable"), type("PermissionDenied", (Exception,), {})("no access"),
                type("TooManyRequests", (Exception,), {})("slow down")):
        api = FakeGenieApi(followup_exc=exc)
        with pytest.raises(type(exc)):
            svc(api).ask("q", conversation_id="old")
        assert [c[0] for c in api.calls] == ["followup"]
