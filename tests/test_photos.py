from geologic.photos import credit_for

def test_credit_for_real_photo():
    assert credit_for("/Volumes/jdub_demo/geologic/assets/signals/kittle_tailgate.png") == "Photo: Valereee, CC BY-SA 4.0"

def test_credit_for_press_photo():
    assert credit_for("/Volumes/x/signals/goff_slices_n_stix.jpg") == "Photo: Courtesy of Little Caesars"

def test_retired_athlete_photos_have_no_credit():
    for f in ("barkley_press.jpg", "jefferson_press.jpg", "kittle_radio_row.jpg"):
        assert credit_for(f"/Volumes/x/signals/{f}") is None

def test_no_credit_for_drawn_or_missing():
    assert credit_for("/Volumes/x/signals/bg_1.png") is None and credit_for(None) is None
