"""Share of Model per answer and over rows (same math as v_kpis.answer_share), and the official citation rate."""
from __future__ import annotations

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
