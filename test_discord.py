
import os
import json
import urllib.request
import urllib.error

def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

    if not webhook_url:
        raise SystemExit(
            "ERROR: DISCORD_WEBHOOK_URL is missing. "
            "Check GitHub Settings > Secrets and variables > Actions."
        )

    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        raise SystemExit(
            "ERROR: The webhook URL format looks incorrect. "
            "Copy a fresh URL from your Discord channel's Webhooks settings."
        )

    payload = json.dumps({
        "content": "✅ Amazon Deal Alerts: Discord connection successful!",
        "allowed_mentions": {"parse": []}
    }).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
    "Content-Type": "application/json",
    "User-Agent": "DiscordBot (https://github.com, 1.0)"
},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(f"SUCCESS: Discord returned HTTP {response.status}.")
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        print(f"Discord returned HTTP {error.code}.")
        print(f"Response details: {details}")
        raise
    except urllib.error.URLError as error:
        print(f"Could not connect to Discord: {error.reason}")
        raise

if __name__ == "__main__":
    main()
