import os
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from html import unescape

FEED_URL = os.getenv(
    "DEAL_FEED_URL",
    "https://www.dealnews.com/rss/todays-edition"
)

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
STATE_FILE = Path("seen_ids.json")


def clean_text(value):
    value = unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def get_feed():
    request = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "PersonalDealFinder/1.0"}
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        return ET.fromstring(response.read())


def load_seen():
    try:
        return set(json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        ))
    except (OSError, ValueError):
        return set()


def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(sorted(seen)[-2000:], indent=2),
        encoding="utf-8"
    )


def send_discord(title, link, category):
    if not WEBHOOK:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL secret is missing."
        )

    message = (
        f"**Amazon Deal Finder: {category}**\n"
        f"{title[:250]}\n{link}\n"
        "Source: DealNews"
    )

    payload = json.dumps({
        "content": message,
        "allowed_mentions": {"parse": []}
    }).encode("utf-8")

    request = urllib.request.Request(
        WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status not in (200, 204):
            raise RuntimeError("Discord alert failed.")


def scan_category(category, keywords):
    root = get_feed()
    seen = load_seen()
    found = []

    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        description = clean_text(
            item.findtext("description", "")
        )
        link = (item.findtext("link", "") or "").strip()
        item_id = (
            item.findtext("guid", "") or link or title
        ).strip()

        if not title or not link or item_id in seen:
            continue

        searchable = (
            f"{title} {description} {link}"
        ).lower()

        if "amazon" not in searchable:
            continue

        if any(word.lower() in searchable for word in keywords):
            found.append((item_id, title, link))

    for item_id, title, link in found[:15]:
        send_discord(title, link, category)
        seen.add(item_id)

    save_seen(seen)
    print(f"{category}: {min(len(found), 15)} alerts sent.")