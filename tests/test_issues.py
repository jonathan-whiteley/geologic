from datetime import date, datetime
from geologic.datagen.reference import brand_facts, personas
from geologic.issues import build_issues, claim_key

T = date(2026, 10, 21)
P = [dict(prompt_id="q201", prompt_text="Super Bowl party for 12", cluster="game_day_party", priority="Gold", branded=False),
     dict(prompt_id="q062", prompt_text="Best pizza for a Super Bowl party", cluster="game_day_party", priority="Gold", branded=False),
     dict(prompt_id="q090", prompt_text="Game day food ideas for a crowd", cluster="game_day_party", priority="Gold", branded=False),
     dict(prompt_id="q002", prompt_text="How much is a Hot-N-Ready", cluster="value", priority="Gold", branded=True),
     dict(prompt_id="q115", prompt_text="Best breadsticks", cluster="comparison", priority="Silver", branded=False),
     dict(prompt_id="q202", prompt_text="Best Detroit-style pizza for game day", cluster="game_day_party", priority="Gold", branded=False),
     dict(prompt_id="q119", prompt_text="NFL pizza ads", cluster="sponsorship", priority="Bronze", branded=False)]
SRC = [dict(doc_id="editorial_superbowl_roundup_2024", owner_class="Editorial", domain="partyplanner-weekly.com", page_id=None,
            title="2024 Super Bowl party food roundup", body="Little Caesars Party Pack is $24.99. Pizza Hut and Domino's too."),
       dict(doc_id="reddit_pizza_hnr", owner_class="Community", domain="reddit.com", page_id=None, title="r", body="$4.25"),
       dict(doc_id="review_pizzahut_gameday_top", owner_class="Editorial", domain="sportsfanfood.com", page_id=None, title="g",
            body="Pizza Hut is a top choice. Domino's is a close second."),
       dict(doc_id="comp_dominos_party_guide", owner_class="Competitor", domain="dominos.com", page_id=None, title="d", body="Domino's"),
       dict(doc_id="lce_pg_item_classic_pepperoni", owner_class="Owned", domain="littlecaesars.com", page_id="pg_item_classic_pepperoni",
            title="c", body="## Classic"),
       dict(doc_id="lce_pg_deals_game_day", owner_class="Owned", domain="littlecaesars.com", page_id="pg_deals_game_day", title="g", body="x")]
PAGES = [dict(page_id="pg_item_classic_pepperoni", primary_subject="classic_pepperoni", updated_at=datetime(2025, 6, 1)),
         dict(page_id="pg_item_crazy_bread", primary_subject="crazy_bread", updated_at=datetime(2026, 8, 1)),
         dict(page_id="pg_deals_game_day", primary_subject="gameday_499", updated_at=datetime(2025, 6, 1))]

def ans(pid, eng, mentioned=False, cited=(), retrieved=()):
    return dict(answer_id=f"{pid}{eng}", prompt_id=pid, engine=eng, status="ok", lce_mentioned=mentioned,
                cited_doc_ids=list(cited), retrieved_doc_ids=list(retrieved or cited))

ENG = ("Claude", "ChatGPT", "Gemini", "Meta AI")
ANS = ([ans("q201", e, e == "Claude", ["editorial_superbowl_roundup_2024"]) for e in ENG]
       + [ans("q062", e, False, ["review_pizzahut_gameday_top"]) for e in ENG]
       + [ans("q090", e, False, ["review_pizzahut_gameday_top", "comp_dominos_party_guide"]) for e in ENG]
       + [ans("q002", e, True, ["reddit_pizza_hnr"]) for e in ENG]
       + [ans("q115", e, False, ["comp_dominos_party_guide"]) for e in ENG]
       + [ans("q202", e, False, ["comp_dominos_party_guide"]) for e in ENG]
       + [ans("q119", e, False, ["comp_dominos_party_guide"]) for e in ENG])

def cl(pid, eng, subject, value, tag, fact, src):
    return dict(prompt_id=pid, engine=eng, subject=subject, attribute="price", stated_value=value, tag=tag, fact_id=fact, source_doc_id=src)

CLAIMS = [cl("q201", "ChatGPT", "party_pack", "$24.99", "Outdated", "F13", "editorial_superbowl_roundup_2024"),
          cl("q201", "Gemini", "party_pack", "$24.99", "Outdated", "F13", "editorial_superbowl_roundup_2024"),
          cl("q002", "Claude", "classic_pepperoni", "$4.25", "Wrong", "F03", "reddit_pizza_hnr"),
          cl("q002", "Gemini", "crazy_bread", "$3.99", "Correct", "F10", None)]
MOMENTS = [dict(moment_id="mo_goff", kind="persona", title="Jared Goff posted a Detroit-Style moment", persona_id="p_goff",
                item_id="detroit_pepperoni", prompt_ids=["q202", "s_abc"], signal_ids=["g1"]),
           dict(moment_id="mo_puffs", kind="trend", title="Crazy Puffs is trending", persona_id=None,
                item_id="crazy_puffs_pepperoni", prompt_ids=["s_def"], signal_ids=["t1"])]

def build(**kw):
    args = dict(answers=ANS, claims=CLAIMS, prompts=P, sources=SRC, pages=PAGES, facts=brand_facts(), moments=MOMENTS,
                personas=personas(), today=T)
    return build_issues(**{**args, **kw})

def one(issues, **match):
    hits = [i for i in issues if all(i.get(k) == v for k, v in match.items())]
    assert len(hits) == 1, (match, [(i["issue_type"], i["source_doc_id"]) for i in issues])
    return hits[0]

def test_outdated_editorial_makes_correction_email_and_counter_patch():
    i = one(build(), issue_type="outdated", source_doc_id="editorial_superbowl_roundup_2024")
    assert i["fact_id"] == "F12" and i["stated_fact_id"] == "F13" and i["prompt_ids"] == ["q201"] and i["engines"] == ["ChatGPT", "Gemini"]
    assert i["action_lane"] == "request_correction"
    assert [(f["asset_type"], f["page_id"], f["recipient"]) for f in i["planned"]] == [
        ("correction_email", None, "partyplanner-weekly.com"), ("owned_patch", "pg_deals_game_day", None)]
    assert i["claim_keys"] == [claim_key("Outdated", "editorial_superbowl_roundup_2024", "party_pack", "price")]

def test_wrong_community_makes_brand_reply():
    i = one(build(), issue_type="wrong", source_doc_id="reddit_pizza_hnr")
    assert i["action_lane"] == "reply_as_brand" and [f["asset_type"] for f in i["planned"]] == ["community_reply"]

def test_stale_owned_page_makes_t0_jsonld_even_when_never_cited():
    i = one(build(), issue_type="outdated", source_doc_id="lce_pg_item_classic_pepperoni")
    assert i["planned"] == [dict(asset_type="jsonld", lane="fix_page", page_id="pg_item_classic_pepperoni", section_id="jsonld",
                                 op="replace", recipient=None)]
    assert i["prompt_ids"] == ["q002"] and i["fact_id"] == "F03"

def test_fresh_owned_page_and_unclaimed_stale_page_make_no_issue():
    ids = {i["source_doc_id"] for i in build()}
    assert "lce_pg_item_crazy_bread" not in ids          # fresh page
    assert "lce_pg_deals_game_day" not in ids            # stale, but no tracked prompt has a gameday_499 claim

def test_missing_us_needs_two_prompts_no_lce_and_not_a_competitor():
    i = one(build(), issue_type="missing_us")
    assert i["source_doc_id"] == "review_pizzahut_gameday_top" and i["prompt_ids"] == ["q062", "q090"]
    assert i["cluster"] == "game_day_party" and i["planned"][0]["page_id"] == "pg_answer_game_day_party"
    one_prompt = [a for a in ANS if a["prompt_id"] != "q090"]
    assert not [x for x in build(answers=one_prompt) if x["issue_type"] == "missing_us"]

def test_moment_gap_with_association_only_for_an_approved_real_person():
    i = one(build(), issue_type="moment_gap")
    assert i["moment_id"] == "mo_goff" and i["prompt_ids"] == ["q202"] and i["persona_id"] == "p_goff"
    assert [f["asset_type"] for f in i["planned"]] == ["moment_page", "association"]
    assert all(f["page_id"] == "pg_moment_detroit_pepperoni" for f in i["planned"])
    creator = [{**MOMENTS[0], "persona_id": "p_creator_slicequeen"}]
    assert [f["asset_type"] for f in one(build(moments=creator), issue_type="moment_gap")["planned"]] == ["moment_page"]

def test_no_answer_page_only_for_uncovered_unbranded_gold_or_silver():
    issues = build()
    i = one(issues, issue_type="no_answer_page")
    assert i["prompt_ids"] == ["q115"] and i["planned"][0]["page_id"] == "pg_answer_q115"
    assert not any(x["issue_type"] == "no_answer_page" and x["prompt_ids"] in (["q119"], ["q202"], ["q062"]) for x in issues)

def test_every_issue_has_prompts_stable_ids_and_ranks():  # Review Focus: no prompt, no issue
    a, b = build(), build()
    assert [x["issue_id"] for x in a] == [x["issue_id"] for x in b]
    assert all(x["prompt_ids"] for x in a) and [x["rank"] for x in a] == list(range(1, len(a) + 1))
    assert all(x["issue_id"].startswith("is_") and "\u2014" not in x["title"] for x in a)

def test_moment_with_only_suggestions_makes_no_issue():
    assert not [x for x in build() if x.get("moment_id") == "mo_puffs"]

def test_owned_competitor_and_memory_claims_pick_their_lanes():
    extra = [cl("q115", "Claude", "crazy_bread", "$2.99", "Wrong", "F10", "comp_dominos_party_guide"),
             cl("q115", "Gemini", "crazy_bread", "$2.99", "Wrong", "F10", None),
             cl("q202", "ChatGPT", "detroit_pepperoni", "$9.99", "Wrong", "F08", "lce_pg_deals_game_day")]
    issues = build(claims=CLAIMS + extra)
    comp = one(issues, issue_type="wrong", source_doc_id="comp_dominos_party_guide")
    assert comp["action_lane"] == "counter_content"
    assert [(f["asset_type"], f["page_id"], f["op"]) for f in comp["planned"]] == [("owned_patch", "pg_menu", "insert")]
    mem = one(issues, issue_type="wrong", source_doc_id=None)
    assert mem["action_lane"] == "publish_fact" and mem["planned"][0]["page_id"] == "pg_answer_q115"
    assert mem["claim_keys"] == ["Wrong|memory|crazy_bread|price"] and mem["source_doc_ids"] == [] and mem["fact_id"] == "F10"
    assert mem["title"] == "Engines state a wrong Crazy Bread price from memory ($2.99)" and mem["stated_fact_id"] is None
    own = one(issues, issue_type="wrong", source_doc_id="lce_pg_deals_game_day")
    assert own["action_lane"] == "fix_page"
    assert [(f["asset_type"], f["page_id"], f["op"]) for f in own["planned"]] == [("owned_patch", "pg_deals_game_day", "replace")]

def test_moment_on_a_prompt_we_already_win_makes_no_issue():
    won = [a for a in ANS if a["prompt_id"] != "q202"] + [ans("q202", e, True, ["lce_pg_deals_game_day"]) for e in ENG]
    assert not [x for x in build(answers=won) if x["issue_type"] == "moment_gap"]

def test_discontinued_item_moment_makes_no_moment_gap_but_its_stale_claim_still_does():  # fix round 1
    old_price = next(f["fact_id"] for f in brand_facts() if f["subject"] == "pretzel_crust" and f["attribute"] == "price")
    pretzel = dict(moment_id="mo_pretzel", kind="trend", title="Pretzel Crust Pepperoni is trending", persona_id=None,
                   item_id="pretzel_crust", prompt_ids=["q115"], signal_ids=["p1"])
    claims = CLAIMS + [cl("q115", "Claude", "pretzel_crust", "$8.99", "Outdated", old_price, None)]
    issues = build(moments=MOMENTS + [pretzel], claims=claims)
    assert not [x for x in issues if x["issue_type"] == "moment_gap" and x["moment_id"] == "mo_pretzel"]
    i = one(issues, issue_type="outdated", subject="pretzel_crust")
    assert i["prompt_ids"] == ["q115"] and i["stated_fact_id"] == old_price
    assert one(issues, issue_type="moment_gap")["moment_id"] == "mo_goff"   # available items keep their moment gap



# Ruling S2-D (smoke 2 F-S2-3): rule 2 counts only claims on the stale fact's attribute (Unverifiable alias hits do not
# count), and a rule 1 issue on the same owned page and fact absorbs the jsonld asset: one issue per stale page.
def _unverifiable(pid, attribute):
    return dict(prompt_id=pid, engine="Claude", subject="classic_pepperoni", attribute=attribute, stated_value=None,
                tag="Unverifiable", fact_id=None, source_doc_id=None)

def test_stale_page_counts_only_price_claims_not_unverifiable_alias_hits():
    claims = CLAIMS + [_unverifiable("q201", "ordering"), _unverifiable("q115", "price"), _unverifiable("q062", None)]
    i = one(build(claims=claims), issue_type="outdated", source_doc_id="lce_pg_item_classic_pepperoni")
    assert i["prompt_ids"] == ["q002"] and i["engines"] == ["Claude"]
    only_alias = [c for c in CLAIMS if c["subject"] != "classic_pepperoni"] + [_unverifiable("q201", "ordering")]
    assert not [x for x in build(claims=only_alias) if x["source_doc_id"] == "lce_pg_item_classic_pepperoni"]

def test_owned_stale_claim_and_stale_page_make_one_issue_with_t0_jsonld():
    owned = [cl("q002", e, "classic_pepperoni", "$5", "Outdated", "F04", "lce_pg_item_classic_pepperoni") for e in ("Claude", "ChatGPT")]
    issues = build(claims=CLAIMS + owned)
    i = one(issues, source_doc_id="lce_pg_item_classic_pepperoni")   # exactly one issue for the page
    assert i["issue_type"] == "outdated" and i["fact_id"] == "F03" and i["stated_fact_id"] == "F04" and i["prompt_ids"] == ["q002"]
    assert [(f["asset_type"], f["page_id"], f["section_id"], f["op"]) for f in i["planned"]] == [
        ("owned_patch", "pg_item_classic_pepperoni", None, "replace"), ("jsonld", "pg_item_classic_pepperoni", "jsonld", "replace")]
    assert i["claim_keys"] == [claim_key("Outdated", "lce_pg_item_classic_pepperoni", "classic_pepperoni", "price")]
    from geologic.datagen.answer_key import ANSWER_KEY
    from geologic.tiering import assign_tier
    key = ANSWER_KEY["classic_pepperoni"]
    hits = [x for x in issues if x["issue_type"] == key["issue_type"] and x["source_doc_id"] == key["source_doc_id"]]
    assert [assign_tier(f["asset_type"], names_person=False, checks_ok=True) for f in hits[0]["planned"]
            if f["asset_type"] in key["fixes"]] == ["T0"]


def test_item_linked_moments_gap_only_where_engines_miss_and_never_for_a_discontinued_item():   # Ruling S2-F
    from geologic.datagen.reference import menu_items
    from geologic.moments import link_moment
    prompts = P + [dict(prompt_id="q057", prompt_text="What is Detroit-style pizza at Little Caesars?", cluster="product",
                        priority="Silver", branded=True),
                   dict(prompt_id="q300", prompt_text="Is the pretzel crust pizza back?", cluster="product", priority="Gold",
                        branded=False)]
    answers = ANS + [ans("q057", e, True, ["lce_pg_deals_game_day"]) for e in ENG] + [ans("q300", e) for e in ENG]
    goff = {**MOMENTS[0], "prompt_ids": []}
    goff["prompt_ids"], _ = link_moment(goff, [], lambda t, k=5: [], 0.80, prompts, menu_items())
    assert goff["prompt_ids"] == ["q057", "q202"]
    pretzel = dict(moment_id="mo_pretzel", kind="trend", title="Pretzel Crust Pepperoni is trending", persona_id=None,
                   item_id="pretzel_crust", signal_ids=["p1"], prompt_ids=[])
    pretzel["prompt_ids"], _ = link_moment(pretzel, [], lambda t, k=5: [], 0.80, prompts, menu_items())
    assert pretzel["prompt_ids"] == ["q300"]
    issues = build(prompts=prompts, answers=answers, moments=[goff, pretzel])
    gap = one(issues, issue_type="moment_gap")
    assert gap["moment_id"] == "mo_goff" and gap["prompt_ids"] == ["q202"]   # q057 names LCE on every engine: no gap
    assert not [x for x in issues if x.get("moment_id") == "mo_pretzel"]
