import os
import re
import json
import hashlib
import requests
from difflib import SequenceMatcher

# ======================================
# SETTINGS
# ======================================

MAX_PRICE = 50.00

# Multipack unit price must be at least
# 60% cheaper than comparison listing.
MIN_UNIT_SAVINGS = 60

# Similarity needed for matching products
MIN_SIMILARITY = 0.80

WEBHOOK = os.environ.get(
    "DISCORD_WEBHOOK_URL", ""
)

DATA_FILE = "amazon_products.json"
SEEN_FILE = "seen_glitches.json"

PACK_SIZES = [
    1, 2, 4, 6, 8, 10,
    12, 24, 36, 48
]

# ======================================
# PRODUCT MATCHING
# ======================================

def clean_title(title):
    title = title.lower()

    title = re.sub(
        r"\b\d+\s?[- ]?(?:pack|pk|count|ct)\b",
        " ",
        title
    )

    title = re.sub(
        r"[^a-z0-9 ]",
        " ",
        title
    )

    return " ".join(title.split())


def similarity(a, b):
    return SequenceMatcher(
        None,
        clean_title(a),
        clean_title(b)
    ).ratio()


def same_seller(a, b):
    seller_a = str(
        a.get("seller_id", "")
    ).strip()

    seller_b = str(
        b.get("seller_id", "")
    ).strip()

    return (
        bool(seller_a)
        and bool(seller_b)
        and seller_a == seller_b
    )


# ======================================
# LOAD PRODUCTS
# ======================================

def load_products():
    if not os.path.exists(DATA_FILE):
        print(
            "No product data found. "
            "Add amazon_products.json."
        )
        return []

    with open(DATA_FILE, "r") as file:
        products = json.load(file)

    if not isinstance(products, list):
        raise ValueError(
            "Product data must be a list."
        )

    return products


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r") as file:
            return set(json.load(file))
    except (OSError, ValueError):
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as file:
        json.dump(sorted(seen), file, indent=2)


# ======================================
# GLITCH DETECTION
# ======================================

def compare_products(a, b):

    try:
        price_a = float(a["price"])
        price_b = float(b["price"])

        qty_a = int(a["quantity"])
        qty_b = int(b["quantity"])

    except (KeyError, ValueError, TypeError):
        return None

    if min(price_a, price_b) <= 0:
        return None

    if min(qty_a, qty_b) <= 0:
        return None

    # Compare smaller and larger packs.
    if qty_a <= qty_b:
        small, large = a, b
        small_price = price_a
        large_price = price_b
        small_qty = qty_a
        large_qty = qty_b
    else:
        small, large = b, a
        small_price = price_b
        large_price = price_a
        small_qty = qty_b
        large_qty = qty_a

    if large_price > MAX_PRICE:
        return None

    match_score = similarity(
        small["title"],
        large["title"]
    )

    if match_score < MIN_SIMILARITY:
        return None

    if not same_seller(small, large):
        return None

    small_unit_price = (
        small_price / small_qty
    )

    large_unit_price = (
        large_price / large_qty
    )

    if small_unit_price <= 0:
        return None

    savings = (
        1 - (
            large_unit_price /
            small_unit_price
        )
    ) * 100

    if savings < MIN_UNIT_SAVINGS:
        return None

    return {
        "product": large,
        "comparison": small,
        "savings": round(savings, 1),
        "unit_price": round(
            large_unit_price, 2
        ),
        "expected_price": round(
            small_unit_price * large_qty, 2
        ),
        "similarity": round(
            match_score, 2
        )
    }


# ======================================
# DISCORD ALERTS
# ======================================

def send_alert(glitch):

    if not WEBHOOK:
        print(
            "Missing DISCORD_WEBHOOK_URL"
        )
        return False

    product = glitch["product"]
    comparison = glitch["comparison"]

    payload = {
        "embeds": [
            {
                "title": (
                    "🚨 POSSIBLE AMAZON "
                    "MULTIPACK PRICE GLITCH"
                ),
                "description": product["title"],
                "url": product["url"],
                "color": 16711680,
                "fields": [
                    {
                        "name": "Multipack Price",
                        "value": (
                            f"${float(product['price']):.2f}"
                        ),
                        "inline": True
                    },
                    {
                        "name": "Pack Quantity",
                        "value": str(
                            product["quantity"]
                        ),
                        "inline": True
                    },
                    {
                        "name": "Unit Price",
                        "value": (
                            f"${glitch['unit_price']:.2f}"
                        ),
                        "inline": True
                    },
                    {
                        "name": "Reference Listing",
                        "value": (
                            f"{comparison['quantity']} units "
                            f"for ${float(comparison['price']):.2f}"
                        ),
                        "inline": False
                    },
                    {
                        "name": "Implied Savings",
                        "value": (
                            f"{glitch['savings']}%"
                        ),
                        "inline": True
                    },
                    {
                        "name": "Reference-Based Value",
                        "value": (
                            f"${glitch['expected_price']:.2f}"
                        ),
                        "inline": True
                    },
                    {
                        "name": "Reference Link",
                        "value": comparison["url"],
                        "inline": False
                    }
                ],
                "footer": {
                    "text": (
                        "Possible error only. "
                        "Verify quantity, seller, "
                        "price, and checkout."
                    )
                }
            }
        ]
    }

    try:
        response = requests.post(
            WEBHOOK,
            json=payload,
            timeout=20
        )

        response.raise_for_status()

        print(
            "Discord alert sent:",
            product["title"]
        )

        return True

    except requests.RequestException as error:
        print(
            "Discord error:",
            error
        )

        return False


# ======================================
# MAIN SCANNER
# ======================================

def scan():

    products = load_products()
    seen = load_seen()

    print(
        "Products loaded:",
        len(products)
    )

    alerts = 0

    for i, product_a in enumerate(products):

        for product_b in products[i + 1:]:

            glitch = compare_products(
                product_a,
                product_b
            )

            if glitch is None:
                continue

            product = glitch["product"]
            comparison = glitch["comparison"]

            glitch_id = hashlib.sha256(
                (
                    str(product.get("asin", product["url"]))
                    + "|"
                    + str(comparison.get(
                        "asin", comparison["url"]
                    ))
                    + "|"
                    + str(product["price"])
                    + "|"
                    + str(comparison["price"])
                ).encode()
            ).hexdigest()

            if glitch_id in seen:
                continue

            print(
                "POTENTIAL GLITCH:",
                product["title"]
            )

            if send_alert(glitch):
                seen.add(glitch_id)
                alerts += 1

    save_seen(seen)

    print(
        "New glitch alerts:",
        alerts
    )


if __name__ == "__main__":
    scan()