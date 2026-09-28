"""Checks LCE claims in engine answers against the menu ground truth."""
from __future__ import annotations
import re

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUM = re.compile(r"(\d+(?:\.\d{1,2})?)")

def parse_price(s) -> float | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return round(float(s), 2)
    text = str(s).lower().strip()
    m = _NUM.search(text)
    if m:
        return round(float(m.group(1)), 2)
    for word, val in _WORDS.items():
        if re.search(rf"\b{word}\b", text) and re.search(r"dollar|buck", text):
            return float(val)
    return None

def _key(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())

def resolve_item(name: str, menu: list[dict]) -> dict | None:
    k = _key(name or "")
    if not k:
        return None
    for m in menu:
        if k == _key(m["name"]) or k in {_key(a) for a in m.get("aliases", [])}:
            return m
    for m in menu:
        if any(_key(a) and _key(a) in k for a in m.get("aliases", [])):
            return m
    return None

def verify_claims(claims: list[dict], menu: list[dict], deals: list[dict]) -> list[dict]:
    deal_prices = {round(d["price"], 2) for d in deals if d["active"]}
    out = []
    for c in claims:
        item = resolve_item(str(c.get("item", "")), menu)
        price = parse_price(c.get("price"))
        if item is None or price is None:
            verdict = "unverifiable"
        elif abs(price - item["price"]) < 0.01 or price in deal_prices:
            verdict = "correct"
        else:
            verdict = "wrong"
        out.append({**c, "verdict": verdict})
    return out

def accuracy_score(verdicts: list[dict]) -> float | None:
    correct = sum(v["verdict"] == "correct" for v in verdicts)
    wrong = sum(v["verdict"] == "wrong" for v in verdicts)
    return None if correct + wrong == 0 else correct / (correct + wrong)
