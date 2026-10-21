"""Synthetic weekly Share of Model before GEOlogic went live, scaled so it climbs into the live 30-prompt baseline."""
from __future__ import annotations
from datetime import date, timedelta

_LCE_OFFSETS = (-0.09, -0.08, -0.09, -0.07, -0.05, -0.04, -0.02)
# Domino's stays flat within 0.02 of its live value (0.015, not 0.02: a rounded 0.02 step lands a float hair past 0.02).
_DOM_OFFSETS = (0.01, 0.0, 0.015, 0.01, 0.0, 0.01, 0.0)


def history_weeks(baseline_day: date, n: int = 7) -> list[date]:
    monday = baseline_day - timedelta(days=baseline_day.weekday())
    return [monday - timedelta(weeks=n - i) for i in range(n)]


def weekly_history(lce_now: float, dominos_now: float, weeks: list[date]) -> list[tuple[date, str, float]]:
    clamp = lambda v: round(min(1.0, max(0.0, v)), 3)
    rows = [(w, "Little Caesars", clamp(lce_now + o)) for w, o in zip(weeks, _LCE_OFFSETS)]
    rows += [(w, "Domino's", clamp(dominos_now + o)) for w, o in zip(weeks, _DOM_OFFSETS)]
    return rows
