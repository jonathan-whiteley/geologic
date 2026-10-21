"""Claims about Little Caesars, tagged by code against brand_facts (spec section 3). The judge only extracts claims
and maps them to a subject and attribute; Correct, Wrong, Outdated and Unverifiable are decided here."""
from __future__ import annotations
import hashlib
import re
from functools import lru_cache
from geologic.facts import parse_price

TAGS = ("Correct", "Wrong", "Outdated", "Unverifiable")
# Only numeric attributes are tagged Correct, Wrong or Outdated. Free-text values (style, ordering, delivery) cannot be
# compared reliably, so they stay Unverifiable and never count against fact accuracy.
TAGGED_ATTRIBUTES = ("price", "serves", "founded")
ATTRIBUTES = TAGGED_ATTRIBUTES + ("contents", "style", "ordering", "delivery", "nfl_sponsor", "available", "other")
_CITE = re.compile(r"\[([A-Za-z0-9_\-]+)\]")
_NUM = re.compile(r"\$?\d+(?:\.\d{1,2})?")
_SENT = re.compile(r"(?<=[.!?])\s+")
_MASK = re.compile(r"\x00(\d+)\x00")


@lru_cache(maxsize=1)
def protected_names() -> tuple[str, ...]:
    """Menu names and aliases with punctuation inside them ("Detroit-Style Deep!Deep! Dish Pepperoni", "deep!deep! dish").
    Loaded lazily so importing this module never imports geologic.config."""
    from geologic.datagen.reference import menu_items
    names = {n for m in menu_items() for n in (m["name"], *m["aliases"])}
    return tuple(sorted((n for n in names if re.search(r"[.!?]\S", n)), key=len, reverse=True))


def split_sentences(text: str, names=None) -> list[str]:
    """Split on . ! ? followed by whitespace, never inside a protected name (masked first, case-insensitive)."""
    text, saved = text or "", []

    def stash(m):
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    for n in protected_names() if names is None else names:
        text = re.sub(re.escape(n), stash, text, flags=re.IGNORECASE)

    def restore(s):
        return _MASK.sub(lambda m: saved[int(m.group(1))], s)

    return [restore(s).strip() for s in _SENT.split(text) if s.strip()]


def _h(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def answer_id(run_id: str, prompt_id: str, engine: str) -> str:
    return "a_" + _h(f"{run_id}|{prompt_id}|{engine}")


def claim_id(aid: str, i: int) -> str:
    return "c_" + _h(f"{aid}|{i}")


def is_current(fact: dict, today) -> bool:
    return fact["valid_from"] <= today and (fact.get("valid_to") is None or today <= fact["valid_to"])


def _same(a: float, b: float) -> bool:
    """Equal to the cent. Half a cent, not a full cent: 5.00 - 4.99 is 0.0099999 in floating point."""
    return abs(a - b) < 0.005


def values_match(stated, fact: dict) -> bool:
    a, b = parse_price(stated), parse_price(fact["value"])
    return a is not None and b is not None and _same(a, b)


def candidates(claim: dict, facts: list[dict], categories: dict) -> list[dict]:
    subj, attr = claim.get("subject"), claim.get("attribute")
    out = [f for f in facts if f["subject"] == subj and f["attribute"] == attr]
    cat = categories.get(subj)
    if attr == "price" and cat:  # an active deal price is a correct price for the items it applies to
        out += [f for f in facts if f.get("applies_to") == f"category:{cat}" and f["attribute"] == "price"]
    return out


def tag_claim(claim: dict, facts: list[dict], today, categories: dict) -> tuple[str, str | None]:
    if claim.get("attribute") not in TAGGED_ATTRIBUTES or parse_price(claim.get("stated_value")) is None:
        return "Unverifiable", None
    cands = candidates(claim, facts, categories)
    if not cands:
        return "Unverifiable", None
    matches = [f for f in cands if values_match(claim["stated_value"], f)]
    current = [f for f in matches if is_current(f, today)]
    if current:
        return "Correct", current[0]["fact_id"]
    old = [f for f in matches if f.get("valid_to") is not None and f["valid_to"] < today]
    if old:
        return "Outdated", old[0]["fact_id"]
    truth = next((f for f in cands if f["subject"] == claim.get("subject") and is_current(f, today)), None)
    return "Wrong", truth["fact_id"] if truth else None


def _nums(text: str) -> set[float]:
    return {n for n in (parse_price(m) for m in _NUM.findall(_CITE.sub(" ", text or ""))) if n is not None}


def source_for(claim: dict, answer: str, docs) -> str | None:
    """The doc a claim came from: a [doc_id] citation in the sentence that states the value, else the highest-ranked
    retrieved doc whose body states the value, else None (the engine answered from model memory)."""
    ids = [d.doc_id for d in docs]
    value = parse_price(claim.get("stated_value"))
    snippet = (claim.get("text") or "").strip().lower()[:40]
    for sent in split_sentences(answer):
        hit = (value is not None and any(_same(n, value) for n in _nums(sent))) or (snippet and snippet in sent.lower())
        cited = [m for m in _CITE.findall(sent) if m in ids]
        if hit and cited:
            return cited[0]
    if value is not None:
        for d in docs:
            if any(_same(n, value) for n in _nums(d.body)):
                return d.doc_id
    return None


def claim_rows(aid, meta, judged, facts, docs, answer, today, categories) -> list[dict]:
    rows = []
    for i, cl in enumerate(judged):
        tag, fid = tag_claim(cl, facts, today, categories)
        sv = cl.get("stated_value")
        rows.append({**meta, "claim_id": claim_id(aid, i), "answer_id": aid, "text": cl.get("text"), "subject": cl.get("subject"),
                     "attribute": cl.get("attribute"), "stated_value": None if sv is None else str(sv), "tag": tag,
                     "fact_id": fid, "source_doc_id": source_for(cl, answer, docs)})
    return rows


def accuracy(rows: list[dict]) -> float | None:
    good = sum(r["tag"] == "Correct" for r in rows)
    bad = sum(r["tag"] in ("Wrong", "Outdated") for r in rows)
    return None if good + bad == 0 else good / (good + bad)
