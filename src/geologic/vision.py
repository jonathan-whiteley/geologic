"""Vision helpers: image description and menu match via a vision model endpoint."""
import base64


def image_mime(image_bytes: bytes) -> str:
    return "image/jpeg" if image_bytes[:3] == b"\xff\xd8\xff" else "image/png"


def describe_messages(image_b64: str, mime: str = "image/png") -> list[dict]:
    return [{"role": "user", "content": [
        {"type": "text", "text": "Describe the food in this photo in one sentence: shape (round or square pan), crust style, toppings. "
                 "If no real food is visible (only a closed box, packaging, or a printed graphic), reply exactly: no food visible. "
                 "Do not describe faces or identify people."},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
    ]}]


def rerank_messages(description: str, candidates: list[tuple[str, str, float]]) -> list[dict]:
    """Build chat messages asking the model to pick the best item_id from candidates."""
    lines = "\n".join(f"- {item_id}: {search_text}" for item_id, search_text, _ in candidates)
    return [{"role": "user", "content": (
        f"Food photo description: {description}\n\n"
        f"Menu item candidates:\n{lines}\n\n"
        f"Which item_id best matches the described food? "
        f"Answer 'none' if no real food is visible (a closed box, packaging, or a graphic is not food). "
        f"Reply with only the item_id (e.g. detroit_pepperoni), or 'none' if nothing fits."
    )}]


def _norm(answer: str) -> str:
    """'None.', ' NONE ' and '`none`' all mean none; ids are compared the same way."""
    return answer.strip().strip("`'\"*").strip().lower().rstrip(".!?,;:").strip()


def describe_and_match(image_bytes: bytes, chat, endpoint: str, match_fn, candidates_fn=None) -> dict:
    """Describe an image and match it to a menu item.

    When candidates_fn is supplied, uses a retrieve-then-rerank flow:
    candidates_fn(description) returns list[(item_id, search_text, score)].
    The chat model picks the best item_id. An answer of 'none' (case, whitespace and trailing punctuation
    ignored) returns no match; any other answer that is not a candidate id falls back to the top candidate.
    match_fn is used only when candidates_fn is absent or returns an empty list.

    Markdown bold markers (**) are stripped from the description before matching
    and storing so they do not add noise to the VS query.
    """
    raw = chat.complete(endpoint, describe_messages(base64.b64encode(image_bytes).decode(), image_mime(image_bytes)), max_tokens=120).strip()
    desc = raw.replace("**", "")
    if candidates_fn is not None:
        candidates = candidates_fn(desc)
        if candidates:
            answer = _norm(chat.complete(endpoint, rerank_messages(desc, candidates), max_tokens=20))
            if answer == "none":   # e.g. a pizza box or a branded shirt: real signal, no menu item to resolve
                return {"description": desc, "matched_item_id": None, "match_score": None}
            valid_ids = {item_id for item_id, _, _ in candidates}
            if answer in valid_ids:
                score = next(s for iid, _, s in candidates if iid == answer)
                return {"description": desc, "matched_item_id": answer, "match_score": score}
            # Fall back to top candidate on an invalid answer
            top_id, _, top_score = candidates[0]
            return {"description": desc, "matched_item_id": top_id, "match_score": top_score}
    item_id, score = match_fn(desc)
    return {"description": desc, "matched_item_id": item_id, "match_score": score}
