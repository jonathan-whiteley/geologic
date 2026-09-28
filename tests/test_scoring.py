import pytest
from datetime import datetime, timezone
from geologic.scoring import response_share, answer_share, citation_rate, expected_lift, rank_opportunities

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

def test_lift_unavailable_item_is_tiny():
    lo, hi = expected_lift(0.8, 6400, 1.0, 0.29, available=False)
    lo2, hi2 = expected_lift(0.6, 1800, 1.0, 0.58, available=True)
    assert hi < lo2                      # S5: quiet available high-margin beats loud discontinued
    assert 0 <= lo <= hi

def test_lift_calendar_boost():
    base = expected_lift(0.5, 800, 1.0, 0.4, True)
    boosted = expected_lift(0.5, 800, 2.4, 0.4, True)
    assert boosted[0] > base[0]

def test_rank_opportunities():
    t = datetime(2026, 9, 25, tzinfo=timezone.utc)
    ranked = rank_opportunities([
        {"opp_id": "a", "expected_lift_low": 1, "expected_lift_high": 2, "window_expires_at": None},
        {"opp_id": "b", "expected_lift_low": 3, "expected_lift_high": 5, "window_expires_at": None},
        {"opp_id": "c", "expected_lift_low": 1, "expected_lift_high": 2, "window_expires_at": t},
    ])
    assert [o["opp_id"] for o in ranked] == ["b", "c", "a"] and ranked[0]["rank"] == 1
