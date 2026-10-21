import pytest
from geologic.datagen.reference import menu_items
from geologic.facts import parse_price, resolve_item

MENU = menu_items()

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

def test_resolve_item_longest_alias_match():
    assert resolve_item("How much is the stuffed crazy bread with extra cheese", MENU)["item_id"] == "stuffed_crazy_bread"
