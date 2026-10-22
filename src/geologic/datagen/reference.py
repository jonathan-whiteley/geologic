"""Reference data for GEOlogic. Product names are real LCE items; prices and margins are synthetic."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone

CLUSTERS = ["product", "value", "comparison", "ordering", "dietary", "game_day_party", "sponsorship"]
# Human labels for cluster keys, same as the UI (app/frontend/src/components/Heatmap.tsx CLUSTERS).
CLUSTER_LABELS = {"product": "Product questions", "value": "Value and deals", "comparison": "Comparisons",
                  "ordering": "Ordering / Pizza Portal", "dietary": "Dietary", "game_day_party": "Game-day / party sizing",
                  "sponsorship": "Sponsorship (NFL)"}

SEEDED_PAGE_IDS = {
    "hot_n_ready": "pg_item_classic_pepperoni",
    "game_day": "pg_deals_game_day",
    "order": "pg_order",
    "detroit": "pg_item_detroit_pepperoni",
    "about_nfl": "pg_about",
}

# item_id, name, category, price, margin_pct, available, is_lto, dietary_flags, aliases, visual
# visual: how the item looks (shape, crust and toppings only, no setting words)
# Only classic_pepperoni carries the Hot-N-Ready name (smoke 1 F2: a "Classic Cheese Hot-N-Ready" page out-ranked the stale
# Classic Pepperoni page for q002, so the stale-page and Reddit price stories never reproduced).
_MENU = [
    ("classic_pepperoni", "Classic Pepperoni Hot-N-Ready", "pizza", 6.49, 0.34, True, False, [], ["hot-n-ready", "hot n ready", "classic pepperoni"], "round pizza, pepperoni toppings"),
    ("classic_cheese", "Classic Cheese Pizza", "pizza", 6.49, 0.36, True, False, ["vegetarian"], ["classic cheese"], "round pizza, cheese topping"),
    ("emb_pepperoni", "ExtraMostBestest Pepperoni", "pizza", 7.99, 0.33, True, False, [], ["extramostbestest", "extra most bestest"], "round pizza, extra pepperoni toppings"),
    ("emb_cheese", "ExtraMostBestest Cheese", "pizza", 7.99, 0.35, True, False, ["vegetarian"], [], "round pizza, extra cheese topping"),
    ("three_meat", "3 Meat Treat", "pizza", 10.99, 0.31, True, False, [], ["3 meat treat", "three meat treat"], "round pizza, mixed meat toppings"),
    ("ultimate_supreme", "Ultimate Supreme", "pizza", 10.99, 0.30, True, False, [], ["supreme"], "round pizza, vegetable and meat toppings"),
    ("hula_hawaiian", "Hula Hawaiian", "pizza", 10.49, 0.32, True, False, [], ["hawaiian"], "round pizza, pineapple and ham toppings"),
    ("veggie", "Veggie", "pizza", 10.49, 0.33, True, False, ["vegetarian"], ["veggie pizza"], "round pizza, vegetable toppings"),
    ("detroit_pepperoni", "Detroit-Style Deep!Deep! Dish Pepperoni", "pizza", 11.99, 0.38, True, False, [], ["deep deep dish", "deep!deep! dish", "detroit-style", "detroit style"], "square pan pizza, thick deep-dish style crust, crispy caramelized cheese edges, pepperoni toppings"),
    ("detroit_cheese", "Detroit-Style Deep!Deep! Dish Cheese", "pizza", 11.49, 0.39, True, False, ["vegetarian"], [], "square pan pizza, thick deep-dish style crust, crispy caramelized cheese edges, cheese topping"),
    ("stuffed_crust", "Stuffed Crust Pepperoni", "pizza", 9.99, 0.32, True, False, [], ["stuffed crust"], "round pizza, thick stuffed crust edge, pepperoni"),
    ("thin_crust", "Thin Crust Pepperoni", "pizza", 7.49, 0.34, True, False, [], ["thin crust"], "round pizza, thin crispy crust, pepperoni"),
    ("pretzel_crust", "Pretzel Crust Pepperoni", "pizza", 8.99, 0.29, False, True, [], ["pretzel crust"], "round pizza, pretzel crust edge, pepperoni"),
    ("calzony", "Batman Calzony", "pizza", 9.49, 0.28, False, True, [], ["calzony"], "folded calzone pizza shape"),
    ("crazy_bread", "Crazy Bread", "sides", 3.99, 0.62, True, False, ["vegetarian"], ["crazy bread"], "breadsticks with garlic butter and parmesan"),
    ("crazy_combo", "Crazy Combo", "sides", 4.99, 0.60, True, False, ["vegetarian"], ["crazy combo"], "breadsticks with dipping sauce"),
    ("stuffed_crazy_bread", "Stuffed Crazy Bread", "sides", 5.49, 0.55, True, False, ["vegetarian"], ["stuffed crazy bread"], "stuffed breadsticks filled with cheese"),
    ("italian_cheese_bread", "Italian Cheese Bread", "sides", 5.99, 0.52, True, False, ["vegetarian"], ["italian cheese bread", "cheese bread"], "flat cheese bread"),
    ("pepperoni_cheese_bread", "Pepperoni Cheese Bread", "sides", 6.49, 0.50, True, False, [], ["pepperoni cheese bread"], "flat bread with cheese and pepperoni"),
    ("crazy_puffs_pepperoni", "Crazy Puffs (Pepperoni)", "sides", 4.49, 0.58, True, False, [], ["crazy puffs"], "small puffed pastry bites with pepperoni filling"),
    ("crazy_puffs_cheese", "Crazy Puffs (4 Cheese)", "sides", 4.49, 0.59, True, False, ["vegetarian"], [], "small puffed pastry bites with cheese filling"),
    ("slices_n_stix", "Slices-N-Stix", "sides", 5.99, 0.50, True, False, ["vegetarian"], ["slices-n-stix", "slices n stix"], "pizza slices with breadsticks"),
    ("wings_oven", "Caesar Wings (Oven Roasted)", "wings", 7.99, 0.40, True, False, ["gluten_free_sauce"], ["caesar wings", "wings"], "chicken wings, oven roasted"),
    ("wings_bbq", "Caesar Wings (BBQ)", "wings", 7.99, 0.40, True, False, [], [], "chicken wings, barbecue sauce"),
    ("wings_buffalo", "Caesar Wings (Buffalo)", "wings", 7.99, 0.40, True, False, [], [], "chicken wings, buffalo sauce"),
    ("wings_garlic_parm", "Caesar Wings (Garlic Parmesan)", "wings", 7.99, 0.40, True, False, [], [], "chicken wings, garlic parmesan"),
    ("dip_garlic", "Buttery Garlic Caesar Dip", "dips", 0.99, 0.70, True, False, ["vegetarian"], ["garlic dip"], "garlic butter dipping sauce"),
    ("dip_jalapeno", "Cheezy Jalapeno Caesar Dip", "dips", 0.99, 0.70, True, False, ["vegetarian"], ["jalapeno dip"], "jalapeno cheese dipping sauce"),
    ("dip_ranch", "Ranch Caesar Dip", "dips", 0.99, 0.70, True, False, ["vegetarian"], ["ranch"], "ranch dipping sauce"),
    ("crazy_sauce", "Crazy Sauce", "dips", 1.29, 0.72, True, False, ["vegetarian", "vegan"], ["crazy sauce"], "tomato dipping sauce"),
    ("lunch_combo", "Lunch Combo", "combos", 5.99, 0.45, True, False, [], ["lunch combo"], "pizza slice with dipping sauce"),
    ("party_pack", "Game Day Party Pack", "combos", 29.99, 0.40, True, False, [], ["party pack"], "multiple pizzas and sides combo"),
]


def menu_items() -> list[dict]:
    from geologic.config import settings
    return [
        dict(item_id=i, name=n, category=c, price=p, margin_pct=m, available=a, is_lto=l,
             dietary_flags=list(d), image_uri=f"{settings.volume_path}/menu/{i}.png",
             aliases=list(al), visual=v)
        for (i, n, c, p, m, a, l, d, al, v) in _MENU
    ]


def deals() -> list[dict]:
    return [
        dict(deal_id="gameday_499", name="$4.99 Online Gameday Deal", price=4.99, channel="online", active=True),
        dict(deal_id="lunch_combo", name="Lunch Combo", price=5.99, channel="in_store", active=True),
    ]


_UPDATED = datetime(2026, 8, 1, tzinfo=timezone.utc)
_STALE = datetime(2025, 6, 1, tzinfo=timezone.utc)


def _page(page_id, url, page_type, item_id, body, jsonld=None, primary_subject=None, updated_at=_UPDATED):
    return dict(page_id=page_id, url=url, page_type=page_type, primary_item_id=item_id, body=body,
                jsonld=jsonld, has_valid_jsonld=jsonld is not None, version=1, updated_at=updated_at,
                primary_subject=primary_subject)


# v3 overrides for owned item pages; a key that is absent keeps the generated value.
# No owned page may say "Detroit" at baseline, so the Goff moment gap on q202 stays real.
_PARTY_PACK_JSONLD = ('{"@context":"https://schema.org","@type":"MenuItem","name":"Game Day Party Pack",'
                      '"offers":{"@type":"Offer","price":"24.99","priceCurrency":"USD"}}')   # stale: F13, not F12
# S1 (classic_pepperoni story): the Hot-N-Ready page still states the old $5 price (F04, valid to 2025-12-31) in its body
# and its JSON-LD, and was last updated before the current $6.49 price (F03). It must never state $6.49.
_HOT_N_READY_BODY = ("## Classic Pepperoni Hot-N-Ready\nHow much is a Little Caesars Hot-N-Ready pizza? "
                     "Hot-N-Ready Classic Pepperoni pizza, $5, ready when you walk in. No calling ahead, no waiting.")
_HOT_N_READY_JSONLD = ('{"@context":"https://schema.org","@type":"MenuItem","name":"Classic Pepperoni Hot-N-Ready",'
                       '"offers":{"@type":"Offer","price":"5.00","priceCurrency":"USD"}}')   # stale: F04, not F03
_ITEM_OVERRIDES = {
    "classic_pepperoni": dict(body=_HOT_N_READY_BODY, jsonld=_HOT_N_READY_JSONLD, updated_at=_STALE),
    "party_pack": dict(body="## Game Day Party Pack\nA bundle for groups. See the app for today's price.",
                       jsonld=_PARTY_PACK_JSONLD, updated_at=datetime(2025, 3, 1, tzinfo=timezone.utc)),
    "detroit_pepperoni": dict(body="## Deep!Deep! Dish Pepperoni\nSquare deep dish, pepperoni to the edge.",
                              jsonld=None, updated_at=_STALE),
    "detroit_cheese": dict(body="## Deep!Deep! Dish Cheese\nSquare deep dish, cheese to the edge."),
}


def site_pages() -> list[dict]:
    pages = []
    for m in menu_items():
        body = f"## {m['name']}\n{m['name']} from Little Caesars. ${m['price']:.2f} at most locations."
        if not m["available"]:
            body = f"## {m['name']}\nNo longer available."
        jsonld = (
            '{"@context":"https://schema.org","@type":"MenuItem","name":"%s","offers":{"@type":"Offer","price":"%.2f","priceCurrency":"USD"}}'
            % (m["name"], m["price"]) if m["available"] and m["category"] != "dips" else None
        )
        o = _ITEM_OVERRIDES.get(m["item_id"], {})
        body, jsonld, updated = o.get("body", body), o.get("jsonld", jsonld), o.get("updated_at", _UPDATED)
        slug = "hot-n-ready" if m["item_id"] == "classic_pepperoni" else m["item_id"].replace("_", "-")
        pages.append(_page(f"pg_item_{m['item_id']}", f"https://littlecaesars.com/menu/{slug}", "item",
                           m["item_id"], body, jsonld, primary_subject=m["item_id"], updated_at=updated))
    fixed = [
        ("pg_menu", "https://littlecaesars.com/menu", "menu", None, "## Menu\nPizza, sides, wings, dips, and combos."),
        ("pg_deals", "https://littlecaesars.com/deals", "deals", None, "## Deals\nSee current deals in the app."),
        # S2 + S6: thin game-day page, no sizing answer, sponsorship mentioned once
        ("pg_deals_game_day", "https://littlecaesars.com/deals/game-day", "deals", None,
         "## Game Day Deals\n$4.99 online during NFL games.\nOfficial Pizza Sponsor of the NFL.", None, "gameday_499", _STALE),
        # ordering page
        ("pg_order", "https://littlecaesars.com/order", "ordering", None, "## Order\nPick up with Pizza Portal."),
        ("pg_about", "https://littlecaesars.com/about", "about", None, "## About Little Caesars\nFounded in 1959 in Garden City, Michigan."),
        ("pg_faq", "https://littlecaesars.com/faq", "faq", None, "## FAQ\nQuestions about orders and the app."),
        ("pg_nutrition", "https://littlecaesars.com/nutrition", "faq", None, "## Nutrition\nNutrition and allergen information."),
        ("pg_app", "https://littlecaesars.com/app", "ordering", None, "## The Little Caesars App\nOrder ahead and skip the line."),
    ]
    pages += [_page(*f) for f in fixed]
    # Store-locator style pages to reach ~62 total
    # pg_loc_00 is Grand Rapids, not Detroit: no owned page may say "Detroit" at baseline (q202 gap).
    for i, city in enumerate(["Grand Rapids", "Chicago", "Dallas", "Phoenix", "Atlanta", "Denver", "Houston",
                              "Orlando", "Columbus", "Charlotte", "Minneapolis", "San Antonio", "Tampa",
                              "Las Vegas", "Nashville", "Kansas City", "Cleveland", "Indianapolis",
                              "Memphis", "Tucson", "Omaha", "Louisville"]):
        pages.append(_page(f"pg_loc_{i:02d}", f"https://littlecaesars.com/locations/{city.lower().replace(' ', '-')}",
                           "location", None, f"## Little Caesars {city}\nHot-N-Ready pizza near you in {city}."))
    return pages


def personas() -> list[dict]:
    # Jared Goff is the only athlete; no persona is excluded (exclusions attach to topics, never to a person).
    rows = [
        ("p_goff", "Jared Goff", True, "athlete", 1_600_000, False, True),
        ("p_creator_slicequeen", "SliceQueen", False, "creator", 480_000, False, False),
        ("p_creator_gridirongrub", "Gridiron Grub", False, "creator", 260_000, False, False),
    ]
    return [dict(persona_id=a, display_name=b, is_real=c, persona_type=d, reach=e, is_excluded=f, approved_for_association=g)
            for a, b, c, d, e, f, g in rows]


def exclusion_rules() -> list[dict]:
    rows = [
        ("EX-02", "topic", "politics", "No political association"),
        ("EX-03", "topic", "gambling", "No sports betting association"),
        ("EX-07", "topic", "arrest", "No association with legal incidents"),
        ("EX-09", "category", "alcohol", "No alcohol pairing"),
    ]
    return [dict(rule_id=a, object_type=b, object_ref=c, reason=d, active=True) for a, b, c, d in rows]


def demand_calendar(now: datetime) -> list[dict]:
    def w(wid, name, start_h, dur_h, mult, clusters):
        s = now + timedelta(hours=start_h)
        return dict(window_id=wid, name=name, start_ts=s, end_ts=s + timedelta(hours=dur_h),
                    volume_multiplier=mult, clusters_affected=clusters)
    return [
        w("fantasy_draft", "Fantasy draft season", -24 * 20, 24 * 30, 2.4, ["game_day_party"]),
        w("tnf", "Thursday Night Football", 31, 5, 1.8, ["game_day_party", "value", "sponsorship"]),
        w("sunday_slate", "Sunday slate", 24 * 4, 12, 2.0, ["game_day_party", "value", "sponsorship"]),
        w("super_bowl", "Super Bowl LXI", 24 * 139, 8, 4.0, ["game_day_party", "sponsorship"]),
    ]


_PROMPTS = {
    "product": ["What is on the Little Caesars menu?", "What is a Hot-N-Ready pizza?", "What is Detroit-style pizza at Little Caesars?",
                "What are Crazy Puffs?", "What comes with Crazy Bread?", "What wings does Little Caesars have?",
                "What is the ExtraMostBestest pizza?", "Does Little Caesars have stuffed crust?", "What dips does Little Caesars offer?",
                "What is Slices-N-Stix?", "Does Little Caesars still sell Pretzel Crust pizza?", "What is Italian Cheese Bread?"],
    "value": ["How much is a Little Caesars Hot-N-Ready pizza right now?", "What is the cheapest pizza chain?",
              "Best cheap pizza deal tonight", "How much is Crazy Bread?", "Does Little Caesars have a lunch deal?",
              "What pizza deals are there during NFL games?", "Cheapest large pepperoni pizza near me",
              "Is Little Caesars still five dollars?", "Best pizza deal for a family of four", "How much are Caesar Wings?"],
    "comparison": ["Little Caesars vs Domino's", "Is Little Caesars better than Pizza Hut?", "Best pizza chain for sides",
                   "Little Caesars vs Papa Johns wings", "Which pizza chain has the best breadsticks?",
                   "Best fast pizza chain for game day", "Domino's or Little Caesars for a party?", "Best snack sides at pizza chains"],
    "ordering": ["Can I order Little Caesars online?", "What is the Little Caesars Pizza Portal?", "Do I need to order ahead at Little Caesars?",
                 "Does Little Caesars deliver?", "How do I pick up a Little Caesars order without waiting?", "Does the Little Caesars app have deals?"],
    "dietary": ["Does Little Caesars have gluten free pizza?", "Vegetarian options at Little Caesars", "Is Crazy Sauce vegan?",
                "Little Caesars allergen information", "Low calorie options at Little Caesars", "Does Little Caesars have dairy free options?"],
    "game_day_party": ["How many pizzas for 12 people?", "How many pizzas do I need for a fantasy draft party?",
                       "Best pizza for a Super Bowl party", "Game day food ideas for a crowd", "How much pizza per person for a party?",
                       "Cheapest way to feed 20 people on game day", "Best pizza for a tailgate", "What to order for Thursday Night Football?"],
    "sponsorship": ["What is the official pizza of the NFL?", "Which pizza brand advertises during NFL games?", "Which pizza chain sponsors the NFL?",
                    "Can you get Little Caesars at NFL stadiums?", "What pizza commercials feature NFL players?",
                    "Which pizza chains run football commercials?"],
}
_VARIANTS = ["{p}", "{p} 2026", "Quick question: {p}", "{p} Please be specific."]
_BASE_VOLUME = {"product": 900, "value": 1400, "comparison": 700, "ordering": 500, "dietary": 400, "game_day_party": 800, "sponsorship": 300}
_TAGS = {"game_day_party": ["fantasy_draft", "tnf", "sunday_slate", "super_bowl"], "sponsorship": ["tnf", "sunday_slate", "super_bowl"], "value": ["tnf", "sunday_slate"]}


# LCE trademark product names: prompts that reference these are implicitly branded
# even when the text does not include "little caesars".
_LCE_TRADEMARK_TERMS: frozenset[str] = frozenset({
    "little caesars",
    "hot-n-ready", "hot n ready",
    "crazy puffs",
    "crazy bread",
    "extramostbestest", "extra most bestest",
    "slices-n-stix", "slices n stix",
    "caesar wings",
    "crazy sauce",
    "pizza portal",
    "deep!deep!",
})


def is_branded(text: str) -> bool:
    """Return True if the prompt text references Little Caesars by name or trademark product."""
    low = text.lower()
    return any(term in low for term in _LCE_TRADEMARK_TERMS)


def prompt_bank() -> list[dict]:
    # Round-robin across clusters so every cluster is represented in the 150
    per_cluster = {c: [v.format(p=b) for b in _PROMPTS[c] for v in _VARIANTS] for c in CLUSTERS}
    rows, k = [], 0
    while len(rows) < 150:
        for c in CLUSTERS:
            if k < len(per_cluster[c]) and len(rows) < 150:
                rows.append((c, per_cluster[c][k]))
        k += 1
    return [dict(prompt_id=f"q{n:03d}", prompt_text=t, cluster=c, base_volume=_BASE_VOLUME[c], calendar_tags=_TAGS.get(c, []),
                 branded=is_branded(t))
            for n, (c, t) in enumerate(rows, start=1)]


# 30 tracked prompts for v3 (spec section 3). Base wording from prompt_bank() (no "2026", "Quick question:" or
# "Please be specific." variants), every cluster kept, no athlete other than Jared Goff (q035, q147 are untracked).
# Section 9 stories: Party Pack (q062, q201, q006), game-day listicle (q062, q090, q143), Classic Pepperoni and the
# Reddit price (q002), comparison answer page (q059, q115), Goff moment (q202). q201 and q202 are new prompts.
TRACKED_V3 = [
    ("q002", "Gold"), ("q006", "Gold"), ("q062", "Gold"), ("q090", "Gold"), ("q146", "Gold"), ("q201", "Gold"),
    ("q202", "Gold"), ("q030", "Gold"),
    ("q034", "Silver"), ("q118", "Silver"), ("q058", "Silver"), ("q142", "Silver"), ("q059", "Silver"), ("q115", "Silver"),
    ("q143", "Silver"), ("q003", "Silver"), ("q007", "Silver"), ("q063", "Silver"), ("q086", "Silver"),
    ("q001", "Bronze"), ("q029", "Bronze"), ("q057", "Bronze"), ("q085", "Bronze"), ("q031", "Bronze"), ("q004", "Bronze"),
    ("q032", "Bronze"), ("q116", "Bronze"), ("q005", "Bronze"), ("q033", "Bronze"), ("q119", "Bronze"),
]
NEW_PROMPTS = {
    "q201": ("game_day_party", "What should I order for a Super Bowl party for 12 people?"),
    "q202": ("game_day_party", "Best Detroit-style pizza for game day"),
}


def tracked_prompts() -> list[dict]:
    bank = {p["prompt_id"]: p for p in prompt_bank()}
    out = []
    for pid, priority in TRACKED_V3:
        if pid in NEW_PROMPTS:
            cluster, text = NEW_PROMPTS[pid]
            base = dict(prompt_id=pid, prompt_text=text, cluster=cluster, base_volume=_BASE_VOLUME[cluster],
                        calendar_tags=_TAGS.get(cluster, []), branded=is_branded(text))
        else:
            base = dict(bank[pid])
        out.append({**base, "priority": priority, "source": "seed"})
    return out


# Brand facts: the ground truth claims are checked against, each with a validity window (valid_to None = current).
_D = date
_CURATED = [  # fact_id, subject, attribute, value, applies_to, valid_from, valid_to, page_id
    ("F01", "brand", "founded", "1959, Garden City, Michigan", None, _D(1959, 5, 8), None, "pg_about"),
    ("F02", "brand", "nfl_sponsor", "Official Pizza Sponsor of the NFL", None, _D(2023, 6, 1), None, "pg_about"),
    ("F03", "classic_pepperoni", "price", "6.49", None, _D(2026, 1, 1), None, "pg_item_classic_pepperoni"),
    ("F04", "classic_pepperoni", "price", "5.00", None, _D(2004, 1, 1), _D(2025, 12, 31), "pg_item_classic_pepperoni"),
    ("F05", "classic_pepperoni", "ready", "Hot-N-Ready: ready when you walk in", None, _D(2004, 1, 1), None, "pg_item_classic_pepperoni"),
    ("F06", "gameday_499", "price", "4.99", "category:pizza", _D(2025, 9, 1), None, "pg_deals_game_day"),
    ("F07", "lunch_combo", "price", "5.99", None, _D(2026, 1, 1), None, "pg_item_lunch_combo"),
    ("F08", "detroit_pepperoni", "price", "11.99", None, _D(2026, 1, 1), None, "pg_item_detroit_pepperoni"),
    ("F09", "detroit_pepperoni", "style", "Detroit-style square deep dish with crispy cheese edges", None, _D(2024, 1, 1), None, "pg_item_detroit_pepperoni"),
    ("F10", "crazy_bread", "price", "3.99", None, _D(2026, 1, 1), None, "pg_item_crazy_bread"),
    ("F11", "brand", "ordering", "Pizza Portal pickup: order ahead and skip the line", None, _D(2020, 1, 1), None, "pg_order"),
    ("F12", "party_pack", "price", "29.99", None, _D(2025, 9, 1), None, "pg_item_party_pack"),
    ("F13", "party_pack", "price", "24.99", None, _D(2024, 1, 1), _D(2025, 8, 31), "pg_item_party_pack"),
    ("F14", "party_pack", "serves", "12", None, _D(2024, 1, 1), None, "pg_item_party_pack"),
    ("F15", "party_pack", "contents", "3 large pizzas and 2 orders of Crazy Bread", None, _D(2025, 9, 1), None, "pg_item_party_pack"),
    ("F16", "brand", "delivery", "Delivery through the Little Caesars app in most areas", None, _D(2021, 1, 1), None, "pg_app"),
]
_CURRENT_FROM = _D(2026, 1, 1)          # current menu prices start 2026-01-01
_DISCONTINUED_FROM = _D(2024, 1, 1)     # a discontinued item's last price ran 2024-01-01 to 2025-12-31
_DISCONTINUED_TO = _D(2025, 12, 31)
_NUMERIC = {"price", "serves", "founded"}

SUBJECTS: tuple[str, ...] = tuple(row[0] for row in _MENU) + ("gameday_499", "brand")


def subject_vocabulary() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Every judge subject as (id, display name, aliases), in SUBJECTS order: menu items, the deals that are not menu
    items, then the brand. The judge reads names, not bare ids (smoke 1: "Game Day Party Pack" was read as gameday_499)."""
    menu = [(row[0], row[1], tuple(row[8])) for row in _MENU]
    on_menu = {row[0] for row in _MENU}
    extra = [(d["deal_id"], d["name"], ()) for d in deals() if d["deal_id"] not in on_menu]
    return tuple(menu + extra + [("brand", "Little Caesars", ())])


def categories() -> dict[str, str]:
    return {**{row[0]: row[2] for row in _MENU}, "gameday_499": "deal", "brand": "brand"}


def _fact_rows() -> list[tuple]:
    rows = list(_CURATED)
    curated_price = {r[1] for r in _CURATED if r[2] == "price"}
    n = len(_CURATED) + 1
    for item_id, _name, _cat, price, _m, available, *_ in _MENU:
        if item_id in curated_price:
            continue
        page_id = f"pg_item_{item_id}"
        if available:
            rows.append((f"F{n:02d}", item_id, "price", f"{price:.2f}", None, _CURRENT_FROM, None, page_id))
            n += 1
        else:
            rows.append((f"F{n:02d}", item_id, "price", f"{price:.2f}", None, _DISCONTINUED_FROM, _DISCONTINUED_TO, page_id))
            rows.append((f"F{n + 1:02d}", item_id, "available", "no", None, _CURRENT_FROM, None, page_id))
            n += 2
    return rows


def brand_facts() -> list[dict]:
    from geologic.facts import parse_price
    names = {sid: name for sid, name, _aliases in subject_vocabulary()}
    urls = {p["page_id"]: p["url"] for p in site_pages()}
    return [dict(fact_id=fid, subject=subj, subject_name=names[subj], attribute=attr, value=val,
                 value_num=parse_price(val) if attr in _NUMERIC else None, applies_to=applies,
                 valid_from=vf, valid_to=vt, source_url=urls[page_id], page_id=page_id)
            for fid, subj, attr, val, applies, vf, vt, page_id in _fact_rows()]
