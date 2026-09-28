from datetime import date
from geologic.datagen.reference import prompt_bank
from geologic.datagen.prompts_ext import prompt_candidates, monthly_volume, THEMES, THEME_LABELS

def test_candidates_are_new_and_unique():
    bank = {p["prompt_text"].lower() for p in prompt_bank()}
    c = prompt_candidates()
    assert len(c) >= 20 and len({x["prompt_id"] for x in c}) == len(c)
    assert all(x["prompt_id"].startswith("c") for x in c)
    assert not any(x["prompt_text"].lower() in bank for x in c)

def test_monthly_volume_shape_and_seasonality():
    party = next(p for p in prompt_bank() if p["cluster"] == "game_day_party")
    rows = monthly_volume(party, date(2026, 9, 1))
    assert len(rows) == 12 and rows[-1]["month"] == date(2026, 9, 1) and rows[0]["month"] == date(2025, 10, 1)
    by = {r["month"].month: r["est_volume"] for r in rows}
    assert by[2] > 1.8 * by[6]                     # Super Bowl spike vs. offseason

def test_monthly_volume_flat_for_non_nfl_cluster():
    diet = next(p for p in prompt_bank() if p["cluster"] == "dietary")
    vals = [r["est_volume"] for r in monthly_volume(diet, date(2026, 9, 1))]
    assert max(vals) / min(vals) < 1.15

def test_monthly_volume_deterministic():
    p = prompt_bank()[0]
    assert monthly_volume(p, date(2026, 9, 1)) == monthly_volume(p, date(2026, 9, 1))

def test_theme_labels():
    assert set(THEME_LABELS) == set(THEMES)
