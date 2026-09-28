"""Long-tail candidate prompts, monthly question volume, and sentiment themes for the Prompt Explorer."""
from __future__ import annotations
import hashlib
from datetime import date

THEMES = ("value", "speed_convenience", "quality", "deals_app", "game_day")
THEME_LABELS = {"value": "Value", "speed_convenience": "Speed and convenience", "quality": "Quality",
                "deals_app": "Deals and app", "game_day": "Game day"}

_CANDIDATES = {
    "value": ["Little Caesars prices 2026", "How much is a Little Caesars party pack?", "Little Caesars deals today",
              "Is Hot-N-Ready available late at night?"],
    "game_day_party": ["Pizza for a fantasy draft party", "How many pizzas for 30 people?", "Best game day food delivery",
                       "How much pizza for a Super Bowl party of 15?"],
    "sponsorship": ["Who sponsors the NFL for pizza?", "Little Caesars NFL commercial", "George Kittle pizza ad"],
    "product": ["What do Crazy Puffs taste like?", "Little Caesars Detroit style review", "Best Little Caesars pizza to order"],
    "ordering": ["How does Little Caesars Pizza Portal work?", "Little Caesars order ahead app"],
    "dietary": ["Little Caesars vegan options", "Little Caesars calories per slice"],
    "comparison": ["Little Caesars or Domino's for a party", "Best pizza chain wings 2026"],
}
_BASE = {"product": 500, "value": 700, "comparison": 400, "ordering": 300, "dietary": 250, "game_day_party": 600, "sponsorship": 200}
_NFL = {"game_day_party", "sponsorship", "value"}
_SEASON = {9: 1.15, 10: 1.1, 11: 1.15, 12: 1.2, 1: 1.25, 2: 1.6, 3: 0.8, 4: 0.7, 5: 0.7, 6: 0.72, 7: 0.78, 8: 1.0}

def prompt_candidates() -> list[dict]:
    rows, n = [], 1
    for cluster, texts in _CANDIDATES.items():
        for t in texts:
            rows.append(dict(prompt_id=f"c{n:03d}", prompt_text=t, cluster=cluster, base_volume=_BASE[cluster], calendar_tags=[]))
            n += 1
    return rows

def _months_back(end: date, n: int) -> list[date]:
    out, y, m = [], end.year, end.month
    for _ in range(n):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))

def monthly_volume(prompt: dict, end_month: date) -> list[dict]:
    base = prompt["base_volume"] * 10
    rows = []
    for m in _months_back(end_month, 12):
        season = _SEASON[m.month] if prompt["cluster"] in _NFL else 1.0
        h = int(hashlib.sha1(f"{prompt['prompt_id']}|{m}".encode()).hexdigest(), 16)
        noise = 1 + ((h % 11) - 5) / 100          # deterministic +/- 5%
        rows.append(dict(prompt_id=prompt["prompt_id"], month=m, est_volume=int(round(base * season * noise))))
    return rows
