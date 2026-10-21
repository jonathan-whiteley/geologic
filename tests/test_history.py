from datetime import date
from geologic.history import history_weeks, weekly_history

def test_weeks_are_the_seven_mondays_before_the_baseline_week():
    w = history_weeks(date(2026, 10, 22))     # a Thursday; its week starts Monday 2026-10-19
    assert w[0] == date(2026, 8, 31) and w[-1] == date(2026, 10, 12) and len(w) == 7 and all(d.weekday() == 0 for d in w)

def test_history_climbs_into_the_live_value_without_a_jump():
    rows = weekly_history(0.42, 0.47, history_weeks(date(2026, 10, 22)))
    lce = [v for _, b, v in rows if b == "Little Caesars"]
    dom = [v for _, b, v in rows if b == "Domino's"]
    assert len(lce) == len(dom) == 7 and lce[0] < lce[-1] < 0.42 and 0.42 - lce[-1] <= 0.03
    assert all(abs(v - 0.47) <= 0.02 for v in dom) and all(0 <= v <= 1 for v in lce + dom)

def test_history_clamps_low_baselines():
    assert min(v for _, _, v in weekly_history(0.03, 0.02, history_weeks(date(2026, 10, 22)))) >= 0
