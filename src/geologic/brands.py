"""Brand attribution for citations and logos for the leaderboard."""
BRANDS = ["Little Caesars", "Domino's", "Pizza Hut", "Papa Johns"]
_PUBLISHER_BRAND = {"dominos.com": "Domino's", "pizzahut.com": "Pizza Hut", "papajohns.com": "Papa Johns"}
LOGOS = {"Little Caesars": "/logos/lce-mascot.svg", "Domino's": "/logos/dominos.svg",
         "Pizza Hut": "/logos/pizzahut.svg", "Papa Johns": "/logos/papajohns.svg"}

def brand_for_doc(doc: dict) -> str | None:
    if doc.get("is_official"):
        return "Little Caesars"
    return _PUBLISHER_BRAND.get(doc.get("publisher", ""))
