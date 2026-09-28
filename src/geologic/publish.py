"""Applies an approved suggestion to a page, producing the next version."""
from __future__ import annotations

PUBLISHABLE = {"approved", "auto_published"}

def next_page_version(page: dict, suggestion: dict) -> dict:
    if suggestion.get("tier") == "BLOCKED":
        raise ValueError("blocked suggestions never publish")
    if suggestion.get("state") not in PUBLISHABLE:
        raise ValueError(f"state {suggestion.get('state')} is not publishable")
    new = dict(page)
    if suggestion["asset_type"] == "jsonld":
        new["jsonld"] = suggestion["diff_after"]
        new["has_valid_jsonld"] = True
    else:
        new["body"] = suggestion["diff_after"]
    new["version"] = page["version"] + 1
    return new
