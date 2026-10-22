"""Real photos shipped with the demo and the credit line each one requires."""
import os
import shutil

CREDITS = {
    "goff_slices_n_stix.jpg": "Photo: Courtesy of Little Caesars",
}


def credit_for(image_uri: str | None) -> str | None:
    return CREDITS.get(image_uri.rsplit("/", 1)[-1]) if image_uri else None


def place_photo(name: str, local_dir: str, dest_dir: str, draw) -> str:
    """Put a credited photo in the volume, never overwriting a file already there (scripts/deploy.sh uploads the real
    press photo, which is gitignored and so absent from the bundle). Copies the local file when the volume has none,
    else calls draw(dest) for a placeholder. Returns kept, copied or placeholder."""
    dest = os.path.join(dest_dir, name)
    if os.path.exists(dest):
        return "kept"
    src = os.path.join(local_dir, name)
    if os.path.exists(src):
        shutil.copyfile(src, dest)
        return "copied"
    draw(dest)
    return "placeholder"
