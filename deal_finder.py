import csv
import json
import os
import re
import hashlib
from difflib import SequenceMatcher
from pathlib import Path

import requests

# SETTINGS
DATA = Path("amazon_products.csv")
SEEN = Path("seen_glitches.json")

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")

MAX_PRICE = 50.00
MIN_SAVINGS = 0.60

# PRODUCT MATCHING

def normalize(title):
    title = title.lower()

    title = re.sub(
        r"\b(?:pack of\s*\d+|\d+\s*[- ]?pack|\d+\s*(?:count|ct|pk))\b",
        " ",
        title
    )

    return " ".join(
        re.findall(r"[a-z0-9]+", title)
    )


def parse_row(row):
    try:
        row["price"] = float(row["price"])
        row["quantity"] = int(row["quantity"])

        row["sold_by_amazon"] = (
            row["sold_by_amazon"].strip().lower() == "true"
        )

        row["missing_image"] = (
            row.get("missing_image", "").strip().lower() == "true"
        )

        if not (
            row["price"] > 0
            and row["quantity"] > 0
            and row["asin"]
            and row["title"]
            and row["url"]
        ):
            return None

        return row

    except (ValueError, KeyError, TypeError):
        return None


def load_products():
    if not DATA.exists():
        print("No product data source configured.")
        return []

    with DATA.open(
        newline="",
        encoding="utf-8"
    ) as file:

        return [
            product
            for row in csv.DictReader(file)
            if (product := parse_row(row))
        ]


# COMPARE MULTIPACKS

def compare(a, b):

    # Only products sold by Amazon
    if not (
        a["sold_by_amazon"]
        and b["sold_by_amazon"]
    ):
        return None

    if a["quantity"] == b["quantity"]:
        return None

    small, large = sorted(
        (a, b),
        key=lambda product: product["quantity"]
    )

    if large["price"] > MAX_PRICE:
        return None

    match = SequenceMatcher(
        None,
        normalize(small["title"]),
        normalize(large["title"])
    ).ratio()

    if match < 0.88:
        return None

    small_unit_price = (
        small["price"] / small["quantity"]
    )

    large_unit_price = (
        large["price"] / large["quantity"]
    )

    savings = (
        1 - large_unit_price / small_unit_price
    )

    if savings < MIN_SAVINGS:
        return None

    return small, large, savings


# DISCORD NOTIFICATIONS

def send_alert(small, large, savings):

    if not WEBHOOK:
        print("Discord webhook missing.")
        return False

    description = (
        f"**{large['title']}**\n\n"
        f"📦 Pack Quantity: {large['quantity']}\n"
        f"💰 Multipack Price: ${large['price']:.2f}\n"
        f"📊 Reference Price: ${small['price']:.2f}\n"
        f"🔥 Unit Price Savings: {savings:.0%}\n"
        f"🖼️ Missing Image: {large['missing_image']}\n\n"
        f"🛒 [BUY MULTIPACK]({large['url']})\n"
        f"🔎 [COMPARE LISTING]({small['url']})\n\n"
        "⚠️ Potential glitch only. "
        "Verify seller, quantity, and checkout price."
    )

    payload = {
        "embeds": [
            {
                "title": "🚨 AMAZON MULTIPACK GLITCH ALERT",
                "description": description,
                "color": 16711680
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

        print("Discord alert sent!")

        return True

    except requests.RequestException as error:
        print("Discord error:", error)
        return False


# MAIN SCANNER

def main():

    products = load_products()

    print("Products loaded:", len(products))

    try:
        seen = (
            set(json.loads(SEEN.read_text()))
            if SEEN.exists()
            else set()
        )
    except (ValueError, OSError):
        seen = set()

    alerts = 0

    for i, product_a in enumerate(products):

        for product_b in products[i + 1:]:

            result = compare(
                product_a,
                product_b
            )

            if result is None:
                continue

            small, large, savings = result

            glitch_id = hashlib.sha256(
                (
                    f"{small['asin']}|"
                    f"{large['asin']}|"
                    f"{small['price']}|"
                    f"{large['price']}"
                ).encode()
            ).hexdigest()

            if glitch_id in seen:
                continue

            print(
                "POTENTIAL GLITCH:",
                large["title"]
            )

            if send_alert(
                small,
                large,
                savings
            ):
                seen.add(glitch_id)
                alerts += 1

    SEEN.write_text(
        json.dumps(sorted(seen), indent=2)
    )

    print("New glitch alerts:", alerts)


if __name__ == "__main__":
    main()