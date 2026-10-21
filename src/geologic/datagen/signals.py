"""Signals streamed through Zerobus into bronze_signals."""
from __future__ import annotations
import json
import random
import uuid
from datetime import datetime

SEEDED = ("S3_goff", "S4_repost", "S5_pretzel", "S5_puffs")


def _img(name: str) -> str:
    from geologic.config import settings
    return f"{settings.volume_path}/signals/{name}"


def _row(source_type, payload, now, image_uri=None, producer="background"):
    return dict(signal_id=str(uuid.uuid4()), source_type=source_type, payload=json.dumps(payload),
                image_uri=image_uri, ingested_at=now, producer=producer)

def seeded_signal(truth_id: str, now: datetime) -> dict:
    if truth_id == "S3_goff":
        return _row("athlete_post", {"author": "Jared Goff", "author_persona_id": "p_goff", "reach": 1_600_000,
                    "text": "Detroit-style is back before kickoff. Corner piece is mine."}, now, _img("goff_slices_n_stix.jpg"), "seeded")
    if truth_id == "S4_repost":   # sportsbook repost of the Goff moment; quarantined at ingest by EX-03, never shown
        return _row("social", {"author": "@sidelinebets", "reach": 240_000, "velocity": 6.5,
                    "text": "Corner piece energy before kickoff. Same-game parlay boost on Detroit tonight, odds in bio. "
                            "Gambling problem? Call 1-800-GAMBLER."}, now, None, "seeded")
    if truth_id == "S5_pretzel":
        return _row("social", {"author": "r/nfl", "reach": 6400, "velocity": 7.9,
                    "text": "Remember when the Hot-N-Ready Pretzel Crust was a thing? Bring it back for playoffs."}, now, None, "seeded")
    if truth_id == "S5_puffs":
        return _row("social", {"author": "r/fastfood", "reach": 1800, "velocity": 4.2,
                    "text": "Crazy Puffs are the most underrated thing on any pizza menu."}, now, None, "seeded")
    raise ValueError(f"unknown truth_id {truth_id}")

_BG_TEXT = [
    ("social", "Crazy Bread and a Hot-N-Ready for the game tonight."),
    ("social", "Hot take: Detroit-style Deep!Deep! Dish beats every other chain's pan pizza."),
    ("social", "Draft party math: one pizza per 3 people."),
    ("review", "Pickup was fast with Pizza Portal."),
    ("review", "Caesar Wings were cold this time."),
    ("crawler_hit", "GPTBot fetched /menu."),
]

def background_signal(rng: random.Random, now: datetime) -> dict:
    # Background chatter only: no athlete posts (Jared Goff appears only in the seeded S3 moment).
    st, text = rng.choice(_BG_TEXT)
    payload = {"author": f"user{rng.randint(100, 9999)}", "reach": rng.randint(10, 5000), "text": text}
    if st == "crawler_hit":
        payload.update(bot=rng.choice(["GPTBot", "PerplexityBot", "ClaudeBot"]), page="/menu", hits=rng.randint(1, 40))
    return _row(st, payload, now)
