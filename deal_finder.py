import json
import os
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
MAX_PRICE = 30.00
MIN_DISCOUNT = 50
MAX_ALERTS_PER_RUN = 10

FEEDS = [
    "https://www.dealnews.com/rss/todays-edition",
    "https://www.dealnews.com/rss/editors-choice/",
]

SEEN_FILE = Path("seen_deals.json")


def fetch_feed(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AmazonDealFinder/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return ET.fromstring(response.read())


def clean(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()


def load_seen():
    try:
        return set(json.loads(SEEN_FILE.read_text()))
    except (OSError, ValueError):
        return set()


def send_discord(message):
    payload = json.dumps({"content": message}).encode("utf-8")
    request = urllib.request.Request(
        WEBHOOK,
        data=payload,
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

    seen = load_seen()
    new_seen = set(seen)
    candidates = {}
    feed_errors = []

    for feed_url in FEEDS:
        try:
            root = fetch_feed(feed_url)
            channel = root.find("channel")

            if channel is None:
                print(f"WARNING: No RSS channel: {feed_url}")
                continue

            items = channel.findall("item")
            print(f"Feed loaded: {feed_url} — {len(items)} items")

            for item in items:
                title = clean(item.findtext("title", ""))
                description = clean(item.findtext("description", ""))
                link = clean(item.findtext("link", ""))
                guid = clean(item.findtext("guid", "")) or link

                if guid:
                    candidates.setdefault(
                        guid,
                        {
                            "title": title,
                            "description": description,
                            "link": link,
                        }
                    )

        except Exception as error:
            feed_errors.append(f"{feed_url}: {error}")
            print(f"FEED ERROR: {feed_url}: {error}")

    print(f"Unique feed items: {len(candidates)}")

    if not candidates:
        raise SystemExit(
            "No feed items retrieved. Check the feed errors above."
        )

    counts = {
        "already_seen": 0,
        "not_amazon": 0,
        "no_price": 0,
        "over_budget": 0,
        "discount_too_low": 0,
        "sent": 0,
    }

    for guid, deal in candidates.items():
        if guid in seen:
            counts["already_seen"] += 1
            continue

        title = deal["title"]
        description = deal["description"]
        text = f"{title} {description}"

        if "amazon" not in text.lower():
            counts["not_amazon"] += 1
            continue

        # Prefer the price shown in the title.
        price_match = re.search(
            r"\$\s*([\d,]+(?:\.\d{1,2})?)", title
        )
        if not price_match:
            price_match = re.search(
                r"\$\s*([\d,]+(?:\.\d{1,2})?)", description
            )

        if not price_match:
            counts["no_price"] += 1
            continue

        price = float(price_match.group(1).replace(",", ""))

        if price <= 0 or price > MAX_PRICE:
            counts["over_budget"] += 1
            continue

        discount_matches = re.findall(
            r"(\d{1,3})\s*%\s*(?:off|discount)",
            text,
            re.IGNORECASE,
        )
        discounts = [int(value) for value in discount_matches]

        if discounts and max(discounts) < MIN_DISCOUNT:
            counts["discount_too_low"] += 1
            continue

        if discounts:
            discount_note = (
                f"Advertised discount: {max(discounts)}% "
                "(not independently verified)"
            )
        else:
            discount_note = (
                "Discount not stated; this is a candidate, "
                "not a verified glitch."
            )

        message = (
            f"🔎 **Potential Amazon deal candidate**\n"
            f"**{title[:220]}**\n"
            f"Price mentioned: ${price:.2f}\n"
            f"{discount_note}\n"
            f"Deal/source link: {deal['link']}\n"
            f"Source: DealNews RSS"
        )

        if counts["sent"] >= MAX_ALERTS_PER_RUN:
            print("Alert limit reached; remaining candidates skipped.")
            break

        try:
            send_discord(message)
        except Exception as error:
            print(f"DISCORD ERROR: {error}")
            raise

        new_seen.add(guid)
        counts["sent"] += 1
        print(f"ALERT SENT: {title}")

    SEEN_FILE.write_text(json.dumps(sorted(new_seen), indent=2))

    print("\n--- Diagnostic summary ---")
    for name, count in counts.items():
        print(f"{name}: {count}")

    if feed_errors:
        print("WARNING: One or more feeds failed.")

    print(f"Finished. New matching alerts sent: {counts['sent']}")


if __name__ == "__main__":
    main()
