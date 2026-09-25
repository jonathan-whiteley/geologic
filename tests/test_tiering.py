import pytest
from geologic.tiering import assign_tier

def t(asset, **kw):
    base = dict(touches_persona=False, visual_sourced=False, exclusion_hit=False)
    base.update(kw)
    return assign_tier(asset, **base)

@pytest.mark.parametrize("asset,expected", [("jsonld", "T0"), ("alt_text", "T0"), ("facts", "T0"),
                                            ("faq", "T1"), ("description", "T1"), ("mystery", "T2")])
def test_base_tiers(asset, expected):
    assert t(asset) == expected

def test_exclusion_beats_everything():
    assert t("jsonld", exclusion_hit=True, touches_persona=True) == "BLOCKED"

def test_persona_or_visual_forces_t2():
    assert t("jsonld", touches_persona=True) == "T2"
    assert t("alt_text", visual_sourced=True) == "T2"

def test_invalid_jsonld_bumps_to_t1():
    assert t("jsonld", jsonld_valid=False) == "T1"

def test_low_confidence_never_auto_publishes():
    assert t("jsonld", resolution_confidence=0.5) == "T1"
    assert t("faq", resolution_confidence=0.5) == "T1"
