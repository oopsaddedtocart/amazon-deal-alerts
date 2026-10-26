
import requests
from urllib.parse import quote_plus
import os

WEBHOOK = os.environ["DISCORD_WEBHOOK"]

SEARCHES = [
    '"case of 12" brand multipack',
    '"pack of 24" household products',
    '"bulk pack" name brand',
    '"multipack" cleaning supplies',
    '"case pack" personal care',
    '"pack of 6" name brand',
    '"pack of 12" toys',
    '"bulk pack" office supplies',
    '"multipack" kitchen products',
    '"case of 24" name brand',
]

lines = [
    "🔎 **Amazon Multipack Deal Research**",
    "Target: name brands, multipacks and case lots.",
    "Check for missing images, current price under $20,",
    "and a genuine discount of 55% or more before buying.",
    ""
]

for query in SEARCHES:
    url = "https://www.amazon.com/s?k=" + quote_plus(query)
    lines.append(f"• [{query}]({url})")

message = "\n".join(lines)

response = requests.post(
    WEBHOOK,
    json={"content": message},
    timeout=20
)
response.raise_for_status()

print("Amazon search links sent to Discord!")
