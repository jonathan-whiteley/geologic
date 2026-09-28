from geologic.datagen.reference import menu_items
from geologic.jsonld import validate

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
