import pytest
from geologic.scoring import response_share, answer_share, citation_rate

def test_response_share():
    assert response_share(True, 1) == 1.0 and response_share(True, 4) == 0.25
    assert response_share(False, None) == 0.0 and response_share(None, None) == 0.0

def test_answer_share_ignores_non_ok():
    rows = [{"status": "ok", "lce_mentioned": True, "lce_rank": 2},
            {"status": "ok", "lce_mentioned": False, "lce_rank": None},
            {"status": "engine_error", "lce_mentioned": None, "lce_rank": None}]
    assert answer_share(rows) == pytest.approx(0.25)
    assert answer_share([{"status": "unjudged"}]) is None

def test_citation_rate():
    assert citation_rate([{"status": "ok", "cites_official": True}, {"status": "ok", "cites_official": False}]) == 0.5
