import json, random
from datetime import datetime, timezone
from geologic.datagen import reference as r, corpus as c, signals as s
from geologic.datagen.answer_key import ANSWER_KEY

NOW = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)

def test_corpus_mirrors_pages_and_seeds_truths():
    pages = r.site_pages()
    docs = {d["doc_id"]: d for d in c.web_corpus(pages)}
    assert all(f"lce_{p['page_id']}" in docs for p in pages)
    blog = docs[c.SEEDED_DOC_IDS["stale_price_blog"]]
    assert "$5" in blog["body"] and blog["is_official"] is False           # S1
    assert "how many" in docs[c.SEEDED_DOC_IDS["dominos_sizing"]]["body"].lower()   # S2
    nfl = docs[c.SEEDED_DOC_IDS["nfl_news"]]
    assert "Saquon Barkley" in nfl["body"] and nfl["is_official"] is False   # S6
    assert len(docs) >= 120

def test_seeded_signals():
    k = s.seeded_signal("S3_kittle", NOW)
    assert k["source_type"] == "athlete_post" and k["image_uri"].endswith(".png")
    assert json.loads(k["payload"])["author"] == "George Kittle"
    ex = json.loads(s.seeded_signal("S4_exclusion", NOW)["payload"])
    assert ex["author_persona_id"] == "p_fictional_dax"
    cr = json.loads(s.seeded_signal("S7_crawler", NOW)["payload"])
    assert cr["page"] == "/order" and cr["hits"] == 0

def test_background_signals_never_tie_real_people_to_exclusions():
    rng = random.Random(7)
    for _ in range(500):
        row = s.background_signal(rng, NOW)
        p = json.loads(row["payload"])
        if p.get("author_persona_id") in {"p_jefferson", "p_kittle", "p_goff", "p_barkley"}:
            assert not any(w in p["text"].lower() for w in ["arrest", "politic", "gambl", "bet "])

def test_answer_key_covers_all_truths():
    assert set(ANSWER_KEY) == {"S1", "S2", "S3", "S4", "S5", "S6", "S7"}
