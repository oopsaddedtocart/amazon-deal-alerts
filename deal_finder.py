import json
import os
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

FEED_URL = "https://www.dealnews.com/rss/todays-edition"
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
MAX_PRICE = 30.00
MIN_DISCOUNT = 70
SEEN_FILE = Path("seen_deals.json")


def fetch_feed():
    request = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "DealFinder/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return ET.fromstring(response.read())


def clean(text):
    return re.sub(r"\s+", " ", unescape(
        re.sub(r"<[^>]+>", " ", text or "")
    )).strip()


def get_text(item, name):
    return item.findtext(name, default="", namespaces={
        "content": "http://purl.org/rss/1.0/modules/content/"
    })


def find_amazon_link(text):
    links = re.findall(
        r"""https?://(?:www\.)?amazon\.com/[^\s"'<>]+""",
        text,
        re.IGNORECASE
    )
    return links[0].rstrip(").,") if links else None


def load_seen():
    try:
        return set(json.loads(SEEN_FILE.read_text()))
    except (OSError, ValueError):
        return set()


def main():
    if not WEBHOOK:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL secret.")

    root = fetch_feed()
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("RSS feed has no channel.")

    seen = load_seen()
    new_ids = set(seen)
    sent = 0

    for item in channel.findall("item"):
        title = clean(get_text(item, "title"))
        description = clean(get_text(item, "description"))
        link = clean(get_text(item, "link"))
        guid = clean(get_text(item, "guid")) or link

        if not guid or guid in seen:
            continue

        text = f"{title} {description}"
        if "amazon" not in text.lower():
            continue

        # Do not treat "up to 70% off" as a verified 70% discount
        if re.search(r"\bup to\s+\d+\s*%\s*off", text, re.I):
            continue

        discounts = [
            int(n) for n in re.findall(
                r"(\d{2,3})\s*%\s*(?:off|discount)",
                text, re.I
            )
        ]
        if not discounts or max(discounts) < MIN_DISCOUNT:
            continue

        prices = [
            float(n.replace(",", ""))
            for n in re.findall(r"\$\s*([\d,]+(?:\.\d{1,2})?)", title)
        ]
        if not prices:
            continue

        price = min(prices)
        if price > MAX_PRICE:
            continue

        amazon_link = find_amazon_link(description) or link

        message = (
            f"🔎 **Potential Amazon deal**\n"
            f"**{title[:220]}**\n"
            f"Price mentioned: ${price:.2f}\n"
            f"Discount mentioned: {max(discounts)}% "
            f"(not independently verified)\n"
            f"Link: {amazon_link}\n"
            f"Source: DealNews RSS"
        )

        payload = json.dumps({"content": message}).encode("utf-8")
        request = urllib.request.Request(
            WEBHOOK,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status not in (200, 204):
                    raise RuntimeError(
                        f"Unexpected Discord status: {response.status}"
                    )
        except urllib.error.HTTPError as error:
            raise RuntimeError(
                f"Discord returned HTTP {error.code}: "
                f"{error.read().decode(errors='replace')}"
            ) from error

        new_ids.add(guid)
        sent += 1

    SEEN_FILE.write_text(json.dumps(sorted(new_ids), indent=2))
    print(f"Finished. New matching alerts sent: {sent}")


if __name__ == "__main__":
    main()
