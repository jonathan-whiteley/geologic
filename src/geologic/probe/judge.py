"""LLM-as-judge prompt and a strict, tolerant parser."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass

class JudgeParseError(ValueError):
    pass

@dataclass(frozen=True)
class JudgeResult:
    lce_mentioned: bool
    lce_rank: int | None
    brands_mentioned: list[str]
    sentiment: str
    claims: list[dict]

_INSTR = ("Read the AI answer below. Return only JSON with keys: lce_mentioned (bool, true if Little Caesars is named), "
          "lce_rank (int, 1-based position of Little Caesars among pizza brands in order of first mention, or null), "
          "brands_mentioned (list of pizza brand names in order), sentiment toward Little Caesars (positive|neutral|negative), "
          "claims (list of {item, price} for every price stated for a Little Caesars item or deal).")

# Canonical brand names and their variant spellings (lowercase keys).
CANONICAL_BRANDS = ["Little Caesars", "Domino's", "Pizza Hut", "Papa Johns"]
_BRAND_MAP: dict[str, str] = {
    # Little Caesars variants
    "little caesars": "Little Caesars",
    "little caesar's": "Little Caesars",
    "little caesars'": "Little Caesars",
    "littlecaesars": "Little Caesars",
    "lce": "Little Caesars",
    # Domino's variants
    "domino's": "Domino's",
    "dominos": "Domino's",
    "domino s": "Domino's",
    "dominoes": "Domino's",
    "domino": "Domino's",
    # Pizza Hut variants
    "pizza hut": "Pizza Hut",
    "pizzahut": "Pizza Hut",
    "pizza-hut": "Pizza Hut",
    # Papa Johns variants
    "papa johns": "Papa Johns",
    "papa john's": "Papa Johns",
    "papa john s": "Papa Johns",
    "papajohns": "Papa Johns",
    "papa john": "Papa Johns",
    "papa johns pizza": "Papa Johns",
}


def normalize_brand(name: str) -> str:
    """Return the canonical brand name for a judge-emitted variant, or the original if unknown."""
    return _BRAND_MAP.get(name.strip().lower(), name)


def _normalize_brands(brands: list) -> list[str]:
    """Normalize each brand, deduplicate preserving first-mention order."""
    seen: set[str] = set()
    out: list[str] = []
    for b in brands:
        canonical = normalize_brand(str(b))
        if canonical not in seen:
            seen.add(canonical)
            out.append(canonical)
    return out


def judge_messages(prompt: str, answer: str, strict: bool = False) -> list[dict]:
    extra = " Output a single JSON object and nothing else. No markdown fences." if strict else ""
    return [{"role": "system", "content": _INSTR + extra},
            {"role": "user", "content": f"Question: {prompt}\n\nAnswer: {answer}"}]

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

def parse_judge_output(text: str) -> JudgeResult:
    raw = _FENCE.sub("", (text or "").strip())
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise JudgeParseError(str(e)) from e
    if not isinstance(obj, dict) or not isinstance(obj.get("lce_mentioned"), bool):
        raise JudgeParseError("missing lce_mentioned")
    mentioned = obj["lce_mentioned"]
    rank = obj.get("lce_rank")
    rank = int(rank) if mentioned and isinstance(rank, (int, float)) and rank >= 1 else (1 if mentioned else None)
    brands = _normalize_brands(obj.get("brands_mentioned") or [])
    return JudgeResult(mentioned, rank, brands,
                       str(obj.get("sentiment") or "neutral"), list(obj.get("claims") or []))
