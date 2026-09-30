"""Vision helpers: image description and menu match via a vision model endpoint."""
import base64


def describe_messages(image_b64: str) -> list[dict]:
    return [{"role": "user", "content": [
        {"type": "text", "text": "Describe the food in this photo in one sentence: shape (round or square pan), crust style, toppings. Do not describe faces or identify people."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
    ]}]


def describe_and_match(image_bytes: bytes, chat, endpoint: str, match_fn) -> dict:
    desc = chat.complete(endpoint, describe_messages(base64.b64encode(image_bytes).decode()), max_tokens=120).strip()
    item_id, score = match_fn(desc)
    return {"description": desc, "matched_item_id": item_id, "match_score": score}
