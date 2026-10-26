
from deal_scanner import scan_category

KEYWORDS = [
    "cleaner",
    "cleaning",
    "paper towel",
    "toilet paper",
    "trash bag",
    "laundry detergent",
    "dish soap",
    "dishwasher",
    "tissue",
    "storage",
    "household",
    "refill",
    "sponge",
    "wipes",
    "air freshener",
    "vacuum",
    "mop",
    "multipack",
    "multi-pack",
    "pack of",
    "case of",
    "bulk pack",
    "bulk",
    "sprayway",
    "zep"
]

if __name__ == "__main__":
    scan_category("Household Supplies", KEYWORDS)
