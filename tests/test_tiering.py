from geologic.tiering import assign_tier

def test_tiers_by_code():
    assert assign_tier("jsonld", names_person=False, checks_ok=True) == "T0"
    assert assign_tier("jsonld", names_person=False, checks_ok=False) == "T1"
    for a in ("owned_patch", "answer_page", "moment_page"):
        assert assign_tier(a, names_person=False, checks_ok=True) == "T1"
        assert assign_tier(a, names_person=True, checks_ok=True) == "T2"
    for a in ("association", "correction_email", "community_reply", "mystery"):
        assert assign_tier(a, names_person=False, checks_ok=True) == "T2"
