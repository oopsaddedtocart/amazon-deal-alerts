
import os
import re
import json
import time
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

WEBHOOK = os.environ["DISCORD_WEBHOOK"]
MAX_PRICE = 50.00
MIN_DISCOUNT = 55
MAX_ALERTS = 8

# Public feeds. Some may occasionally block requests or be unavailable.
FEEDS = {
    "Slickdeals": (
        "https://slickdeals.net/newsearch.php?"
        "mode=frontpage&rss=1&searcharea=deals&searchin=first"
    ),
    "DealNews": "https://www.dealnews.com/rss/todays-edition",
    "Reddit Deals": "https://www.reddit.com/r/DealsReddit/.rss",
    "Reddit General Deals": "https://www.reddit.com/r/deals/.rss",
    "Reddit Amazon": "https://www.reddit.com/r/AmazonDeals/.rss",
    "Reddit Walmart": "https://www.reddit.com/r/Walmart/.rss",
    "Reddit Target": "https://www.reddit.com/r/Target/.rss",
    "Reddit Home Depot": "https://www.reddit.com/r/HomeDepot/.rss",
    "Reddit Lowes": "https://www.reddit.com/r/Lowes/.rss",
}

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
    "KitchenAid", "Cuisinart", "DeWalt", "Milwaukee",
    "Craftsman", "WD-40", "Energizer", "Duracell",
    "YETI", "Stanley", "Owala", "Hydro Flask",
    "Ring", "Blink", "Tapo", "Amazon Basics", "Nintendo",
    "Pokémon", "Funko", "Bandai", "Kleenex", "Pampers",
    "Huggies", "Gerber", "Aveeno", "Colgate", "Persil",
    "Swiffer", "Mr. Clean", "Instant Pot", "Black+Decker",
    "DeWalt", "Milwaukee", "Kobalt", "Lodge", "OXO",
    "Gorilla", "Scotch", "Sharpie", "Nongshim",
    "Gorilla Grip", "Rubbermaid", "Cricut", "Brother",
    "HP", "Canon", "Epson", "Microsoft", "Western Digital",
    "WD", "Seagate", "Corsair", "Razer", "HyperX",
    "Pokémon TCG", "Mega", "Play-Doh", "Paw Patrol",
]

MULTIPACK = re.compile(
    r"\b\d+\s*(?:pack|pk|count|ct|pcs|pieces|rolls|"
    r"cans|bottles|bars|pairs|bags|boxes|sets)\b|"
    r"\b(?:pack|case|set)\s+of\s+\d+\b|"
    r"\bmulti[\s-]?pack\b|\bbulk pack\b|\bcase pack\b",
    re.I,
)

GLITCH_WORDS = re.compile(
    r"price error|pricing error|price glitch|price mistake|"
    r"mispriced|misprice|pricing mistake|price drop error|"
    r"possible glitch|penny deal|penny item|decimal error|"
    r"wrong price|checkout glitch",
    re.I,
)

RETAILERS = {
    "Amazon": ["amazon.com", "amzn.to", "a.co"],
    "Home Depot": ["homedepot.com"],
    "Lowe's": ["lowes.com"],
    "Walmart": ["walmart.com", "walmrt.us"],
    "Target": ["target.com"],
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; PersonalDealFinder/1.0)"
})


def local_name(tag):
    return tag.split("}")[-1].split(":")[-1].lower()


def brand_in_title(title):
    for brand in BRANDS:
        if re.search(
            r"(?<![A-Za-z0-9])" + re.escape(brand) +
            r"(?![A-Za-z0-9])",
            title,
            re.I,
        ):
            return brand
    return None


def retailer_for(url, text):
    host = (urlparse(url).hostname or "").lower()

    for retailer, domains in RETAILERS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return retailer

    # Some deal titles identify the retailer but don't expose
    # its direct product URL in the feed.
    for retailer, pattern in [
        ("Home Depot", r"\bhome depot\b"),
        ("Lowe's", r"\blowe'?s\b"),
        ("Walmart", r"\bwalmart\b"),
        ("Target", r"\btarget\b"),
        ("Amazon", r"\bamazon\b"),
    ]:
        if re.search(pattern, text, re.I):
            return retailer

    return None


def entry_fields(entry):
    title = ""
    source_url = ""
    content_parts = []
    image_url = ""

    for child in entry.iter():
        tag = local_name(child.tag)

        if tag == "title" and not title:
            title = "".join(child.itertext()).strip()

        elif tag == "link":
            href = child.attrib.get("href")
            rel = child.attrib.get("rel", "alternate")

            if href and rel in ("alternate", "") and not source_url:
                source_url = href
            elif not href and child.text and not source_url:
                source_url = child.text.strip()

        elif tag in ("description", "summary", "encoded", "content"):
            if child.text:
                content_parts.append(child.text)
            else:
                content_parts.append(" ".join(child.itertext()))

        elif tag in ("thumbnail", "content", "enclosure"):
            candidate = child.attrib.get("url", "")
            if candidate.startswith("https://") and not image_url:
                image_url = candidate

    return title, source_url, "\n".join(content_parts), image_url


def extract_links_and_image(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        candidate = urljoin(base_url, a["href"])
        if candidate.startswith("https://"):
            links.append(candidate)

    image = None
    for img in soup.find_all("img"):
        candidate = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-original")
        )
        if candidate:
            candidate = urljoin(base_url, candidate)
            if candidate.startswith("https://"):
                image = candidate
                break

    return links, image


def parse_price_and_discount(title, text):
    combined = title + " " + text

    # Prefer the first dollar amount in the title: deal posts
    # commonly put the current price before the old price.
    amounts = re.findall(
        r"\$\s*([\d,]+(?:\.\d{1,2})?)", title
    )

    if not amounts:
        amounts = re.findall(
            r"\$\s*([\d,]+(?:\.\d{1,2})?)", text
        )

    price = None
    if amounts:
        try:
            price = float(amounts[0].replace(",", ""))
        except ValueError:
            pass

    discount = None
    match = re.search(
        r"(\d{1,3})\s*%\s*(?:off|discount|savings)",
        combined,
        re.I,
    )

    if match:
        discount = int(match.group(1))

    # Estimate a discount only when the post clearly identifies
    # an old/regular/list price. This is still not price-history proof.
    if discount is None and re.search(
        r"\b(?:was|regular price|original price|list price|retail price)\b",
        combined,
        re.I,
    ):
        all_amounts = re.findall(
            r"\$\s*([\d,]+(?:\.\d{1,2})?)", combined
        )
        try:
            values = [
                float(x.replace(",", "")) for x in all_amounts
            ]
            if len(values) >= 2 and values[0] < max(values[1:]):
                original = max(values[1:])
                discount = round(
                    (original - values[0]) / original * 100
                )
        except (ValueError, ZeroDivisionError):
            pass

    return price, discount


def collect_deals():
    deals = []
    diagnostics = {}

    for source_name, feed_url in FEEDS.items():
        try:
            response = session.get(feed_url, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            entries = [
                item for item in root.iter()
                if local_name(item.tag) in ("item", "entry")
            ]

            diagnostics[source_name] = (
                f"feed OK; {len(entries)} entries"
            )

            for entry in entries:
                title, source_url, html, feed_image = entry_fields(entry)

                if not title or not source_url:
                    continue

                links, html_image = extract_links_and_image(
                    html, source_url
                )

                combined_text = BeautifulSoup(
                    html, "html.parser"
                ).get_text(" ", strip=True)

                brand = brand_in_title(title)
                if not brand:
                    continue

                # Look for an actual retailer product link if present.
                product_url = None
                retailer = None

                for link in links:
                    found = retailer_for(link, "")
                    if found:
                        product_url = link
                        retailer = found
                        break

                if not retailer:
                    retailer = retailer_for(
                        source_url, title + " " + combined_text
                    )

                if not retailer:
                    continue

                price, discount = parse_price_and_discount(
                    title, combined_text
                )

                if price is None or price <= 0 or price > MAX_PRICE:
                    continue

                glitch = bool(
                    GLITCH_WORDS.search(title + " " + combined_text)
                )

                if not glitch and (
                    discount is None or discount < MIN_DISCOUNT
                ):
                    continue

                # A retailer-specific source link may be the only link
                # exposed by a feed. Clearly label it in the alert.
                destination = product_url or source_url
                multipack = bool(MULTIPACK.search(title))

                key = hashlib.sha256(
                    (destination + title).encode()
                ).hexdigest()

                deals.append({
                    "key": key,
                    "title": title,
                    "brand": brand,
                    "retailer": retailer,
                    "price": price,
                    "discount": discount,
                    "glitch": glitch,
                    "multipack": multipack,
                    "url": destination,
                    "direct": product_url is not None,
                    "image": feed_image or html_image,
                    "source": source_name,
                })

        except Exception as exc:
            diagnostics[source_name] = (
                f"FAILED: {type(exc).__name__}: {exc}"
            )

    return deals, diagnostics


def send_alert(deal):
    if deal["glitch"]:
        kind = "⚠️ POTENTIAL PRICE ERROR / GLITCH"
    else:
        kind = "🔥 DEEP DISCOUNT"

    discount_text = (
        f'{deal["discount"]}% advertised off'
        if deal["discount"] is not None
        else "Discount not stated; source flags possible error"
    )

    pack_text = (
        "Multipack/case candidate"
        if deal["multipack"]
        else "Single item or pack size unclear"
    )

    link_text = (
        "Direct retailer product link"
        if deal["direct"]
        else "Deal-source link (direct product link unavailable)"
    )

    embed = {
        "title": deal["title"][:256],
        "url": deal["url"],
        "description": (
            f'**Retailer:** {deal["retailer"]}\n'
            f'**Brand:** {deal["brand"]}\n'
            f'**Listed price:** ${deal["price"]:.2f}\n'
            f'**Discount:** {discount_text}\n'
            f'**Type:** {kind}\n'
            f'**Pack:** {pack_text}\n'
            f'**Link:** {link_text}\n'
            f'**Found via:** {deal["source"]}\n\n'
            "Verify current price, quantity, seller, stock, and "
            "checkout total before buying. Price errors may be corrected "
            "or orders cancelled."
        ),
        "footer": {
            "text": "Personal deal finder • Price not independently verified"
        },
    }

    if deal["image"]:
        embed["thumbnail"] = {"url": deal["image"]}

    response = session.post(
        WEBHOOK,
        json={"embeds": [embed]},
        timeout=20,
    )
    response.raise_for_status()


def main():
    state_file = Path("seen.json")

    try:
        seen = set(json.loads(state_file.read_text()))
    except (OSError, ValueError):
        seen = set()

    deals, diagnostics = collect_deals()

    print("SOURCE DIAGNOSTICS")
    for source, status in diagnostics.items():
        print(f"{source}: {status}")

    print(f"Total candidates before filters: {len(deals)}")

    # Prioritize multipacks, then explicit price-error candidates,
    # then the largest stated discounts.
    deals.sort(
        key=lambda d: (
            d["multipack"],
            d["glitch"],
            d["discount"] or 0,
        ),
        reverse=True,
    )

    sent = 0
    new_seen = set(seen)

    for deal in deals:
        if deal["key"] in seen:
            continue

        try:
            send_alert(deal)
            new_seen.add(deal["key"])
            sent += 1
            print("ALERT SENT:", deal["title"])
            time.sleep(1)

            if sent >= MAX_ALERTS:
                break

        except Exception as exc:
            print("DISCORD SEND ERROR:", exc)
            raise

    # Keep the most recent identifiers.
    state_file.write_text(
        json.dumps(list(new_seen)[-3000:], indent=2)
    )

    print("Candidates found:", len(deals))
    print("New Discord alerts sent:", sent)
    print("Previously seen candidates:", len(seen))


if __name__ == "__main__":
    main()
