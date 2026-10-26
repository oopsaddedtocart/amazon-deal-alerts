
import os
import re
import json
import time
import hashlib
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

WEBHOOK = os.environ["DISCORD_WEBHOOK"]
MAX_PRICE = 20.00
MIN_DISCOUNT = 55
MAX_ALERTS = 8

BASE = "https://saveblitz.com"
PAGES = [
    f"{BASE}/ranking/most-discount",
    *[f"{BASE}/ranking/most-discount-{n}" for n in range(2, 6)]
]

# Recognizable brands; add more if desired.
BRANDS = [
    "LEGO", "Hasbro", "Mattel", "Fisher-Price", "VTech",
    "Crayola", "Sharpie", "Anker", "Logitech", "Samsung",
    "Sony", "Apple", "Belkin", "TP-Link", "SanDisk",
    "Kingston", "JBL", "Bose", "Roku", "Philips",
    "Oral-B", "Crest", "Dove", "Olay", "Gillette",
    "CeraVe", "Cetaphil", "Neutrogena", "Tide", "Gain",
    "Dawn", "Febreze", "Clorox", "Lysol", "Ziploc",
    "Glad", "Hefty", "Rubbermaid", "Scotch-Brite", "OXO",
    "Pyrex", "Ninja", "Shark", "Bissell", "Keurig",
    "KitchenAid", "Cuisinart", "Instant Pot", "DeWalt",
    "Milwaukee", "Craftsman", "WD-40", "Energizer",
    "Duracell", "YETI", "Stanley", "Owala", "Hydro Flask",
    "Ring", "Blink", "Tapo", "Amazon Basics", "3M",
    "Scotch", "Nintendo", "Pokémon", "Funko", "Bandai",
    "Kleenex", "Pampers", "Huggies", "Gerber", "Aveeno",
    "Colgate", "Palmolive", "Persil", "Swiffer", "Mr. Clean"
]

MULTIPACK = re.compile(
    r"\b(?:\d+\s*(?:pack|pk|count|ct|pcs|pieces|rolls|"
    r"cans|bottles|bars|pairs)|"
    r"(?:pack|case|set)\s+of\s+\d+|"
    r"multi[\s-]?pack|bulk pack|case pack|bundle)\b",
    re.I
)

def find_brand(title):
    for brand in BRANDS:
        if re.search(
            r"(?<![A-Za-z0-9])" + re.escape(brand) +
            r"(?![A-Za-z0-9])",
            title,
            re.I
        ):
            return brand
    return None

def extract_product(link):
    node = link

    # Find the nearest product card containing title, image,
    # price and discount.
    for _ in range(9):
        if node is None:
            return None

        text = node.get_text(" ", strip=True)
        heading = node.find(["h2", "h3"])
        image = node.find("img")

        if (
            heading and image
            and re.search(r"\$\s?\d", text)
            and re.search(r"-\s*\d{1,3}\s*%", text)
        ):
            break

        node = node.parent
    else:
        return None

    title = heading.get_text(" ", strip=True)
    brand = find_brand(title)

    if not brand or not MULTIPACK.search(title):
        return None

    prices = re.findall(
        r"\$\s?([\d,]+(?:\.\d{1,2})?)", text
    )
    discount_match = re.search(
        r"-\s*(\d{1,3})\s*%", text
    )

    if not prices or not discount_match:
        return None

    price = float(prices[0].replace(",", ""))
    discount = int(discount_match.group(1))

    if price > MAX_PRICE or discount < MIN_DISCOUNT:
        return None

    href = link.get("href", "")
    parsed = urlparse(href)

    # Only use individual Amazon product links.
    if not (
        parsed.hostname
        and (
            parsed.hostname == "amazon.com"
            or parsed.hostname.endswith(".amazon.com")
        )
    ):
        return None

    image_url = (
        image.get("src")
        or image.get("data-src")
        or image.get("data-lazy-src")
    )

    if not image_url or not image_url.startswith("https://"):
        return None

    return {
        "title": title,
        "brand": brand,
        "price": price,
        "discount": discount,
        "url": href,
        "image": image_url,
    }

state_file = Path("seen.json")
seen = set(json.loads(state_file.read_text())) if state_file.exists() else set()
new_seen = set(seen)
sent = 0
scanned = 0
matched = 0

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; DealFinder/1.0)"
})

for page_url in PAGES:
    try:
        response = session.get(page_url, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as exc:
        print(f"Could not read source page: {page_url}: {exc}")
        continue

    for link in soup.find_all("a", href=True):
        href = link["href"]
        host = urlparse(href).hostname or ""

        if not (host == "amazon.com" or host.endswith(".amazon.com")):
            continue

        scanned += 1
        product = extract_product(link)

        if not product:
            continue

        matched += 1
        key = hashlib.sha256(
            (product["url"] + product["title"]).encode()
        ).hexdigest()

        if key in seen:
            continue

        embed = {
            "title": product["title"][:256],
            "url": product["url"],
            "description": (
                f"**Brand:** {product['brand']}\n"
                f"**Price listed:** ${product['price']:.2f}\n"
                f"**Source-stated discount:** "
                f"{product['discount']}% off\n\n"
                f"📦 Multipack candidate\n"
                f"⚠️ Verify the Amazon price, seller, "
                f"quantity and discount before buying."
            ),
            "image": {"url": product["image"]},
            "footer": {
                "text": "Source: SaveBlitz • Not independently verified"
            }
        }

        try:
            result = session.post(
                WEBHOOK,
                json={"embeds": [embed]},
                timeout=20
            )
            result.raise_for_status()
            new_seen.add(key)
            sent += 1
            print("Discord alert sent:", product["title"])

            time.sleep(1)

            if sent >= MAX_ALERTS:
                break

        except Exception as exc:
            print("Discord send failed:", exc)
            raise

    if sent >= MAX_ALERTS:
        break

# Save IDs to prevent repeat alerts.
new_seen = set(list(new_seen)[-3000:])
state_file.write_text(json.dumps(sorted(new_seen), indent=2))

print(f"Product links scanned: {scanned}")
print(f"Products matching filters: {matched}")
print(f"New Discord alerts sent: {sent}")
