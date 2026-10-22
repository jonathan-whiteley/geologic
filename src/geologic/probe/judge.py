"""LLM-as-judge prompt and a strict, tolerant parser."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from geologic.claims import ATTRIBUTES
from geologic.style import strip_fences

ATTRIBUTES_TEXT = ", ".join(ATTRIBUTES)


class JudgeParseError(ValueError):
    pass

@dataclass(frozen=True)
class JudgeResult:
    lce_mentioned: bool
    lce_rank: int | None
    brands_mentioned: list[str]
    sentiment: str
    claims: list[dict]   # each {text, subject, attribute, stated_value}; tagged later by geologic.claims

_INSTR = ("Read the AI answer below. Return only JSON with keys: lce_mentioned (bool, true if Little Caesars is named), "
          "lce_rank (int, 1-based position of Little Caesars among pizza brands in order of first mention, or null), "
          "brands_mentioned (list of pizza brand names in order of first mention), sentiment toward Little Caesars "
          "(positive|neutral|negative), claims (list of every factual statement about a Little Caesars menu item, deal or the "
          "company; each {text: the sentence that states it, subject: the id of one of SUBJECTS, attribute: one of ATTRIBUTES, "
          "stated_value: the value as written, for example $24.99 or 12}). Each SUBJECTS line is id: display name (aliases); "
          "pick the subject whose name or alias matches the item or deal the sentence is about, and return only its id. "
          "A deal is its own subject, separate from the menu items it applies to. Use subject brand for company facts and "
          "attribute other when none fits. Do not include claims about other brands.\nSUBJECTS:\n{subjects}\n"
          "ATTRIBUTES: {attributes}")

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


def _vocab(subjects) -> list[tuple[str, str | None, tuple[str, ...]]]:
    """Subjects as (id, display name or None, aliases). Accepts bare ids or (id, name, aliases) entries."""
    out = []
    for s in subjects:
        if isinstance(s, str):
            out.append((s, None, ()))
        else:
            sid, name, *rest = s
            out.append((sid, name, tuple(rest[0]) if rest else ()))
    return out


def _subject_line(sid, name, aliases) -> str:
    if not name:
        return f"- {sid}"
    extra = [a for a in aliases if _key(a) != _key(name)]   # "Crazy Bread (crazy bread)" says nothing new
    return f"- {sid}: {name}" + (f" ({', '.join(extra)})" if extra else "")


def _key(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text).lower()).split())


def _subject_lookup(subjects) -> dict[str, str]:
    """Lookup from an id, display name or alias (normalized) to the subject id. Ids win; then names; then aliases;
    the first subject to claim a name keeps it."""
    vocab, out = _vocab(subjects), {}
    for sid, _n, _a in vocab:
        out.setdefault(sid.strip().lower(), sid)
    for tier in (lambda n, a: [n] if n else [], lambda n, a: list(a)):
        for sid, name, aliases in vocab:
            for label in tier(name, aliases):
                if _key(label):
                    out.setdefault(_key(label), sid)
    return out


def resolve_subject(value, lookup: dict[str, str]) -> str:
    """Map a judge-returned subject (an id, a display name, an alias, or a whole "id: name" line) to its id, else unknown."""
    text = str(value or "").strip().lstrip("-").strip()
    for cand in (text.lower(), text.split(":", 1)[0].strip().lower(), _key(text)):
        if cand and cand in lookup:
            return lookup[cand]
    return "unknown"


def judge_messages(prompt: str, answer: str, strict: bool = False, subjects=()) -> list[dict]:
    # str.replace, not str.format: the instructions contain literal braces ({text: ...}).
    lines = "\n".join(_subject_line(*v) for v in _vocab(subjects))
    instr = _INSTR.replace("{subjects}", lines).replace("{attributes}", ", ".join(ATTRIBUTES))
    extra = " Output a single JSON object and nothing else. No markdown fences." if strict else ""
    return [{"role": "system", "content": instr + extra},
            {"role": "user", "content": f"Question: {prompt}\n\nAnswer: {answer}"}]


def _normalize_claims(claims, subjects) -> list[dict]:
    """Keep the judge inside the vocabulary: a display name or alias maps back to its subject id, unknown subjects become
    "unknown", unknown attributes "other"."""
    out, lookup = [], _subject_lookup(subjects)
    for c in claims if isinstance(claims, list) else []:
        if not isinstance(c, dict):
            continue
        attr = str(c.get("attribute") or "").strip().lower()
        v = c.get("stated_value")
        out.append({"text": "" if c.get("text") is None else str(c["text"]),
                    "subject": resolve_subject(c.get("subject"), lookup),
                    "attribute": attr if attr in ATTRIBUTES else "other",
                    "stated_value": None if v is None else str(v)})
    return out

def parse_judge_output(text: str, subjects=()) -> JudgeResult:
    raw = strip_fences(text)
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
                       str(obj.get("sentiment") or "neutral"), _normalize_claims(obj.get("claims") or [], subjects))
