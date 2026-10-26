
import os
import re
import json
import hashlib
import requests
import feedparser
from pathlib import Path
from urllib.parse import urlencode

MAX_PRICE = 20.00
MIN_DISCOUNT = 55
WEBHOOK = os.environ["DISCORD_WEBHOOK"]

# Common recognizable brands. Add more as needed.
BRANDS = [
    "LEGO", "Nerf", "Hasbro", "Mattel", "Fisher-Price",
    "VTech", "Logitech", "Anker", "Belkin", "TP-Link",
    "Samsung", "Sony", "Apple", "Amazon", "Kindle",
    "Ring", "Blink", "Tapo", "Philips", "Philips Hue",
    "Oral-B", "Crest", "Dove", "Olay", "Gillette",
    "Nivea", "L'Oreal", "L'Oreal Paris", "Maybelline",
    "Revlon", "CeraVe", "Cetaphil", "Neutrogena",
    "Scotch-Brite", "Dawn", "Tide", "Gain", "Febreze",
    "Ziploc", "Glad", "Rubbermaid", "OXO", "Pyrex",
    "Instant Pot", "Ninja", "Shark", "Dyson", "Keurig",
    "KitchenAid", "Cuisinart", "Bissell", "Dewalt",
    "Milwaukee", "Craftsman", "Klein Tools", "WD-40",
    "Crayola", "Sharpie", "Canon", "Epson", "HP",
    "Seagate", "Western Digital", "WD", "Kingston",
    "SanDisk", "JBL", "Bose", "Roku", "Fire TV",
    "YETI", "Stanley", "Owala", "Hydro Flask",
    "Funko", "Pokemon", "Pokémon", "Bandai", "Nintendo"
]

STATE = Path("seen.json")
seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()

# Public deal-search RSS. Results depend on what the
# deal publisher currently indexes; this is not all Amazon.
feed_url = "https://slickdeals.net/newsearch.php?" + urlencode({
    "q": "Amazon",
    "searcharea": "deals",
    "searchin": "first",
    "rss": "1"
})

feed = feedparser.parse(feed_url)
print("Feed URL:", feed_url)
print("Feed entries found:", len(feed.entries))

for entry in feed.entries[:10]:
    print("TITLE:", entry.get("title", "No title"))
    print("LINK:", entry.get("link", "No link"))
if feed.bozo and not feed.entries:
    raise RuntimeError("Could not read the deal feed.")

new_ids = set(seen)
sent = 0

for entry in feed.entries:
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    link = entry.get("link", "")
    text = f"{title} {summary}"
    lower = text.casefold()

    # Only alert on a recognized brand.
    brand = next((b for b in BRANDS if b.casefold() in lower), None)
    if not brand:
        continue

    # Require an explicitly stated discount percentage.
    discounts = re.findall(
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:off|discount|savings?)",
        text, re.I
    )
    if not discounts:
        discounts = re.findall(
            r"(\d{1,3}(?:\.\d+)?)\s*%\s*off", title, re.I
        )
    if not discounts:
        continue

    discount = max(map(float, discounts))
    if discount < MIN_DISCOUNT or discount > 100:
        continue

    # Require a stated dollar price at or below $20.
    prices = re.findall(r"\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)", text)
    prices = [float(p.replace(",", "")) for p in prices]
    if not prices:
        continue

    price = min(prices)
    if price > MAX_PRICE:
        continue

    # Deduplicate deal posts across runs.
    key = hashlib.sha256(
        (entry.get("id", link) + title).encode()
    ).hexdigest()
    if key in seen:
        continue

    message = (
        f"**Potential Amazon deal — check before buying**\n"
        f"**Brand match:** {brand}\n"
        f"**Post:** {title[:220]}\n"
        f"**Price mentioned:** ${price:.2f}\n"
        f"**Discount stated by source:** {discount:g}%\n"
        f"{link}\n"
        f"⚠️ Price, stock, seller, and discount not independently verified."
    )

    response = requests.post(
        WEBHOOK, json={"content": message}, timeout=20
    )
    response.raise_for_status()
    new_ids.add(key)
    sent += 1

# Keep a rolling history to avoid duplicate alerts.
new_ids = set(list(new_ids)[-3000:])
STATE.write_text(json.dumps(sorted(new_ids), indent=2))
print(f"Finished. New alerts sent: {sent}")
