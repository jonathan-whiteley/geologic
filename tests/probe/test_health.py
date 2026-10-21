from geologic.probe.plan import run_health

ENGINES = ("Claude", "ChatGPT", "Gemini", "Meta AI")


def rows(bad_by_engine, per_engine=30, status="engine_error"):
    out = []
    for e in ENGINES:
        bad = bad_by_engine.get(e, 0)
        out += [{"engine": e, "status": status if i < bad else "ok"} for i in range(per_engine)]
    return out


def test_all_ok_is_healthy():
    h = run_health(rows({}), ENGINES)
    assert h.healthy and h.total == 120 and h.not_ok == 0 and h.dead_engines == ()


def test_ten_percent_not_ok_is_healthy_one_more_is_not():
    h = run_health(rows({"Claude": 6, "Gemini": 6}), ENGINES)          # 12 of 120 = 10%
    assert h.healthy and h.not_ok == 12
    h = run_health(rows({"Claude": 7, "Gemini": 6}), ENGINES)          # 13 of 120
    assert not h.healthy and h.not_ok == 13 and h.dead_engines == ()


def test_one_dead_engine_is_unhealthy_even_under_the_threshold():
    live = [{"engine": e, "status": "ok"} for e in ENGINES[:3] for _ in range(39)]
    h = run_health(live + [{"engine": "Meta AI", "status": "engine_error"}] * 3, ENGINES)   # 3 of 120 = 2.5%
    assert h.not_ok == 3 and h.total == 120 and h.dead_engines == ("Meta AI",) and not h.healthy


def test_expected_engine_with_no_rows_is_dead():
    h = run_health([{"engine": "Claude", "status": "ok"}], ("Claude", "Gemini"))
    assert not h.healthy and h.dead_engines == ("Gemini",)


def test_counts_by_engine_and_status():
    h = run_health(rows({"Claude": 2}, per_engine=3, status="unjudged"), ENGINES)
    assert h.counts[("Claude", "unjudged")] == 2 and h.counts[("Claude", "ok")] == 1 and h.counts[("Gemini", "ok")] == 3
    assert "Claude" in h.summary() and "unjudged=2" in h.summary()


def test_empty_run_with_expected_engines_is_unhealthy():
    h = run_health([], ENGINES)
    assert not h.healthy and h.total == 0 and set(h.dead_engines) == set(ENGINES)
