"""Signals streamed through Zerobus into bronze_signals."""
from __future__ import annotations
import json
import random
import uuid
from datetime import datetime

SEEDED = ("S3_kittle", "S4_exclusion", "S5_pretzel", "S5_puffs", "S7_crawler")
_IMG = "/Volumes/jdub_demo/geologic/assets/signals/{}.png"

def _row(source_type, payload, now, image_uri=None, producer="background"):
    return dict(signal_id=str(uuid.uuid4()), source_type=source_type, payload=json.dumps(payload),
                image_uri=image_uri, ingested_at=now, producer=producer)

def seeded_signal(truth_id: str, now: datetime) -> dict:
    if truth_id == "S3_kittle":
        return _row("athlete_post", {"author": "George Kittle", "author_persona_id": "p_kittle", "reach": 2_100_000,
                    "text": "Tailgate fuel before kickoff. That corner piece though."}, now, _IMG.format("kittle_tailgate"), "seeded")
    if truth_id == "S4_exclusion":
        return _row("social", {"author": "@sportsdesk", "author_persona_id": "p_fictional_dax", "reach": 900_000,
                    "text": "Dax Merriwether trending after arrest report; fans post Little Caesars memes."}, now, None, "seeded")
    if truth_id == "S5_pretzel":
        return _row("social", {"author": "r/nfl", "reach": 6400, "velocity": 7.9,
                    "text": "Remember when the Hot-N-Ready Pretzel Crust was a thing? Bring it back for playoffs."}, now, None, "seeded")
    if truth_id == "S5_puffs":
        return _row("social", {"author": "r/fastfood", "reach": 1800, "velocity": 4.2,
                    "text": "Crazy Puffs are the most underrated thing on any pizza menu."}, now, None, "seeded")
    if truth_id == "S7_crawler":
        return _row("crawler_hit", {"author": "PerplexityBot", "bot": "PerplexityBot", "page": "/order", "hits": 0, "reach": 0,
                    "text": "PerplexityBot has not fetched /order in 30 days."}, now, None, "seeded")
    raise ValueError(f"unknown truth_id {truth_id}")

_BG_TEXT = [
    ("social", "Crazy Bread and a Hot-N-Ready for the game tonight."),
    ("social", "Hot take: Detroit-style Deep!Deep! Dish beats every other chain's pan pizza."),
    ("social", "Draft party math: one pizza per 3 people."),
    ("review", "Pickup was fast with Pizza Portal."),
    ("review", "Caesar Wings were cold this time."),
    ("crawler_hit", "GPTBot fetched /menu."),
]
_REAL = [("Justin Jefferson", "p_jefferson", "Thursday night. Crazy Bread count: yes."),
         ("Jared Goff", "p_goff", "Pregame Hot-N-Ready with the family."),
         ("Saquon Barkley", "p_barkley", "Pizza night after practice.")]

def background_signal(rng: random.Random, now: datetime) -> dict:
    roll = rng.random()
    if roll < 0.08:
        name, pid, text = rng.choice(_REAL)
        return _row("athlete_post", {"author": name, "author_persona_id": pid, "reach": rng.randint(1_000_000, 4_000_000), "text": text},
                    now, _IMG.format(f"bg_{rng.randint(1, 5)}"))
    st, text = rng.choice(_BG_TEXT)
    payload = {"author": f"user{rng.randint(100, 9999)}", "reach": rng.randint(10, 5000), "text": text}
    if st == "crawler_hit":
        payload.update(bot=rng.choice(["GPTBot", "PerplexityBot", "ClaudeBot"]), page="/menu", hits=rng.randint(1, 40))
    return _row(st, payload, now)
