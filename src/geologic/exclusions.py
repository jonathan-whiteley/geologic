"""Exclusion matching shared by ingest, suggest, and publish enforcement points."""
from __future__ import annotations

def find_exclusion(text: str, persona_id: str | None, topics: list[str], rules: list[dict]) -> str | None:
    lowered = (text or "").lower()
    topic_set = {t.lower() for t in topics or []}
    for r in rules:
        if not r.get("active", True):
            continue
        ref = r["object_ref"].lower()
        if r["object_type"] == "persona" and persona_id and persona_id.lower() == ref:
            return r["rule_id"]
        if r["object_type"] in ("topic", "category") and (ref in topic_set or ref in lowered):
            return r["rule_id"]
    return None

def assert_persona_invariant(personas: list[dict]) -> None:
    bad = [p["persona_id"] for p in personas if p.get("is_real") and p.get("is_excluded")]
    if bad:
        raise ValueError(f"real people cannot be excluded: {bad}")
