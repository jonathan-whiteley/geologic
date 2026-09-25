"""The simulated web: official LCE pages plus third-party docs the engines retrieve from."""
from __future__ import annotations
from datetime import datetime, timezone

SEEDED_DOC_IDS = {
    "stale_price_blog": "blog_cheapeats_2019",
    "dominos_sizing": "comp_dominos_party_guide",
    "nfl_news": "news_lce_nfl_2023",
}

def _d(doc_id, source_type, publisher, title, body, year, official=False, page_id=None):
    return dict(doc_id=doc_id, source_type=source_type, publisher=publisher, title=title, body=body,
                published_at=datetime(year, 6, 1, tzinfo=timezone.utc), is_official=official, page_id=page_id)

_THIRD_PARTY = [
    # S1: stale price
    _d("blog_cheapeats_2019", "blog", "cheapeats-guide", "The $5 pizza that changed fast food",
       "Little Caesars made its name with the $5 Hot-N-Ready pepperoni pizza. Walk in, pay $5, walk out.", 2019),
    _d("reddit_pizza_hnr", "reddit", "r/pizza", "Is Hot-N-Ready still $5?",
       "Pretty sure the Hot-N-Ready is still $5 at my store. Crazy Bread is the move.", 2021),
    # S2: competitor answers party sizing
    _d("comp_dominos_party_guide", "competitor", "dominos.com", "How many pizzas for a party",
       "How many pizzas do you need? Plan on 3 slices per adult. For 12 people, order 5 large pizzas from Domino's.", 2025),
    _d("comp_pizzahut_gameday", "competitor", "pizzahut.com", "Game day bundles",
       "Pizza Hut game day bundles feed 8 to 10 fans. Order ahead for kickoff.", 2025),
    # S6: sponsorship only covered by third parties
    _d("news_lce_nfl_2023", "news", "qsr-weekly", "Little Caesars becomes official pizza sponsor of the NFL",
       "Little Caesars is the official pizza sponsor of the NFL. Campaigns feature Justin Jefferson, George Kittle, and Jared Goff, "
       "and a Saquon Barkley commercial ran last season. Select team venues sell Little Caesars in stadium concessions. "
       "Fans get $4.99 online gameday pizza deals.", 2023),
    _d("comp_old_sponsor", "blog", "sportsfood-blog", "The NFL's pizza history",
       "For years another chain was the official pizza of the NFL.", 2018),
    # S5 context
    _d("reddit_puffs", "reddit", "r/fastfood", "Crazy Puffs appreciation",
       "Crazy Puffs are the most underrated item on any pizza menu.", 2026),
    _d("reddit_pretzel", "reddit", "r/nfl", "Bring back Pretzel Crust",
       "Remember the Hot-N-Ready Pretzel Crust? Bring it back for playoffs.", 2026),
    _d("comp_dominos_deals", "competitor", "dominos.com", "Carryout deals", "Domino's carryout deal: large 1-topping for $7.99.", 2026),
    _d("comp_papajohns_wings", "competitor", "papajohns.com", "Wings", "Papa Johns wings come in Buffalo and BBQ.", 2026),
    _d("review_gameday_confusion", "review", "reviews", "2 stars",
       "Sign said $4.99 gameday deal but the app would not take it in store. Had to order online.", 2026),
]

def web_corpus(pages: list[dict]) -> list[dict]:
    docs = [_d(f"lce_{p['page_id']}", "lce_page", "littlecaesars.com", p["url"], p["body"], 2026, True, p["page_id"]) for p in pages]
    docs += _THIRD_PARTY
    # Filler third-party docs so retrieval has realistic noise
    for i in range(60):
        chain = ["Domino's", "Pizza Hut", "Papa Johns", "Little Caesars"][i % 4]
        docs.append(_d(f"filler_{i:03d}", ["review", "blog", "news"][i % 3], "misc", f"{chain} note {i}",
                       f"A customer wrote about {chain} pizza, delivery times, and value for money.", 2024 + i % 3))
    return docs
