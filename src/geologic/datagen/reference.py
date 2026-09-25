"""Reference data for GEOlogic. Product names are real LCE items; prices and margins are synthetic."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

CLUSTERS = ["product", "value", "comparison", "ordering", "dietary", "game_day_party", "sponsorship"]

SEEDED_PAGE_IDS = {
    "hot_n_ready": "pg_item_classic_pepperoni",
    "game_day": "pg_deals_game_day",
    "order": "pg_order",
    "detroit": "pg_item_detroit_pepperoni",
    "about_nfl": "pg_about",
}

# item_id, name, category, price, margin_pct, available, is_lto, dietary_flags, aliases
_MENU = [
    ("classic_pepperoni", "Classic Pepperoni Hot-N-Ready", "pizza", 6.49, 0.34, True, False, [], ["hot-n-ready", "hot n ready", "classic pepperoni"]),
    ("classic_cheese", "Classic Cheese Hot-N-Ready", "pizza", 6.49, 0.36, True, False, ["vegetarian"], ["classic cheese"]),
    ("emb_pepperoni", "ExtraMostBestest Pepperoni", "pizza", 7.99, 0.33, True, False, [], ["extramostbestest", "extra most bestest"]),
    ("emb_cheese", "ExtraMostBestest Cheese", "pizza", 7.99, 0.35, True, False, ["vegetarian"], []),
    ("three_meat", "3 Meat Treat", "pizza", 10.99, 0.31, True, False, [], ["3 meat treat", "three meat treat"]),
    ("ultimate_supreme", "Ultimate Supreme", "pizza", 10.99, 0.30, True, False, [], ["supreme"]),
    ("hula_hawaiian", "Hula Hawaiian", "pizza", 10.49, 0.32, True, False, [], ["hawaiian"]),
    ("veggie", "Veggie", "pizza", 10.49, 0.33, True, False, ["vegetarian"], ["veggie pizza"]),
    ("detroit_pepperoni", "Detroit-Style Deep!Deep! Dish Pepperoni", "pizza", 11.99, 0.38, True, False, [], ["deep deep dish", "deep!deep! dish", "detroit-style", "detroit style"]),
    ("detroit_cheese", "Detroit-Style Deep!Deep! Dish Cheese", "pizza", 11.49, 0.39, True, False, ["vegetarian"], []),
    ("stuffed_crust", "Stuffed Crust Pepperoni", "pizza", 9.99, 0.32, True, False, [], ["stuffed crust"]),
    ("thin_crust", "Thin Crust Pepperoni", "pizza", 7.49, 0.34, True, False, [], ["thin crust"]),
    ("pretzel_crust", "Pretzel Crust Pepperoni", "pizza", 8.99, 0.29, False, True, [], ["pretzel crust"]),
    ("calzony", "Batman Calzony", "pizza", 9.49, 0.28, False, True, [], ["calzony"]),
    ("crazy_bread", "Crazy Bread", "sides", 3.99, 0.62, True, False, ["vegetarian"], ["crazy bread"]),
    ("crazy_combo", "Crazy Combo", "sides", 4.99, 0.60, True, False, ["vegetarian"], ["crazy combo"]),
    ("stuffed_crazy_bread", "Stuffed Crazy Bread", "sides", 5.49, 0.55, True, False, ["vegetarian"], ["stuffed crazy bread"]),
    ("italian_cheese_bread", "Italian Cheese Bread", "sides", 5.99, 0.52, True, False, ["vegetarian"], ["italian cheese bread", "cheese bread"]),
    ("pepperoni_cheese_bread", "Pepperoni Cheese Bread", "sides", 6.49, 0.50, True, False, [], ["pepperoni cheese bread"]),
    ("crazy_puffs_pepperoni", "Crazy Puffs (Pepperoni)", "sides", 4.49, 0.58, True, False, [], ["crazy puffs"]),
    ("crazy_puffs_cheese", "Crazy Puffs (4 Cheese)", "sides", 4.49, 0.59, True, False, ["vegetarian"], []),
    ("slices_n_stix", "Slices-N-Stix", "sides", 5.99, 0.50, True, False, ["vegetarian"], ["slices-n-stix", "slices n stix"]),
    ("wings_oven", "Caesar Wings (Oven Roasted)", "wings", 7.99, 0.40, True, False, ["gluten_free_sauce"], ["caesar wings", "wings"]),
    ("wings_bbq", "Caesar Wings (BBQ)", "wings", 7.99, 0.40, True, False, [], []),
    ("wings_buffalo", "Caesar Wings (Buffalo)", "wings", 7.99, 0.40, True, False, [], []),
    ("wings_garlic_parm", "Caesar Wings (Garlic Parmesan)", "wings", 7.99, 0.40, True, False, [], []),
    ("dip_garlic", "Buttery Garlic Caesar Dip", "dips", 0.99, 0.70, True, False, ["vegetarian"], ["garlic dip"]),
    ("dip_jalapeno", "Cheezy Jalapeno Caesar Dip", "dips", 0.99, 0.70, True, False, ["vegetarian"], ["jalapeno dip"]),
    ("dip_ranch", "Ranch Caesar Dip", "dips", 0.99, 0.70, True, False, ["vegetarian"], ["ranch"]),
    ("crazy_sauce", "Crazy Sauce", "dips", 1.29, 0.72, True, False, ["vegetarian", "vegan"], ["crazy sauce"]),
    ("lunch_combo", "Lunch Combo", "combos", 5.99, 0.45, True, False, [], ["lunch combo"]),
    ("party_pack", "Game Day Party Pack", "combos", 29.99, 0.40, True, False, [], ["party pack"]),
]


def menu_items() -> list[dict]:
    return [
        dict(item_id=i, name=n, category=c, price=p, margin_pct=m, available=a, is_lto=l,
             dietary_flags=list(d), image_uri=f"/Volumes/jdub_demo/geologic/assets/menu/{i}.png", aliases=list(al))
        for (i, n, c, p, m, a, l, d, al) in _MENU
    ]


def deals() -> list[dict]:
    return [
        dict(deal_id="gameday_499", name="$4.99 Online Gameday Deal", price=4.99, channel="online", active=True),
        dict(deal_id="lunch_combo", name="Lunch Combo", price=5.99, channel="in_store", active=True),
    ]


_UPDATED = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _page(page_id, url, page_type, item_id, body, jsonld=None):
    return dict(page_id=page_id, url=url, page_type=page_type, primary_item_id=item_id, body=body,
                jsonld=jsonld, has_valid_jsonld=jsonld is not None, version=1, updated_at=_UPDATED)


def site_pages() -> list[dict]:
    pages = []
    for m in menu_items():
        if m["item_id"] == "classic_pepperoni":
            # S1: no price text, no JSON-LD
            body = "## Classic Hot-N-Ready\nPepperoni pizza, ready when you walk in."
            pages.append(_page("pg_item_classic_pepperoni", "https://littlecaesars.com/menu/hot-n-ready", "item", m["item_id"], body))
            continue
        body = f"## {m['name']}\n{m['name']} from Little Caesars. ${m['price']:.2f} at most locations."
        if not m["available"]:
            body = f"## {m['name']}\nNo longer available."
        jsonld = (
            '{"@context":"https://schema.org","@type":"MenuItem","name":"%s","offers":{"@type":"Offer","price":"%.2f","priceCurrency":"USD"}}'
            % (m["name"], m["price"]) if m["available"] and m["category"] != "dips" else None
        )
        pages.append(_page(f"pg_item_{m['item_id']}", f"https://littlecaesars.com/menu/{m['item_id'].replace('_', '-')}", "item", m["item_id"], body, jsonld))
    fixed = [
        ("pg_menu", "https://littlecaesars.com/menu", "menu", None, "## Menu\nPizza, sides, wings, dips, and combos."),
        ("pg_deals", "https://littlecaesars.com/deals", "deals", None, "## Deals\nSee current deals in the app."),
        # S2 + S6: thin game-day page, no sizing answer, sponsorship mentioned once
        ("pg_deals_game_day", "https://littlecaesars.com/deals/game-day", "deals", None,
         "## Game Day Deals\n$4.99 online during NFL games.\nOfficial Pizza Sponsor of the NFL."),
        # S7: ordering page exists but is orphaned (crawlers never reach it)
        ("pg_order", "https://littlecaesars.com/order", "ordering", None, "## Order\nPick up with Pizza Portal."),
        ("pg_about", "https://littlecaesars.com/about", "about", None, "## About Little Caesars\nFounded in 1959 in Garden City, Michigan."),
        ("pg_faq", "https://littlecaesars.com/faq", "faq", None, "## FAQ\nQuestions about orders and the app."),
        ("pg_nutrition", "https://littlecaesars.com/nutrition", "faq", None, "## Nutrition\nNutrition and allergen information."),
        ("pg_app", "https://littlecaesars.com/app", "ordering", None, "## The Little Caesars App\nOrder ahead and skip the line."),
    ]
    pages += [_page(*f) for f in fixed]
    # Store-locator style pages to reach ~62 total
    for i, city in enumerate(["Detroit", "Chicago", "Dallas", "Phoenix", "Atlanta", "Denver", "Houston",
                              "Orlando", "Columbus", "Charlotte", "Minneapolis", "San Antonio", "Tampa",
                              "Las Vegas", "Nashville", "Kansas City", "Cleveland", "Indianapolis",
                              "Memphis", "Tucson", "Omaha", "Louisville"]):
        pages.append(_page(f"pg_loc_{i:02d}", f"https://littlecaesars.com/locations/{city.lower().replace(' ', '-')}",
                           "location", None, f"## Little Caesars {city}\nHot-N-Ready pizza near you in {city}."))
    return pages


def personas() -> list[dict]:
    rows = [
        ("p_jefferson", "Justin Jefferson", True, "athlete", 3_400_000, False),
        ("p_kittle", "George Kittle", True, "athlete", 2_100_000, False),
        ("p_goff", "Jared Goff", True, "athlete", 1_600_000, False),
        ("p_barkley", "Saquon Barkley", True, "athlete", 4_200_000, False),
        ("p_creator_slicequeen", "SliceQueen", False, "creator", 480_000, False),
        ("p_creator_gridirongrub", "Gridiron Grub", False, "creator", 260_000, False),
        # S4: fictional athlete in an off-field controversy
        ("p_fictional_dax", "Dax Merriwether", False, "athlete", 900_000, True),
    ]
    return [dict(persona_id=a, display_name=b, is_real=c, persona_type=d, reach=e, is_excluded=f) for a, b, c, d, e, f in rows]


def exclusion_rules() -> list[dict]:
    rows = [
        ("EX-01", "persona", "p_fictional_dax", "Off-field controversy"),
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
    "sponsorship": ["What is the official pizza of the NFL?", "What pizza does Saquon Barkley advertise?", "Which pizza chain sponsors the NFL?",
                    "Can you get Little Caesars at NFL stadiums?", "What pizza commercials feature NFL players?",
                    "Does Justin Jefferson do pizza commercials?"],
}
_VARIANTS = ["{p}", "{p} 2026", "Quick question: {p}", "{p} Please be specific."]
_BASE_VOLUME = {"product": 900, "value": 1400, "comparison": 700, "ordering": 500, "dietary": 400, "game_day_party": 800, "sponsorship": 300}
_TAGS = {"game_day_party": ["fantasy_draft", "tnf", "sunday_slate", "super_bowl"], "sponsorship": ["tnf", "sunday_slate", "super_bowl"], "value": ["tnf", "sunday_slate"]}


def prompt_bank() -> list[dict]:
    # Round-robin across clusters so every cluster is represented in the 150
    per_cluster = {c: [v.format(p=b) for b in _PROMPTS[c] for v in _VARIANTS] for c in CLUSTERS}
    rows, k = [], 0
    while len(rows) < 150:
        for c in CLUSTERS:
            if k < len(per_cluster[c]) and len(rows) < 150:
                rows.append((c, per_cluster[c][k]))
        k += 1
    return [dict(prompt_id=f"q{n:03d}", prompt_text=t, cluster=c, base_volume=_BASE_VOLUME[c], calendar_tags=_TAGS.get(c, []))
            for n, (c, t) in enumerate(rows, start=1)]
