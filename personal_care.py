
from deal_scanner import scan_category

KEYWORDS = [
    "shampoo",
    "conditioner",
    "toothpaste",
    "toothbrush",
    "deodorant",
    "body wash",
    "lotion",
    "skincare",
    "skin care",
    "razor",
    "shaving",
    "personal care",
    "vitamin",
    "oral care",
    "soap",
    "wipes",
    "sunscreen",
    "face wash",
    "moisturizer",
    "hair care",
    "mouthwash",
    "floss",
    "lip balm",
    "multipack",
    "multi-pack",
    "pack of",
    "case of"
]

if __name__ == "__main__":
    scan_category("Personal Care", KEYWORDS)
