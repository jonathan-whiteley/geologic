import pytest
from geologic.datagen.reference import menu_items, deals
from geologic.facts import parse_price, resolve_item, verify_claims, accuracy_score

MENU, DEALS = menu_items(), deals()

@pytest.mark.parametrize("raw,val", [("$6.49", 6.49), ("6.49 dollars", 6.49), ("$5", 5.0), (5, 5.0),
                                     ("five dollars", 5.0), ("five bucks", 5.0), ("USD 4.99", 4.99)])
def test_parse_price(raw, val):
    assert parse_price(raw) == val

@pytest.mark.parametrize("raw", [None, "", "cheap", "varies by location"])
def test_parse_price_unparseable(raw):
    assert parse_price(raw) is None

def test_resolve_item_by_alias():
    assert resolve_item("Hot-N-Ready", MENU)["item_id"] == "classic_pepperoni"
    assert resolve_item("deep deep dish", MENU)["item_id"] == "detroit_pepperoni"
    assert resolve_item("mystery pie", MENU) is None

def test_verify_claims():
    out = verify_claims([{"item": "Hot-N-Ready", "price": "$5"},
                         {"item": "Hot-N-Ready", "price": "$6.49"},
                         {"item": "Hot-N-Ready", "price": "$4.99"},          # matches gameday deal
                         {"item": "Mystery Pie", "price": "$9"},
                         {"item": "Crazy Bread", "price": "cheap"}], MENU, DEALS)
    assert [c["verdict"] for c in out] == ["wrong", "correct", "correct", "unverifiable", "unverifiable"]
    assert accuracy_score(out) == pytest.approx(2 / 3)

def test_accuracy_none_when_nothing_checkable():
    assert accuracy_score([{"verdict": "unverifiable"}]) is None

def test_resolve_item_longest_alias_match():
    assert resolve_item("How much is the stuffed crazy bread with extra cheese", MENU)["item_id"] == "stuffed_crazy_bread"

def test_verify_claims_deal_price_pizza_only():
    out = verify_claims([{"item": "Crazy Bread", "price": "$4.99"}], MENU, DEALS)
    assert out[0]["verdict"] == "wrong"
