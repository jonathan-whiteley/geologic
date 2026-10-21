from datetime import date
from geologic.datagen.reference import brand_facts, menu_items, site_pages
from geologic.jsonld import build_for_page, validate, validate_against_facts

MENU = menu_items()
GOOD = '{"@context":"https://schema.org","@type":"MenuItem","name":"Classic Pepperoni Hot-N-Ready","offers":{"@type":"Offer","price":"6.49","priceCurrency":"USD"}}'

def test_valid():
    assert validate(GOOD, MENU) == []

def test_bad_json():
    assert validate("{not json", MENU) == ["invalid JSON"]

def test_wrong_price_and_currency():
    bad = GOOD.replace('"6.49"', '"5.00"').replace("USD", "EUR")
    errs = validate(bad, MENU)
    assert "offer price 5.00 does not match menu price 6.49" in errs
    assert "priceCurrency must be USD" in errs

def test_unknown_type():
    assert validate({"@type": "Recipe"}, MENU) == ["unsupported @type Recipe"]

def test_faq_page_ok():
    assert validate({"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": "Q", "acceptedAnswer": {"@type": "Answer", "text": "A"}}]}, MENU) == []

def test_none_is_error():
    assert validate(None, MENU) == ["missing JSON-LD"]


def test_build_for_item_page_uses_the_current_fact():
    page = next(p for p in site_pages() if p["page_id"] == "pg_item_party_pack")
    d = build_for_page(page, brand_facts(), date(2026, 10, 21))
    assert d["patch"]["section_id"] == "jsonld" and d["patch"]["op"] == "replace"
    assert '"price":"29.99"' in d["patch"]["text"] and d["sentences"][0]["fact_ids"] == ["F12"]
    assert validate_against_facts(d["patch"]["text"], brand_facts(), date(2026, 10, 21)) == []

def test_build_for_deals_page_is_an_organization_offer():
    page = next(p for p in site_pages() if p["page_id"] == "pg_deals_game_day")
    d = build_for_page(page, brand_facts(), date(2026, 10, 21))
    assert '"@type":"Organization"' in d["patch"]["text"] and '"price":"4.99"' in d["patch"]["text"]

def test_stale_price_fails_validation():
    stale = '{"@context":"https://schema.org","@type":"MenuItem","name":"Game Day Party Pack","offers":{"@type":"Offer","price":"24.99","priceCurrency":"USD"}}'
    assert validate_against_facts(stale, brand_facts(), date(2026, 10, 21))
