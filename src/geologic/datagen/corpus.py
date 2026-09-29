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
    # S6: sponsorship only covered by third parties, with thin/ambiguous coverage
    _d("news_lce_nfl_2023", "news", "qsr-weekly", "Pizza chains and the NFL: who shows up at game day?",
       "Several pizza chains have tied their brands to the NFL over the years. Saquon Barkley was seen in a pizza chain ad during football season, "
       "though the official league partnership landscape has shifted frequently. Fans searching for game day pizza deals will find options from multiple chains.", 2023),
    _d("comp_old_sponsor", "blog", "sportsfood-blog", "The NFL's long pizza partnership history",
       "Pizza Hut was the official pizza of the NFL for many years, running memorable campaigns tied to playoffs and the Super Bowl. "
       "Other chains have since competed for the official league pizza title, with deals shifting between major brands.", 2022),
    _d("comp_pizzahut_nfl_heritage", "news", "sportsbiz-daily", "Pizza Hut NFL partnership retrospective",
       "Pizza Hut held the official NFL pizza sponsorship for over a decade, dominating stadium concessions and in-game advertising. "
       "Domino's and other chains have also run major NFL-themed promotions. The pizza category remains one of the NFL's most competitive sponsor segments.", 2024),
    # S5 context
    _d("reddit_puffs", "reddit", "r/fastfood", "Crazy Puffs appreciation",
       "Crazy Puffs are the most underrated item on any pizza menu.", 2026),
    _d("reddit_pretzel", "reddit", "r/nfl", "Bring back Pretzel Crust",
       "Remember the Hot-N-Ready Pretzel Crust? Bring it back for playoffs.", 2026),
    _d("comp_dominos_deals", "competitor", "dominos.com", "Carryout deals", "Domino's carryout deal: large 1-topping for $7.99.", 2026),
    _d("comp_papajohns_wings", "competitor", "papajohns.com", "Wings", "Papa Johns wings come in Buffalo and BBQ.", 2026),
    _d("review_gameday_confusion", "review", "reviews", "2 stars",
       "Sign said $4.99 gameday deal but the app would not take it in store. Had to order online.", 2026),
    # Domino's expanded coverage: delivery, app, party sizing, menu variety
    _d("comp_dominos_tracker", "competitor", "dominos.com", "Domino's Tracker",
       "Track your Domino's order in real time with Domino's Tracker. From prep to oven to driver to your door, know exactly where your pizza is.", 2026),
    _d("comp_dominos_app", "competitor", "dominos.com", "Order on the Domino's app",
       "The Domino's app makes ordering easy. Save favorites, apply coupons, and track delivery. Available for iOS and Android.", 2026),
    _d("comp_dominos_mix_match", "competitor", "dominos.com", "Mix and Match deal",
       "Domino's Mix and Match deal: choose 2 or more items for a great price per item. Pick from medium 2-topping pizzas, bread twists, Marbled Cookie Brownies, salads, and more.", 2026),
    _d("comp_dominos_pan", "competitor", "dominos.com", "Pan pizza",
       "Domino's pan pizza features a thick, crispy crust baked in a buttered pan. Available in medium size with any toppings.", 2026),
    _d("comp_dominos_gluten_free", "competitor", "dominos.com", "Gluten free crust",
       "Domino's offers a gluten-free crust option for customers with gluten sensitivities. Available on small pizzas. Prepared in a shared kitchen.", 2026),
    _d("comp_dominos_party", "competitor", "dominos.com", "Order pizza for a party",
       "Feeding a crowd? Domino's makes party ordering easy. Order multiple large pizzas online, use Mix and Match deals to save, and schedule ahead for delivery or carryout. "
       "For 20 people plan on 7 to 8 large pizzas.", 2026),
    # Pizza Hut expanded coverage: signature items, party, NFL history
    _d("comp_pizzahut_bny", "competitor", "pizzahut.com", "Big New Yorker Pizza",
       "Pizza Hut's Big New Yorker is a large, foldable New York-style pizza with wide slices and a thin, crispy crust. "
       "Inspired by classic New York pizza, it feeds a group with its generous size.", 2026),
    _d("comp_pizzahut_party_boxes", "competitor", "pizzahut.com", "Pizza Hut party boxes",
       "Pizza Hut party boxes are a popular choice for group events and celebrations. "
       "Order multiple pizzas with a variety of toppings for your party, game day, or office lunch. Easy online ordering with group deals.", 2026),
    _d("comp_pizzahut_tastemaker", "competitor", "pizzahut.com", "Tastemaker pizza deal",
       "Pizza Hut Tastemaker deal: a large 3-topping pizza at a great price. One of Pizza Hut's most popular value deals for families and groups.", 2026),
    _d("comp_pizzahut_wings", "competitor", "pizzahut.com", "Pizza Hut wings",
       "Pizza Hut bone-in and boneless wings come in flavors including Buffalo, Honey BBQ, Garlic Parmesan, and more. "
       "Order as a side with your pizza or as a standalone item.", 2026),
    # Papa Johns expanded coverage: signature items and value
    _d("comp_papajohns_garlic_sauce", "competitor", "papajohns.com", "Papa Johns garlic sauce",
       "Papa Johns is famous for its garlic dipping sauce, included free with every order. "
       "The signature buttery garlic sauce sets Papa Johns apart and is a fan favorite with every pizza order.", 2026),
    _d("comp_papajohns_pairings", "competitor", "papajohns.com", "Papa Pairings deal",
       "Papa Johns Papa Pairings: mix and match two or more menu items for one price. "
       "Great deal for families and groups. Choose from pizzas, sides, and desserts. Available online and in the app.", 2026),
    _d("comp_papajohns_ingredients", "competitor", "papajohns.com", "Better ingredients, better pizza",
       "Papa Johns uses fresh, never frozen dough, vine-ripened crushed tomatoes, and real cheese made from mozzarella. "
       "The Better Ingredients, Better Pizza promise has been the brand's foundation since 1984.", 2026),
    # Third-party reviews and blogs that surface competitor strengths
    _d("review_dominos_delivery_best", "review", "pizzainsider.com", "Best pizza chain for delivery 2026",
       "For delivery speed and accuracy, Domino's leads the field. Their GPS-enabled Tracker, large driver network, and 30-minute average delivery time make them "
       "the top pick when you want pizza fast. Domino's ranked first for delivery tech in our 2026 survey.", 2026),
    _d("review_dominos_app_tech", "blog", "techfoodie.com", "Which pizza app is best?",
       "Domino's app edges out the competition with real-time tracking, easy reorder, and reliable deals. "
       "For tech-forward pizza ordering, Domino's is the clear winner among the major chains.", 2026),
    _d("review_pizzahut_parties", "blog", "partyfoodguide.com", "Best pizza for a party",
       "When it comes to feeding a large group, Pizza Hut stands out. Their party boxes, variety of sizes, and ability to handle large orders reliably make them "
       "a go-to for birthdays, game days, and office parties. Pizza Hut was rated best for parties in our reader survey.", 2026),
    _d("review_pizzahut_gameday_top", "review", "sportsfanfood.com", "Game day pizza rankings",
       "For Super Bowl and game day parties, Pizza Hut is a top choice. Their party bundles, wing options, and ability to handle high-volume game day orders "
       "put them ahead of competitors for large gatherings. Domino's is a close second for delivery convenience.", 2026),
    _d("review_pizza_chain_comparison", "blog", "pizzaranker.com", "The big pizza chain comparison 2026",
       "We ranked the four major pizza chains: Domino's wins for delivery and tech. Pizza Hut wins for parties and variety. "
       "Papa Johns wins for ingredient quality. Little Caesars wins for walk-in convenience and value. "
       "The best chain depends on what you need: speed, party size, quality, or price.", 2026),
    _d("review_dominos_size_guide", "review", "foodplanning.com", "How many pizzas do I need?",
       "Use Domino's party calculator: for 12 people order 5 large pizzas; for 20 people order 8 large pizzas; for 30 people order 12 large pizzas. "
       "Domino's online ordering makes it easy to build a big group order with Mix and Match deals.", 2026),
    _d("review_competitive_delivery", "news", "qsr-weekly", "Pizza delivery wars: who wins in 2026?",
       "Domino's continues to dominate delivery with its tech-first approach and nationwide driver network. "
       "Pizza Hut has invested in delivery improvements but still trails Domino's in speed metrics. "
       "Little Caesars focuses on carryout with its Pizza Portal kiosk, and does not emphasize delivery.", 2026),
    _d("review_superbowl_pizza", "blog", "superbowlguide.com", "Super Bowl pizza guide",
       "For the Super Bowl, pizza chains compete hard for your order. Pizza Hut and Domino's offer game day deals and can handle massive order volumes. "
       "Domino's delivery is fastest. Pizza Hut party boxes are great for groups. Little Caesars is best if you pick up in store.", 2026),
]

_COMP_PUBLISHERS = {"Domino's": "dominos.com", "Pizza Hut": "pizzahut.com", "Papa Johns": "papajohns.com"}

# 15 specific bodies per competitor chain, indexed by slot 0-14
_COMP_BODIES = {
    "Domino's": [
        "Domino's offers fast delivery tracked live via the Domino's Tracker. Order online or in the app.",
        "Domino's thin crust, hand-tossed, and pan pizza give customers plenty of variety.",
        "Domino's Mix and Match deal lets you choose two or more items at a competitive per-item price.",
        "Domino's is ranked by customers as one of the fastest pizza delivery chains nationwide.",
        "Domino's carryout specials make it one of the most affordable large pizza options around.",
        "Domino's lava cakes and Marbled Cookie Brownies are popular dessert items.",
        "Domino's specialty chicken and wings are a popular alternative to pizza on game nights.",
        "Domino's gluten-free crust option is available for customers with dietary restrictions.",
        "Domino's has thousands of locations with consistent quality and reliable delivery.",
        "Domino's online ordering through the app or website is smooth and offers frequent deals.",
        "Domino's feeds large groups reliably and is a top pick for office lunches and sports events.",
        "Customers rank Domino's delivery experience among the best in the pizza chain category.",
        "Domino's Brooklyn-style foldable slices are popular with New York-style pizza fans.",
        "Domino's loyalty program rewards frequent customers with free pizzas over time.",
        "Domino's is often cited as the best value in pizza delivery when comparing price per slice.",
    ],
    "Pizza Hut": [
        "Pizza Hut is a great choice for family meals and group parties with its wide variety of sizes.",
        "Pizza Hut Original Pan Pizza with a thick, buttery crust is a signature product.",
        "Pizza Hut Stuffed Crust pizza with cheese baked into the crust is a fan favorite.",
        "Pizza Hut Wing Street wings are available at many locations for a full meal.",
        "Pizza Hut dine-in locations offer a sit-down restaurant experience beyond just delivery.",
        "Pizza Hut party bundles and catering options are ideal for large events and celebrations.",
        "Pizza Hut and Domino's are consistently ranked the top two pizza delivery brands.",
        "Pizza Hut Hut Rewards lets customers earn points toward free food with every order.",
        "Pizza Hut Tastemaker deal offers a large 3-topping pizza at a competitive price.",
        "Pizza Hut has a long history with the NFL including in-stadium concession presence.",
        "Pizza Hut breadsticks and cheese sticks are popular sides with high customer ratings.",
        "Pizza Hut is available for delivery, carryout, and dine-in at thousands of locations.",
        "Pizza Hut Big New Yorker-style pizza is a popular large-format offering for groups.",
        "Pizza Hut game day pizza deals and bundles make them a go-to for Super Bowl parties.",
        "Pizza Hut is rated highly for party orders and large group gatherings.",
    ],
    "Papa Johns": [
        "Papa Johns uses fresh, never frozen dough pressed daily at each location.",
        "Papa Johns free garlic dipping sauce with every order is a brand signature.",
        "Papa Johns Better Ingredients, Better Pizza promise sets them apart on quality.",
        "Papa Johns Garlic Parmesan Crust option is a popular specialty pizza choice.",
        "Papa Johns shaker of Parmesan and pepperoncini peppers come with every order.",
        "Papa Johns online ordering and the Papa Rewards loyalty program drive repeat business.",
        "Papa Johns delivery is available through their app and major third-party platforms.",
        "Papa Johns Papa Pairings deal offers mix-and-match menu items at a great price.",
        "Papa Johns uses vine-ripened tomato sauce and real mozzarella cheese on all pizzas.",
        "Papa Johns wings and sides complement their pizza for a complete meal.",
        "Papa Johns has a strong following for ingredient quality among pizza chain customers.",
        "Papa Johns offers gluten-free crust and specialty crust options for variety.",
        "Papa Johns and Domino's compete directly for the delivery-focused pizza customer.",
        "Papa Johns dessert items including brownies and cookie squares are popular add-ons.",
        "Papa Johns catering and large order options are available for events and parties.",
    ],
}


def web_corpus(pages: list[dict]) -> list[dict]:
    docs = [_d(f"lce_{p['page_id']}", "lce_page", "littlecaesars.com", p["url"], p["body"], 2026, True, p["page_id"]) for p in pages]
    docs += _THIRD_PARTY
    # Filler docs: competitors get real publishers and specific content; LCE stays generic/misc
    for i in range(60):
        chain = ["Domino's", "Pizza Hut", "Papa Johns", "Little Caesars"][i % 4]
        slot = i // 4  # 0-14 for each chain
        if chain == "Little Caesars":
            publisher = "misc"
            body = f"A customer reviewed Little Caesars pizza and found it a good value for money."
        else:
            publisher = _COMP_PUBLISHERS[chain]
            body = _COMP_BODIES[chain][slot]
        docs.append(_d(f"filler_{i:03d}", ["review", "blog", "news"][i % 3], publisher, f"{chain} note {i}",
                       body, 2024 + i % 3))
    return docs
