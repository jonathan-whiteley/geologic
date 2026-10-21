from geologic.patches import sections, apply_patch, get_section, last_section_id, section_containing, slug

BODY = "## Game Day Deals\n$4.99 online during NFL games.\nOfficial Pizza Sponsor of the NFL."

def test_sections_and_slug():
    assert slug("Feeding 12 for the big game!") == "feeding-12-for-the-big-game"
    assert sections(BODY) == [("game-day-deals", BODY)]
    assert sections("intro text\n## A\nx") == [("intro", "intro text"), ("a", "## A\nx")]
    assert last_section_id(BODY) == "game-day-deals" and last_section_id("") is None
    assert section_containing(BODY, "$4.99") == "game-day-deals" and section_containing(BODY, "$9") is None

def test_insert_after_section_keeps_the_rest():
    out = apply_patch(BODY, {"section_id": "game-day-deals", "op": "insert", "text": "## Feeding 12\nThe Party Pack feeds 12 for $29.99."})
    assert out.startswith(BODY) and out.endswith("The Party Pack feeds 12 for $29.99.\n") and out.count("## ") == 2

def test_replace_only_that_section():
    body = "## A\nold\n\n## B\nkeep"
    assert apply_patch(body, {"section_id": "a", "op": "replace", "text": "## A\nnew"}) == "## A\nnew\n\n## B\nkeep\n"

def test_missing_section_appends_and_empty_page_gets_the_patch():
    assert apply_patch("## A\nx", {"section_id": "zzz", "op": "insert", "text": "## Z\nz"}).endswith("## Z\nz\n")
    assert apply_patch("", {"section_id": "main", "op": "insert", "text": "## New\nn"}) == "## New\nn\n"
    assert get_section("## A\nx\n\n## B\ny", "b") == "## B\ny"
