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


def test_rerank_none_means_no_match():
    # Rerank model answers "none" (e.g. a closed pizza box); no menu item is forced onto the signal
    chat = MultiChat("a closed pizza box", "none")
    out = describe_and_match(b"\x89PNG", chat, "ep", lambda t: ("thin_crust", 0.74),
                             candidates_fn=lambda t: list(_CANDS))
    assert out["matched_item_id"] is None
    assert out["match_score"] is None


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


def test_jpeg_photos_sent_with_jpeg_mime():
    from geologic.vision import describe_messages, image_mime
    assert image_mime(b"\xff\xd8\xff\xe0rest") == "image/jpeg" and image_mime(b"\x89PNG") == "image/png"
    assert describe_messages("AAA", "image/jpeg")[0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_rerank_none_is_normalized():  # finding 15
    for raw in ("None.", "  NONE  ", "none!", "`none`"):
        chat = MultiChat("a closed pizza box", raw)
        r = describe_and_match(b"img", chat, "ep", lambda d: ("x", 0.1),
                               candidates_fn=lambda d: [("thin_crust", "thin", 0.9)])
        assert r["matched_item_id"] is None, raw


def test_rerank_id_with_trailing_period_matches():
    chat = MultiChat("a square pizza", "Detroit_Pepperoni.")
    r = describe_and_match(b"img", chat, "ep", lambda d: ("x", 0.1),
                           candidates_fn=lambda d: [("thin_crust", "thin", 0.9), ("detroit_pepperoni", "square", 0.7)])
    assert r["matched_item_id"] == "detroit_pepperoni"


# Smoke 1 F3b: the Goff photo's description ranked detroit_pepperoni outside the top 10, so the reranker never saw it.
# The candidate list is now the top k from menu_idx plus the signal's text-resolved item when it is not already there.
from geologic.vision import rerank_candidates

_RANKED = [("classic_cheese", "c", 0.668), ("thin_crust", "t", 0.667), ("stuffed_crust", "s", 0.657),
           ("detroit_cheese", "dc", 0.603), ("detroit_pepperoni", "dp", 0.585)]

def test_rerank_candidates_adds_the_text_resolved_item():
    assert rerank_candidates(_RANKED, 3, "detroit_pepperoni") == _RANKED[:3] + [("detroit_pepperoni", "dp", 0.585)]

def test_rerank_candidates_no_duplicate_or_missing_item():
    assert rerank_candidates(_RANKED, 3, "thin_crust") == _RANKED[:3]          # already in the top k
    assert rerank_candidates(_RANKED, 3, None) == _RANKED[:3]                  # no text resolution
    assert rerank_candidates(_RANKED, 3, "party_pack") == _RANKED[:3]          # not in the index result: nothing to add

def test_reranker_can_pick_the_text_resolved_item():
    chat = MultiChat("A square-pan pizza with a thick crust and pepperoni.", "detroit_pepperoni")
    out = describe_and_match(b"\xff\xd8\xff", chat, "ep", lambda t: (None, 0.0),
                             candidates_fn=lambda t: rerank_candidates(_RANKED, 3, "detroit_pepperoni"))
    assert out["matched_item_id"] == "detroit_pepperoni" and out["match_score"] == 0.585
