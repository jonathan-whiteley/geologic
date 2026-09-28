from geologic.brands import brand_for_doc, BRANDS, LOGOS

def test_brand_for_doc():
    assert brand_for_doc({"is_official": True, "publisher": "littlecaesars.com"}) == "Little Caesars"
    assert brand_for_doc({"is_official": False, "publisher": "dominos.com"}) == "Domino's"
    assert brand_for_doc({"is_official": False, "publisher": "r/pizza"}) is None

def test_logos_cover_brands():
    assert set(LOGOS) == set(BRANDS)
