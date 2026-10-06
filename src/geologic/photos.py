"""Real photos shipped with the demo and the credit line each one requires."""
CREDITS = {
    "goff_slices_n_stix.jpg": "Photo: Courtesy of Little Caesars",
    "barkley_press.jpg": "Photo: Courtesy of Little Caesars",
    "jefferson_press.jpg": "Photo: Courtesy of Little Caesars",
    "kittle_radio_row.jpg": "Photo: The Pat McAfee Show via TikTok @rashtic1",
    "kittle_tailgate.png": "Photo: Valereee, CC BY-SA 4.0",
}


def credit_for(image_uri: str | None) -> str | None:
    return CREDITS.get(image_uri.rsplit("/", 1)[-1]) if image_uri else None
