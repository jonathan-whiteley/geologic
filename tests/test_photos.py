from geologic.photos import credit_for

def test_credit_for_real_photo():
    from geologic.config import Settings
    settings = Settings()
    assert credit_for(f"{settings.volume_path}/signals/goff_slices_n_stix.jpg") == "Photo: Courtesy of Little Caesars"
    assert credit_for("/x/kittle_tailgate.png") is None

def test_credit_for_press_photo():
    assert credit_for("/Volumes/x/signals/goff_slices_n_stix.jpg") == "Photo: Courtesy of Little Caesars"

def test_retired_athlete_photos_have_no_credit():
    for f in ("barkley_press.jpg", "jefferson_press.jpg", "kittle_radio_row.jpg"):
        assert credit_for(f"/Volumes/x/signals/{f}") is None

def test_no_credit_for_drawn_or_missing():
    assert credit_for("/Volumes/x/signals/bg_1.png") is None and credit_for(None) is None


# Smoke 1 F3a: the images task must never overwrite a photo already in the volume (deploy.sh uploads the real press
# photo, which is gitignored and so never reaches the bundle); it draws a placeholder only when the file is absent.
from geologic.photos import place_photo

def _draw_to(log):
    def draw(path):
        log.append(path)
        with open(path, "wb") as f:
            f.write(b"placeholder")
    return draw

def test_place_photo_keeps_existing_volume_file(tmp_path):
    local, vol, drawn = tmp_path / "local", tmp_path / "vol", []
    local.mkdir(); vol.mkdir()
    (local / "goff_slices_n_stix.jpg").write_bytes(b"bundle copy")
    (vol / "goff_slices_n_stix.jpg").write_bytes(b"real photo")
    assert place_photo("goff_slices_n_stix.jpg", str(local), str(vol), _draw_to(drawn)) == "kept"
    assert (vol / "goff_slices_n_stix.jpg").read_bytes() == b"real photo" and drawn == []

def test_place_photo_copies_local_then_draws_only_when_absent(tmp_path):
    local, vol, drawn = tmp_path / "local", tmp_path / "vol", []
    local.mkdir(); vol.mkdir()
    (local / "photo.jpg").write_bytes(b"cc photo")
    assert place_photo("photo.jpg", str(local), str(vol), _draw_to(drawn)) == "copied"
    assert (vol / "photo.jpg").read_bytes() == b"cc photo"
    assert place_photo("goff_slices_n_stix.jpg", str(local), str(vol), _draw_to(drawn)) == "placeholder"
    assert drawn == [str(vol / "goff_slices_n_stix.jpg")]
