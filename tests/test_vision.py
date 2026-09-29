from geologic.vision import describe_and_match, describe_messages


class Chat:
    def __init__(self): self.msgs = None
    def complete(self, endpoint, messages, max_tokens=600):
        self.msgs = messages; return "A square deep-dish pepperoni pizza on a tailgate table."


def test_describe_and_match():
    chat = Chat()
    out = describe_and_match(b"\x89PNG", chat, "vision-ep", lambda text: ("detroit_pepperoni", 0.91))
    assert out == {"description": "A square deep-dish pepperoni pizza on a tailgate table.", "matched_item_id": "detroit_pepperoni", "match_score": 0.91}
    img_part = chat.msgs[0]["content"][1]
    assert img_part["type"] == "image_url" and img_part["image_url"]["url"].startswith("data:image/png;base64,")


def test_no_faces_instruction():
    assert "Do not describe faces" in describe_messages("AAAA")[0]["content"][0]["text"]
