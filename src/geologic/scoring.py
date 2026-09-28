"""Answer Share, modeled lift, and opportunity ranking."""
from __future__ import annotations
import math

def response_share(mentioned, rank) -> float:
    return 1.0 / rank if mentioned and rank else 0.0

def _ok(rows):
    return [r for r in rows if r.get("status") == "ok"]

def answer_share(rows: list[dict]) -> float | None:
    ok = _ok(rows)
    return None if not ok else sum(response_share(r["lce_mentioned"], r["lce_rank"]) for r in ok) / len(ok)

def citation_rate(rows: list[dict]) -> float | None:
    ok = _ok(rows)
    return None if not ok else sum(bool(r.get("cites_official")) for r in ok) / len(ok)

UNAVAILABLE_FACTOR = 0.05

def expected_lift(gap_severity, cluster_volume, calendar_multiplier, margin_pct, available) -> tuple[float, float]:
    volume = math.log1p(max(cluster_volume, 0) * max(calendar_multiplier, 0)) / math.log1p(5000)
    base = 10.0 * max(0.0, min(gap_severity, 1.0)) * volume * (0.5 + margin_pct)
    if not available:
        base *= UNAVAILABLE_FACTOR
    return round(base * 0.75, 2), round(base * 1.25, 2)

def rank_opportunities(opps: list[dict]) -> list[dict]:
    far = float("inf")
    def key(o):
        mid = (o["expected_lift_low"] + o["expected_lift_high"]) / 2
        w = o.get("window_expires_at")
        return (-mid, w.timestamp() if w else far)
    out = [dict(o) for o in sorted(opps, key=key)]
    for i, o in enumerate(out, start=1):
        o["rank"] = i
    return out
