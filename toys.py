
from deal_scanner import scan_category

KEYWORDS = [
    "toy",
    "lego",
    "pokemon",
    "pokémon",
    "trading card",
    "collectible",
    "figure",
    "plush",
    "board game",
    "playset",
    "action figure",
    "nerf",
    "hot wheels",
    "needoh",
    "nee doh",
    "funko pop",
    "transformers",
    "barbie",
    "monster high",
    "disney",
    "multipack",
    "multi-pack",
    "pack of"
]

if __name__ == "__main__":
    scan_category("Toys & Collectibles", KEYWORDS)
