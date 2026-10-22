"""House style for generated text: no em or en dashes (Global Constraint 5). LLM output goes through clean_dashes()."""
from __future__ import annotations
import re


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def strip_fences(text) -> str:
    """Removes a leading ```json fence and a trailing ``` fence from LLM output."""
    return _FENCE.sub("", (text or "").strip())


def clean_dashes(text):
    """Deterministically removes em and en dashes from generated text (house style)."""
    if not isinstance(text, str):
        return text
    text = re.sub(r"(?<=\d)\s?[\u2013\u2014]\s?(?=\d)", "-", text)
    # A dash before punctuation or at a line end, or one opening a line, is dropped rather than turned into
    # a stray ", ." or trailing ", ". Only dash sites are touched, so JSON-LD commas stay intact.
    text = re.sub(r"(?m)[ \t]*[\u2013\u2014][ \t]*(?=[.,;:!?)]|$)", "", text)
    text = re.sub(r"(?m)^([ \t]*)[\u2013\u2014][ \t]*", r"\1", text)
    text = re.sub(r"\s*[\u2013\u2014]\s*", ", ", text)
    return text
