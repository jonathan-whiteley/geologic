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


_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")
_RANGE = re.compile(r"(\d+)\s*(?:-|to)\s*(\d+)", re.IGNORECASE)


def stated_range(stated, attribute=None) -> tuple[float, float] | None:
    """The stated value as an inclusive (low, high) range. founded prefers a four-digit year ("May 8, 1959" is 1959);
    serves reads "10-12" or "10 to 12" as a range; everything else (price) is the first number, low == high."""
    if stated is None:
        return None
    text = str(stated)
    if attribute == "founded":
        m = _YEAR.search(text)
        if m:
            return float(m.group(1)), float(m.group(1))
    if attribute == "serves":
        m = _RANGE.search(text)
        if m:
            lo, hi = sorted((float(m.group(1)), float(m.group(2))))
            return lo, hi
    v = parse_price(stated)
    return None if v is None else (v, v)


def _within(n: float, rng: tuple[float, float]) -> bool:
    """Inside the range to the cent. Half a cent, not a full cent: 5.00 - 4.99 is 0.0099999 in floating point."""
    return rng[0] - 0.005 < n < rng[1] + 0.005


def values_match(stated, fact: dict, attribute=None) -> bool:
    rng, b = stated_range(stated, attribute or fact.get("attribute")), parse_price(fact["value"])
    return rng is not None and b is not None and _within(b, rng)


def discontinued(subject, facts: list[dict], today) -> dict | None:
    """The current available = no fact for a subject, if the item is off the menu today."""
    return next((f for f in facts if f["subject"] == subject and f["attribute"] == "available"
                 and str(f["value"]).strip().lower() == "no" and is_current(f, today)), None)


def candidates(claim: dict, facts: list[dict], categories: dict, today=None) -> list[dict]:
    subj, attr = claim.get("subject"), claim.get("attribute")
    out = [f for f in facts if f["subject"] == subj and f["attribute"] == attr]
    cat = categories.get(subj)
    gone = today is not None and discontinued(subj, facts, today) is not None
    if attr == "price" and cat and not gone:  # an active deal price is a correct price for the items it applies to
        out += [f for f in facts if f.get("applies_to") == f"category:{cat}" and f["attribute"] == "price"]
    return out


def tag_claim(claim: dict, facts: list[dict], today, categories: dict) -> tuple[str, str | None]:
    attr = claim.get("attribute")
    if attr not in TAGGED_ATTRIBUTES or stated_range(claim.get("stated_value"), attr) is None:
        return "Unverifiable", None
    cands = candidates(claim, facts, categories, today)
    if not cands:
        return "Unverifiable", None
    matches = [f for f in cands if values_match(claim["stated_value"], f, attr)]
    current = [f for f in matches if is_current(f, today)]
    if current:
        return "Correct", current[0]["fact_id"]
    old = [f for f in matches if f.get("valid_to") is not None and f["valid_to"] < today]
    if old:
        return "Outdated", old[0]["fact_id"]
    truth = next((f for f in cands if f["subject"] == claim.get("subject") and is_current(f, today)), None)
    if truth is None and attr == "price":   # off the menu: the truth is that it is no longer sold
        truth = discontinued(claim.get("subject"), facts, today)
    return "Wrong", truth["fact_id"] if truth else None


def _nums(text: str) -> set[float]:
    return {n for n in (parse_price(m) for m in _NUM.findall(_CITE.sub(" ", text or ""))) if n is not None}


def source_for(claim: dict, answer: str, docs) -> str | None:
    """The doc a claim came from: a [doc_id] citation in the sentence that states the value, else the highest-ranked
    retrieved doc whose body states the value, else None (the engine answered from model memory)."""
    ids = [d.doc_id for d in docs]
    rng = stated_range(claim.get("stated_value"), claim.get("attribute"))
    snippet = (claim.get("text") or "").strip().lower()[:40]
    for sent in split_sentences(answer):
        hit = (rng is not None and any(_within(n, rng) for n in _nums(sent))) or (snippet and snippet in sent.lower())
        cited = [m for m in _CITE.findall(sent) if m in ids]
        if hit and cited:
            return cited[0]
    if rng is not None:
        for d in docs:
            if any(_within(n, rng) for n in _nums(d.body)):
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
