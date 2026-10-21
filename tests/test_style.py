from geologic.style import clean_dashes

def test_clean_dashes_keeps_ranges_and_drops_stray_punctuation():  # moved with _clean from agents/strategist.py
    em, en = "\u2014", "\u2013"
    assert clean_dashes(f"Fast {em} and fresh") == "Fast, and fresh" and clean_dashes(f"3{en}4 adults") == "3-4 adults"
    assert clean_dashes(f"Hot and ready {em}.") == "Hot and ready." and clean_dashes(f"Line one {en}\n{em} line two") == "Line one\nline two"
    js = '{"a": 1, "b": 2}'
    assert clean_dashes(js) == js and clean_dashes(None) is None
