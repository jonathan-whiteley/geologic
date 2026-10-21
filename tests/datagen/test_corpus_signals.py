import json, random
from datetime import datetime, timezone
from geologic.datagen import reference as r, corpus as c, signals as s
from geologic.datagen.answer_key import ANSWER_KEY
from geologic.exclusions import find_exclusion

NOW = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)

def test_corpus_mirrors_pages_and_seeds_truths():
    pages = r.site_pages()
    docs = {d["doc_id"]: d for d in c.web_corpus(pages)}
    assert all(f"lce_{p['page_id']}" in docs for p in pages)
    reddit = docs[c.SEEDED_DOC_IDS["reddit_price"]]
    assert "$4.25" in reddit["body"] and reddit["is_official"] is False      # wrong current price
    roundup = docs[c.SEEDED_DOC_IDS["party_pack_roundup"]]
    assert "$24.99" in roundup["body"] and roundup["is_official"] is False   # superseded Party Pack price
    assert "how many" in docs[c.SEEDED_DOC_IDS["dominos_sizing"]]["body"].lower()
    nfl = docs[c.SEEDED_DOC_IDS["nfl_news"]]
    assert "Jared Goff" in nfl["body"] and nfl["is_official"] is False      # S6
    assert len(docs) >= 120
    assert all(v in docs for v in c.SEEDED_DOC_IDS.values())

def test_owned_urls_match_pages_and_third_party_urls_use_domain():
    pages = {p["page_id"]: p for p in r.site_pages()}
    for d in c.web_corpus(list(pages.values())):
        if d["is_official"]:
            assert d["url"] == pages[d["page_id"]]["url"] and d["last_updated"] == pages[d["page_id"]]["updated_at"].date()
        else:
            assert d["url"] == f"https://{d['domain']}/{d['doc_id'].replace('_', '-')}"

def test_owner_class_rules():
    assert c.domain_for("r/nfl") == "reddit.com" and c.domain_for("youtube.com/@X") == "youtube.com"
    assert c.domain_for("qsr-weekly") == "qsr-weekly.com" and c.domain_for("dominos.com") == "dominos.com"
    assert c.owner_class_for({"is_official": True, "domain": "dominos.com"}) == "Owned"
    assert c.owner_class_for({"domain": "pizzahut.com", "source_type": "competitor"}) == "Competitor"
    assert c.owner_class_for({"domain": "reddit.com", "source_type": "reddit"}) == "Community"
    assert c.owner_class_for({"domain": "pizzapedia.org", "source_type": "reference"}) == "Reference"
    assert c.owner_class_for({"domain": "qsr-weekly.com", "source_type": "news"}) == "Editorial"

def test_web_corpus_does_not_mutate_module_docs():
    c.web_corpus(r.site_pages())
    assert all("owner_class" not in d for d in c._THIRD_PARTY)

def test_seeded_signals():
    k = s.seeded_signal("S3_goff", NOW)
    assert k["source_type"] == "athlete_post" and k["image_uri"].endswith("/signals/goff_slices_n_stix.jpg")
    assert json.loads(k["payload"])["author"] == "Jared Goff"
    repost = json.loads(s.seeded_signal("S4_repost", NOW)["payload"])
    assert repost["author"] == "@sidelinebets" and "author_persona_id" not in repost
    assert find_exclusion(repost["text"], None, [], r.exclusion_rules()) == "EX-03"
    assert set(s.SEEDED) == {"S3_goff", "S4_repost", "S5_pretzel", "S5_puffs"}
    for retired in ("S4_exclusion", "S7_crawler"):
        try:
            s.seeded_signal(retired, NOW)
            raise AssertionError(retired)
        except ValueError:
            pass

def test_background_signals_have_no_athlete_posts():
    rng = random.Random(7)
    for _ in range(500):
        row = s.background_signal(rng, NOW)
        p = json.loads(row["payload"])
        assert row["source_type"] != "athlete_post" and "author_persona_id" not in p and row["image_uri"] is None

def test_answer_key_points_at_real_docs_and_facts():
    docs = {d["doc_id"] for d in c.web_corpus(r.site_pages())}
    facts = {f["fact_id"] for f in r.brand_facts()}
    for story, k in ANSWER_KEY.items():
        if "source_doc_id" in k:
            assert k["source_doc_id"] in docs, story
        for key in ("stated_fact_id", "truth_fact_id"):
            if key in k:
                assert k[key] in facts, story
    assert ANSWER_KEY["goff_moment"]["prompt_id"] in {p["prompt_id"] for p in r.tracked_prompts()}
    assert ANSWER_KEY["goff_moment"]["persona_id"] in {p["persona_id"] for p in r.personas() if p["approved_for_association"]}
