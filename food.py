from deal_scanner import scan_category

KEYWORDS = [
    "food",
    "snack",
    "coffee",
    "tea",
    "drink",
    "beverage",
    "protein bar",
    "granola",
    "cereal",
    "candy",
    "grocery",
    "pack of",
    "case of",
    "24-pack",
    "12-pack",
    "multipack",
    "multi-pack",
    "chips",
    "cookies",
    "chocolate",
    "soda",
    "juice",
    "energy drink"
]


if __name__ == "__main__":
    scan_category("Food & Beverages", KEYWORDS)