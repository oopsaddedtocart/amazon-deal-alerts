import json
import os
import urllib.error
import urllib.request

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

def main():
    if not WEBHOOK_URL:
        raise SystemExit(
            "ERROR: DISCORD_WEBHOOK_URL secret is missing."
        )

    payload = {
        "content": "✅ Amazon deal finder: Discord connection test successful!"
    }

    request = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AmazonDealFinder/1.0"
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print("HTTP status:", response.status)
            print("Discord webhook test successful!")

    except urllib.error.HTTPError as error:
        print("HTTP status:", error.code)
        print("Response:", error.read().decode("utf-8", errors="replace"))
        raise SystemExit(1)

    except urllib.error.URLError as error:
        print("Connection error:", error.reason)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
