import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

SEARCHES = [
    "seasoning 6 pack",
    "barbecue sauce 12 pack",
    "candy bulk multipack",
    "household cleaning supplies case",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

def test_amazon():

    for search in SEARCHES:

        print("\n========================")
        print("Searching:", search)

        url = (
            "https://www.amazon.com/s?k="
            + quote_plus(search)
        )

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=25
            )

            print("HTTP status:", response.status_code)

            if response.status_code != 200:
                print("Amazon request blocked or failed.")
                continue

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            page_text = soup.get_text(
                " ", strip=True
            ).lower()

            if (
                "enter the characters you see below" in page_text
                or "validatecaptcha" in response.url.lower()
            ):
                print("Amazon CAPTCHA detected.")
                continue

            cards = soup.select(
                '[data-component-type="s-search-result"]'
            )

            print("Search result cards:", len(cards))

            for card in cards[:5]:

                asin = card.get("data-asin", "")

                title_element = card.select_one("h2")

                price_element = card.select_one(
                    ".a-price .a-offscreen"
                )

                title = (
                    title_element.get_text(" ", strip=True)
                    if title_element else "Unknown"
                )

                price = (
                    price_element.get_text(" ", strip=True)
                    if price_element else "Not available"
                )

                print("------------------------")
                print("ASIN:", asin)
                print("Title:", title)
                print("Price:", price)

        except requests.RequestException as error:
            print("Request error:", error)


if __name__ == "__main__":
    test_amazon()