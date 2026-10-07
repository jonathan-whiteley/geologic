"""Asserts the seeded truths S1-S7 against live state."""
from geologic.datagen.answer_key import ANSWER_KEY as K


def _opp(state, **match):
    return next((o for o in state["opps"] if all(o.get(k) == v for k, v in match.items())), None)


def _tiers(state, opp_type, page_id):
    return sorted({s["tier"] for s in state["suggestions"] if s.get("opp_type") == opp_type and s["page_id"] == page_id})


def check(state) -> list[str]:
    f = []
    for sid in ("S1", "S2", "S7"):
        k = K[sid]
        if not _opp(state, opp_type=k["opp_type"], page_id=k["page_id"]):
            f.append(f"{sid}: no {k['opp_type']} opportunity for {k['page_id']}")
        elif _tiers(state, k["opp_type"], k["page_id"]) != sorted(k["tiers"]):
            f.append(f"{sid}: tiers {_tiers(state, k['opp_type'], k['page_id'])} != {sorted(k['tiers'])}")
    s6 = _opp(state, opp_type="content_gap", cluster="sponsorship")
    if not s6:
        f.append("S6: no sponsorship content gap")
    elif _tiers(state, "content_gap", s6["page_id"]) != sorted(K["S6"]["tiers"]):
        f.append(f"S6: tiers {_tiers(state, 'content_gap', s6['page_id'])} != {sorted(K['S6']['tiers'])}")
    k3 = K["S3"]
    s3 = _opp(state, opp_type=k3["opp_type"], item_id=k3["item_id"], persona_id=k3["persona_id"])
    if not s3:
        f.append(f"S3: no persona_moment for {k3['persona_id']} and {k3['item_id']}")
    elif _tiers(state, "persona_moment", s3["page_id"]) != sorted(k3["tiers"]):
        f.append("S3: persona moment is not T2")
    ex = [s for s in state["signals"] if s.get("producer") == "seeded" and s.get("persona_id") == "p_fictional_dax"]
    if not ex or not all(s["quarantined"] and s["quarantine_rule_id"] == K["S4"]["rule_id"] for s in ex):
        f.append("S4: excluded signal not quarantined by EX-01")
    points = {a["enforcement_point"] for a in state["audits"] if a.get("exclusion_rule_id") == K["S4"]["rule_id"]}
    f += [f"S4: no audit event at {p}" for p in K["S4"]["enforcement_points"] if p not in points]
    ex_ids = {s["signal_id"] for s in ex}
    if ex_ids & state["public_signal_ids"]:
        f.append("S4: quarantined signal visible in public signals")
    if any(ex_ids & set(o.get("signal_ids") or []) for o in state["opps"]):
        f.append("S4: quarantined signal feeds an opportunity")
    hi, lo = _opp(state, item_id=K["S5"]["higher_item"]), _opp(state, item_id=K["S5"]["lower_item"])
    if not hi or not lo or hi["rank"] >= lo["rank"]:
        f.append("S5: Crazy Puffs does not outrank Pretzel Crust")
    for key, sid in (("accuracy_by_run", "S1"), ("share_by_run", "S2")):
        v = state.get(key)
        if v and v.get("baseline") is not None and v.get("latest") is not None and v["latest"] <= v["baseline"]:
            f.append(f"{sid}: metric did not improve after publish ({v['baseline']:.2f} -> {v['latest']:.2f})")
    return f
