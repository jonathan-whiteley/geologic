# Photo credits

| File | Source | Author | License |
|---|---|---|---|
| kittle_tailgate.png | [Detroit-style pizza showing typica lacy cheese crust](https://commons.wikimedia.org/wiki/File:Detroit-style_pizza_showing_typica_lacy_cheese_crust.jpg) (Wikimedia Commons) | Valereee | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |

Converted from JPEG to PNG and resized by Wikimedia's thumbnailer; not otherwise modified. The photo shows food only. The social post it is attached to in the demo is synthetic.

The live demo also uses one athlete press photo (`goff_slices_n_stix.jpg`, credit in `src/geologic/photos.py`). It is not redistributed in this repo; `scripts/deploy.sh` uploads it to the volume when a local copy exists, and `jobs/make_images.py` draws a placeholder only when the volume has none (it never overwrites a photo already there).

## Citation sources pizza (`app/frontend/public/pizza/`)

| File | Source | Author | License |
|---|---|---|---|
| pepperoni-cc0.webp | [Pepperoni pizza 3.jpg](https://commons.wikimedia.org/wiki/File:Pepperoni_pizza_3.jpg) (Wikimedia Commons) | Kurt Kaiser | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |

Cropped to a circle and resized. The live demo uses a Little Caesars menu photo (`lce-pepperoni.webp`) instead; it is not redistributed in this repo, and the chart falls back to the CC0 photo when it is absent.
