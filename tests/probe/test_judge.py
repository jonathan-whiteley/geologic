import pytest
from geologic.probe.judge import judge_messages, parse_judge_output, normalize_brand, JudgeParseError

def test_fenced_json():
    r = parse_judge_output('```json\n{"lce_mentioned": true, "lce_rank": 1, "brands_mentioned": ["Little Caesars"], "sentiment": "positive", "claims": [{"text": "It is $5.", "subject": "classic_pepperoni", "attribute": "price", "stated_value": "$5"}]}\n```', subjects=("classic_pepperoni",))
    assert r.lce_mentioned and r.lce_rank == 1 and r.claims[0]["stated_value"] == "$5"

def test_not_mentioned_rank_none():
    r = parse_judge_output('{"lce_mentioned": false, "lce_rank": 3, "brands_mentioned": [], "sentiment": "neutral", "claims": []}')
    assert r.lce_rank is None

@pytest.mark.parametrize("bad", ["", "not json", '{"lce_mentioned": "maybe"}', "[]"])
def test_malformed(bad):
    with pytest.raises(JudgeParseError):
        parse_judge_output(bad)

@pytest.mark.parametrize("variant,canonical", [
    ("Dominos", "Domino's"),
    ("dominos", "Domino's"),
    ("Papa John's", "Papa Johns"),
    ("papa john's", "Papa Johns"),
    ("Little Caesar's", "Little Caesars"),
    ("Pizza Hut", "Pizza Hut"),
    ("pizzahut", "Pizza Hut"),
    ("Unknown Brand", "Unknown Brand"),  # passthrough
])
def test_normalize_brand(variant, canonical):
    assert normalize_brand(variant) == canonical

def test_brands_mentioned_normalized_and_deduped():
    r = parse_judge_output('{"lce_mentioned": true, "lce_rank": 2, "brands_mentioned": ["Dominos", "Little Caesar\'s", "domino\'s"], "sentiment": "neutral", "claims": []}')
    # Dominos and domino's both map to Domino's; deduped to first occurrence
    assert r.brands_mentioned == ["Domino's", "Little Caesars"]


def test_judge_prompt_lists_vocabulary():
    m = judge_messages("q", "a", subjects=("party_pack", "brand"))
    assert "party_pack" in m[0]["content"] and "price" in m[0]["content"] and "stated_value" in m[0]["content"]

def test_parse_normalizes_claims():
    raw = ('{"lce_mentioned": true, "lce_rank": 2, "brands_mentioned": ["dominos", "Little Caesars"], "sentiment": "neutral",'
           ' "claims": [{"text": "Party Pack is $24.99.", "subject": "party_pack", "attribute": "price", "stated_value": "$24.99"},'
           ' {"text": "x", "subject": "pizza_mystery", "attribute": "vibes", "stated_value": 3}]}')
    j = parse_judge_output(raw, subjects=("party_pack",))
    assert j.brands_mentioned == ["Domino's", "Little Caesars"]
    assert j.claims == [{"text": "Party Pack is $24.99.", "subject": "party_pack", "attribute": "price", "stated_value": "$24.99"},
                        {"text": "x", "subject": "unknown", "attribute": "other", "stated_value": "3"}]

def test_parse_tolerates_missing_and_malformed_claim_fields():
    raw = ('{"lce_mentioned": true, "lce_rank": 1, "brands_mentioned": [], "sentiment": "neutral",'
           ' "claims": ["not a dict", {"subject": "brand", "attribute": "founded"}]}')
    assert parse_judge_output(raw, subjects=("brand",)).claims == [
        {"text": "", "subject": "brand", "attribute": "founded", "stated_value": None}]

def test_judge_prompt_strict_and_subject_list():
    m = judge_messages("q", "a", strict=True, subjects=("party_pack", "brand"))
    assert "SUBJECTS:\n- party_pack\n- brand\n" in m[0]["content"] and "No markdown fences" in m[0]["content"]
    assert "{subjects}" not in m[0]["content"] and "{attributes}" not in m[0]["content"]


# F1 (smoke 1): the judge sees each subject as "id: display name (aliases)", so "Game Day Party Pack" is never read as
# the gameday_499 id, and a returned display name or alias maps back to its id in code.
def test_judge_prompt_lists_display_names():
    from geologic.datagen.reference import subject_vocabulary
    content = judge_messages("q", "a", subjects=subject_vocabulary())[0]["content"]
    assert "party_pack: Game Day Party Pack" in content
    assert "gameday_499: $4.99 Online Gameday Deal" in content
    assert "classic_pepperoni: Classic Pepperoni Hot-N-Ready" in content and "brand: Little Caesars" in content
    assert "{subjects}" not in content


def test_subject_vocabulary_covers_every_subject_once():
    from geologic.datagen.reference import SUBJECTS, subject_vocabulary
    vocab = subject_vocabulary()
    assert [v[0] for v in vocab] == list(SUBJECTS)
    names = {v[0]: v[1] for v in vocab}
    assert names["party_pack"] == "Game Day Party Pack" and names["gameday_499"] == "$4.99 Online Gameday Deal"


def _claim_out(subject, vocab):
    raw = ('{"lce_mentioned": true, "lce_rank": 1, "brands_mentioned": [], "sentiment": "neutral", "claims": '
           '[{"text": "t", "subject": "%s", "attribute": "price", "stated_value": "$24.99"}]}' % subject)
    return parse_judge_output(raw, subjects=vocab).claims[0]["subject"]


def test_display_name_or_alias_maps_back_to_id():
    from geologic.datagen.reference import subject_vocabulary
    v = subject_vocabulary()
    assert _claim_out("Game Day Party Pack", v) == "party_pack"
    assert _claim_out("game day party pack", v) == "party_pack"
    assert _claim_out("party pack", v) == "party_pack"                           # alias
    assert _claim_out("party_pack: Game Day Party Pack", v) == "party_pack"      # the whole vocabulary line
    assert _claim_out("$4.99 Online Gameday Deal", v) == "gameday_499"
    assert _claim_out("Hot-N-Ready", v) == "classic_pepperoni"
    assert _claim_out("gameday_499", v) == "gameday_499"                         # ids still win
    assert _claim_out("Mystery Calzone", v) == "unknown"


def test_bare_id_subjects_still_work():
    assert _claim_out("party_pack", ("party_pack", "brand")) == "party_pack"
    assert _claim_out("Game Day Party Pack", ("party_pack", "brand")) == "unknown"   # no names given, no mapping


def test_subject_names_and_aliases_are_unique_across_subjects():
    # _subject_lookup uses setdefault, so a label shared by two subjects would silently resolve to the first one.
    from collections import defaultdict
    from geologic.datagen.reference import SUBJECTS, subject_vocabulary
    from geologic.probe.judge import _key
    vocab = subject_vocabulary()
    assert tuple(v[0] for v in vocab) == SUBJECTS
    owners = defaultdict(set)
    for sid, name, aliases in vocab:
        owners[sid.strip().lower()].add(sid)
        for label in (name, *aliases):
            if _key(label):
                owners[_key(label)].add(sid)
    clashes = {k: sorted(v) for k, v in owners.items() if len(v) > 1}
    assert clashes == {}
