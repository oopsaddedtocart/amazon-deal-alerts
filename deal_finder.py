import json
import os
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
MAX_PRICE = 30.00
MIN_DISCOUNT = 50
MAX_ALERTS = 10
HISTORY_FILE = Path("seen_deals.json")

FEED_URL = (
    "https://slickdeals.net/newsearch.php?"
    "mode=frontpage&searcharea=deals&searchin=first&rss=1"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DealFinder/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


def fetch_feed():
    request = urllib.request.Request(FEED_URL, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()

    root = ET.fromstring(data)
    items = root.findall("./channel/item")

    if not items:
        raise RuntimeError(
            "Feed loaded but no RSS items were found. "
            "The feed format may have changed."
        )

    return items


def load_history():
    try:
        return set(json.loads(HISTORY_FILE.read_text()))
    except (OSError, ValueError):
        return set()


def extract_price(text):
    matches = re.findall(
        r"\$\s*([\d,]+(?:\.\d{1,2})?)", text or ""
    )
    prices = [
        float(value.replace(",", ""))
        for value in matches
    ]
    return min(prices) if prices else None


def extract_discount(text):
    matches = re.findall(
        r"(\d{1,3})\s*%\s*(?:off|discount)",
        text or "",
        re.IGNORECASE,
    )
    return max(map(int, matches)) if matches else None


def send_discord(title, link, price, discount):
    price_text = (
        f"${price:.2f}" if price is not None
        else "Price not stated"
    )
    discount_text = (
        f"{discount}% advertised"
        if discount is not None
        else "Discount not stated"
    )

    message = (
        "🔎 **Potential deal candidate**\n"
        f"**{title[:220]}**\n"
        f"Price mentioned: {price_text}\n"
        f"Discount: {discount_text}\n"
        f"Source link: {link}\n"
        "⚠️ Verify the Amazon listing and current price "
        "before purchasing."
    )

    request = urllib.request.Request(
        WEBHOOK,
        data=json.dumps({"content": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status not in (200, 204):
            raise RuntimeError(
                f"Unexpected Discord status: {response.status}"
            )


def main():
    if not WEBHOOK:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL secret.")

    print("Checking deal feed...")
    history = load_history()

    try:
        items = fetch_feed()
    except Exception as error:
        print(f"FEED ERROR: {type(error).__name__}: {error}")
        raise SystemExit(1)

    print(f"Feed items retrieved: {len(items)}")

    sent = 0
    seen_count = 0
    amazon_count = 0
    price_count = 0
    discount_count = 0

    for item in items:
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        description = item.findtext("description", "")
        guid = item.findtext("guid", "").strip() or link

        if not guid or guid in history:
            seen_count += 1
            continue

        text = f"{title} {description} {link}"

        if "amazon" not in text.lower():
            continue

        amazon_count += 1

        price = extract_price(title)
        if price is None:
            price = extract_price(description)

        discount = extract_discount(text)

        # Only reject a stated discount below 50%.
        # Missing discounts remain unverified candidates.
        if discount is not None and discount < MIN_DISCOUNT:
            continue

        if price is not None and (
            price <= 0 or price > MAX_PRICE
        ):
            continue

        # Avoid treating an item with neither price nor
        # discount as a useful deal candidate.
        if price is None and discount is None:
            continue

        price_count += 1
        if discount is not None:
            discount_count += 1

        if sent >= MAX_ALERTS:
            print("Alert limit reached.")
            break

        try:
            send_discord(title, link, price, discount)
        except Exception as error:
            print(f"DISCORD ERROR: {error}")
            raise

        history.add(guid)
        sent += 1
        print(f"Alert sent: {title}")

    HISTORY_FILE.write_text(
        json.dumps(sorted(history), indent=2)
    )

    print("--- Summary ---")
    print(f"Already seen: {seen_count}")
    print(f"Amazon-related items: {amazon_count}")
    print(f"Price/budget candidates: {price_count}")
    print(f"Candidates with stated 50%+ discounts: {discount_count}")
    print(f"Discord alerts sent: {sent}")


if __name__ == "__main__":
    main()
