import pytest
from geologic.publish import next_page_version

PAGE = {"page_id": "p", "body": "old", "jsonld": None, "version": 3}

def test_faq_replaces_body():
    new = next_page_version(PAGE, {"asset_type": "faq", "diff_after": "new body", "tier": "T1", "state": "approved"})
    assert new["body"] == "new body" and new["version"] == 4 and PAGE["version"] == 3

def test_jsonld_replaces_jsonld():
    new = next_page_version(PAGE, {"asset_type": "jsonld", "diff_after": "{}", "tier": "T0", "state": "auto_published"})
    assert new["jsonld"] == "{}" and new["has_valid_jsonld"] is True and new["body"] == "old"

@pytest.mark.parametrize("s", [{"tier": "BLOCKED", "state": "approved"}, {"tier": "T1", "state": "pending_review"}])
def test_refuses(s):
    with pytest.raises(ValueError):
        next_page_version(PAGE, {"asset_type": "faq", "diff_after": "x", **s})
