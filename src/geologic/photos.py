"""Real photos shipped with the demo and the credit line each license requires."""
CREDITS = {"kittle_tailgate.png": "Photo: Valereee, CC BY-SA 4.0"}


def credit_for(image_uri: str | None) -> str | None:
    return CREDITS.get(image_uri.rsplit("/", 1)[-1]) if image_uri else None
