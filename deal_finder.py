import os
import re
import json
import hashlib
import requests
import feedparser

MAX_PRICE = 50
MIN_DISCOUNT = 50

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

# Add authorized RSS deal feeds here.
FEEDS = [
    url.strip()
    for url in os.environ.get("DEAL_FEEDS", "").split(",")
    if url.strip()
]

SEEN_FILE = "seen_deals.json"

STORES = [
    "amazon",
    "walmart",
    "target",
    "home depot",
    "lowe's",
    "lowes",
]

PRIORITY_WORDS = [
    "multipack",
    "multi-pack",
    "6 pack",
    "12 pack",
    "24 pack",
    "case",
    "bundle",
    "household",
    "seasoning",
    "detergent",
    "cleaning",
    "candy",
    "grocery",
    "toy",
]

EXCLUDED_WORDS = [
    "shirt",
    "pants",
    "dress",
    "shoes",
    "jeans",
    "hoodie",
]


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f)


def extract_price(text):
    matches = re.findall(
        r"\$\s?(\d+(?:\.\d{1,2})?)",
        text
    )

    if not matches:
        return None

    return float(matches[0])


def extract_discount(text):
    matches = re.findall(
        r"(\d{1,3})\s?%\s*(?:off|discount)",
        text,
        re.IGNORECASE
    )

    if not matches:
        return None

    return int(matches[0])


def get_store(text):
    text = text.lower()

    for store in STORES:
        if store in text:
            return store.title()

    return None


def is_excluded(text):
    text = text.lower()

    return any(
        word in text
        for word in EXCLUDED_WORDS
    )


def priority_score(text, discount):
    text = text.lower()

    score = 0

    for word in PRIORITY_WORDS:
        if word in text:
            score += 10

    if discount >= 70:
        score += 25

    if discount >= 90:
        score += 50

    return score


def send_discord(title, price, discount, link, store, score):
    if not WEBHOOK:
        print("Missing DISCORD_WEBHOOK_URL")
        return False

    possible_glitch = discount >= 90

    if possible_glitch:
        heading = "🚨 POSSIBLE PRICE GLITCH"
        color = 16711680
    elif discount >= 70:
        heading = "🔥 HUGE DISCOUNT"
        color = 16753920
    else:
        heading = "💰 DEAL ALERT"
        color = 3066993

    payload = {
        "embeds": [
            {
                "title": heading,
                "description": title[:1000],
                "url": link,
                "color": color,
                "fields": [
                    {
                        "name": "Store",
                        "value": store,
                        "inline": True
                    },
                    {
                        "name": "Reported Price",
                        "value": f"${price:.2f}",
                        "inline": True
                    },
                    {
                        "name": "Reported Discount",
                        "value": f"{discount}% OFF",
                        "inline": True
                    },
                    {
                        "name": "Priority Score",
                        "value": str(score),
                        "inline": True
                    }
                ],
                "footer": {
                    "text": (
                        "Unverified feed listing. "
                        "Confirm retailer price and stock."
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
        return True

    except requests.RequestException as error:
        print("Discord error:", error)
        return False


def scan_deals():
    seen = load_seen()

    new_alerts = 0

    if not FEEDS:
        print("No DEAL_FEEDS configured.")
        print("Add RSS URLs before running live scans.")
        return

    for feed_url in FEEDS:
        print("Checking feed:", feed_url)

        try:
            response = requests.get(
                feed_url,
                timeout=20,
                headers={
                    "User-Agent": "DealAlertBot/1.0"
                }
            )

            response.raise_for_status()

            feed = feedparser.parse(response.content)

        except Exception as error:
            print("Feed error:", error)
            continue

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")

            text = title + " " + summary

            if not link:
                continue

            deal_id = hashlib.sha256(
                link.encode("utf-8")
            ).hexdigest()

            if deal_id in seen:
                continue

            if is_excluded(title):
                continue

            store = get_store(text)

            if not store:
                continue

            price = extract_price(text)
            discount = extract_discount(text)

            if price is None or discount is None:
                continue

            if price > MAX_PRICE:
                continue

            if discount < MIN_DISCOUNT:
                continue

            score = priority_score(text, discount)

            print("MATCH:", title)

            success = send_discord(
                title,
                price,
                discount,
                link,
                store,
                score
            )

            if success:
                seen.add(deal_id)
                new_alerts += 1

    save_seen(seen)

    print("New matching alerts sent:", new_alerts)


if __name__ == "__main__":
    scan_deals()