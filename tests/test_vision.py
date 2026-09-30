from geologic.vision import describe_and_match, describe_messages, rerank_messages


class Chat:
    def __init__(self): self.msgs = None
    def complete(self, endpoint, messages, max_tokens=600):
        self.msgs = messages; return "A square deep-dish pepperoni pizza on a tailgate table."


class MultiChat:
    """Returns different responses for the describe call (1st) and rerank call (2nd+)."""
    def __init__(self, desc_response, rerank_response):
        self._responses = [desc_response, rerank_response]
        self._idx = 0

    def complete(self, endpoint, messages, max_tokens=600):
        r = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return r


_CANDS = [
    ("thin_crust", "round pizza thin crispy crust pepperoni", 0.74),
    ("detroit_pepperoni", "square pan pizza thick deep-dish crust pepperoni", 0.68),
    ("stuffed_crust", "round pizza thick stuffed crust pepperoni", 0.72),
]


def test_describe_and_match():
    chat = Chat()
    out = describe_and_match(b"\x89PNG", chat, "vision-ep", lambda text: ("detroit_pepperoni", 0.91))
    assert out == {"description": "A square deep-dish pepperoni pizza on a tailgate table.", "matched_item_id": "detroit_pepperoni", "match_score": 0.91}
    img_part = chat.msgs[0]["content"][1]
    assert img_part["type"] == "image_url" and img_part["image_url"]["url"].startswith("data:image/png;base64,")


def test_no_faces_instruction():
    assert "Do not describe faces" in describe_messages("AAAA")[0]["content"][0]["text"]


def test_rerank_picks_non_top_candidate():
    # Top VS candidate is thin_crust but rerank model picks detroit_pepperoni (2nd in list)
    chat = MultiChat("A square pan pizza with thick deep-dish crust.", "detroit_pepperoni")
    out = describe_and_match(b"\x89PNG", chat, "ep", lambda t: ("thin_crust", 0.74),
                             candidates_fn=lambda t: list(_CANDS))
    assert out["matched_item_id"] == "detroit_pepperoni"
    assert out["match_score"] == 0.68


def test_rerank_fallback_on_invalid_answer():
    # Rerank model returns an id not in the candidate list; should fall back to top candidate
    chat = MultiChat("some pizza", "not_a_valid_id")
    out = describe_and_match(b"\x89PNG", chat, "ep", lambda t: ("thin_crust", 0.74),
                             candidates_fn=lambda t: list(_CANDS))
    assert out["matched_item_id"] == "thin_crust"
    assert out["match_score"] == 0.74


def test_rerank_fallback_on_none():
    # Rerank model answers "none"; should fall back to top candidate
    chat = MultiChat("some food", "none")
    out = describe_and_match(b"\x89PNG", chat, "ep", lambda t: ("thin_crust", 0.74),
                             candidates_fn=lambda t: list(_CANDS))
    assert out["matched_item_id"] == "thin_crust"
    assert out["match_score"] == 0.74


def test_strip_markdown_bold():
    # Vision model returns markdown bold markers; they should be stripped
    class BoldChat:
        def complete(self, endpoint, messages, max_tokens=600):
            return "A **square pan pizza** with **thick** crust."
    out = describe_and_match(b"\x89PNG", BoldChat(), "ep", lambda t: ("pizza", 0.9))
    assert "**" not in out["description"]
    assert out["description"] == "A square pan pizza with thick crust."


def test_rerank_messages_structure():
    msgs = rerank_messages("a square pizza", [("detroit_pepperoni", "square pan pizza", 0.7)])
    assert len(msgs) == 1 and msgs[0]["role"] == "user"
    assert "detroit_pepperoni" in msgs[0]["content"]
    assert "none" in msgs[0]["content"]
