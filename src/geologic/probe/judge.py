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
    return JudgeResult(mentioned, rank, list(obj.get("brands_mentioned") or []),
                       str(obj.get("sentiment") or "neutral"), list(obj.get("claims") or []))
