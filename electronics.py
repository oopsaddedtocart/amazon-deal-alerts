
from deal_scanner import scan_category

KEYWORDS = [
    "headphones",
    "earbuds",
    "charger",
    "usb",
    "cable",
    "keyboard",
    "mouse",
    "monitor",
    "camera",
    "smart home",
    "router",
    "ssd",
    "hard drive",
    "power bank",
    "electronics",
    "bluetooth",
    "speaker",
    "webcam",
    "computer",
    "laptop",
    "tablet",
    "phone case",
    "memory card",
    "flash drive",
    "gaming",
    "controller"
]

if __name__ == "__main__":
    scan_category("Electronics", KEYWORDS)
