
from deal_scanner import scan_category

KEYWORDS = [
    "price drop",
    "price error",
    "pricing error",
    "glitch",
    "mispriced",
    "lowest price",
    "all-time low",
    "all time low",
    "lightning deal",
    "coupon",
    "extra off",
    "clearance",
    "was $",
    "now $",
    "save ",
    "limited time",
    "huge discount",
    "price cut",
    "markdown",
    "deal of the day",
    "50% off",
    "60% off",
    "70% off",
    "80% off",
    "90% off"
]

if __name__ == "__main__":
    scan_category("Price Drops & Potential Glitches", KEYWORDS)
