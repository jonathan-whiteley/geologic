import copy
from geologic.datagen.reference import personas
from geologic.harness import check

GOFF_SIG, REPOST = "sig_goff", "sig_repost"
OK = [{"key": "grounded", "ok": True, "label": "g"}, {"key": "unsupported", "ok": True, "label": "u"}]


def issue(iid, issue_type, **k):
    return {"issue_id": iid, "issue_type": issue_type, "prompt_ids": ["q201"], "source_doc_id": None, "source_doc_ids": [],
            "subject": None, "cluster": None, "moment_id": None, "fact_id": None, "stated_fact_id": None, **k}


def fix(fid, iid, asset, tier, text="Plain copy."):
    return {"fix_id": fid, "issue_id": iid, "asset_type": asset, "tier": tier, "state": "pending_review", "patch_text": text,
            "checks": list(OK)}


def good_state():
    return {
        "kpis": {"tracked_prompts": 30, "engines": 4, "answers": 120},
        "issues": [
            issue("is_pp", "outdated", source_doc_id="editorial_superbowl_roundup_2024", subject="party_pack", fact_id="F12",
                  stated_fact_id="F13"),
            issue("is_gl", "missing_us", source_doc_id="review_pizzahut_gameday_top", source_doc_ids=["review_pizzahut_gameday_top"]),
            issue("is_cp", "outdated", source_doc_id="lce_pg_item_classic_pepperoni", subject="classic_pepperoni"),
            issue("is_rd", "wrong", source_doc_id="reddit_pizza_hnr", subject="classic_pepperoni"),
            issue("is_cm", "no_answer_page", cluster="comparison"),
            issue("is_gm", "moment_gap", moment_id="m_goff", prompt_ids=["q202"]),
        ],
        "fixes": [fix("fx_1", "is_pp", "correction_email", "T2"), fix("fx_2", "is_pp", "owned_patch", "T1"),
                  fix("fx_3", "is_gl", "answer_page", "T1"), fix("fx_4", "is_cp", "jsonld", "T0", '{"@type":"MenuItem"}'),
                  fix("fx_5", "is_rd", "community_reply", "T2"), fix("fx_6", "is_cm", "answer_page", "T1"),
                  fix("fx_7", "is_gm", "moment_page", "T1", "## Deep dish\nSquare deep dish for the game."),
                  fix("fx_8", "is_gm", "association", "T2", "Jared Goff loves the corner piece.")],
        "moments": [{"moment_id": "m_goff", "persona_id": "p_goff", "item_id": "detroit_pepperoni", "prompt_ids": ["q202"],
                     "signal_ids": [GOFF_SIG]}],
        "signals": [{"signal_id": GOFF_SIG, "author": "Jared Goff", "producer": "seeded", "quarantined": False, "quarantine_rule_id": None},
                    {"signal_id": REPOST, "author": "@sidelinebets", "producer": "seeded", "quarantined": True, "quarantine_rule_id": "EX-03"}],
        "audits": [{"exclusion_rule_id": "EX-03", "enforcement_point": p, "object_ref": REPOST} for p in ("ingest", "suggest", "publish")],
        "public_signal_ids": {GOFF_SIG},
        "personas": personas(),
    }


def fails(mutate):
    s = copy.deepcopy(good_state())
    mutate(s)
    return check(s)


def has(msgs, prefix):
    return any(m.startswith(prefix) or prefix in m for m in msgs)


def test_good_state_passes():
    assert check(good_state()) == []


def test_missing_party_pack_issue():
    assert has(fails(lambda s: s["issues"].pop(0)), "party_pack: no matching issue")


def test_correction_email_at_t1():
    assert has(fails(lambda s: s["fixes"][0].update(tier="T1")), "party_pack: fixes")


def test_moment_page_naming_goff():
    assert has(fails(lambda s: s["fixes"][6].update(patch_text="Jared Goff picked the deep dish.")), "names a person")


def test_repost_visible():
    assert has(fails(lambda s: s["public_signal_ids"].add(REPOST)), "sportsbook_repost: visible")


def test_issue_without_prompts():
    assert has(fails(lambda s: s["issues"].append(issue("is_x", "wrong", prompt_ids=[]))), "issue without prompts")


def test_answers_out_of_range():
    assert has(fails(lambda s: s["kpis"].update(answers=100)), "answers")


def test_story_fix_with_unsupported_claim():
    def m(s):
        s["fixes"][1]["checks"] = [OK[0], {"key": "unsupported", "ok": False, "label": "Unsupported claim: x"}]
    assert has(fails(m), "unsupported")


def test_missing_publish_audit_and_goff_link():
    msgs = fails(lambda s: (s["audits"].pop(), s["moments"][0].update(prompt_ids=["q201"])))
    assert "sportsbook_repost: no audit event at publish" in msgs and "goff_moment: moment not linked to q202" in msgs
