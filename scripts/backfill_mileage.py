"""
Backfill mileage on eBay deals where odometer was never recorded.

Strategy (in order):
  1. Regex the existing title/description for a mileage figure
  2. Call EbayDetailFetcher using the item ID extracted from the deal URL

Usage:
    python scripts/backfill_mileage.py           # dry run — shows counts
    python scripts/backfill_mileage.py --apply   # writes mileage to deals
"""
import os
import re
import sys
import time
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from src.enrichment.ebay_detail import EbayDetailFetcher

MILEAGE_RE = re.compile(
    r"(?:odometer|mileage|miles?)[:\s]*([0-9]{1,3}(?:,?[0-9]{3})*)\s*(?:mi(?:les?)?)?",
    re.IGNORECASE,
)
INLINE_MI_RE = re.compile(r"\b([0-9]{1,3}(?:,?[0-9]{3})+)\s*(?:mi|miles)\b", re.IGNORECASE)
EBAY_ITEM_RE = re.compile(r"/itm/(\d+)")

REQUEST_DELAY = 1.0


def extract_mileage_from_text(text: str) -> int | None:
    m = MILEAGE_RE.search(text)
    if m:
        return int(m.group(1).replace(",", ""))
    m = INLINE_MI_RE.search(text)
    if m:
        val = int(m.group(1).replace(",", ""))
        if 1_000 <= val <= 500_000:
            return val
    return None


def item_id_from_url(url: str) -> str | None:
    m = EBAY_ITEM_RE.search(url or "")
    return m.group(1) if m else None


def run(apply: bool) -> None:
    tag = "APPLY" if apply else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"  backfill_mileage.py — {tag}")
    print(f"{'='*60}\n")

    db = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]
    fetcher = EbayDetailFetcher()

    missing = list(db.deals.find(
        {"source": "ebay", "mileage": None},
        {"_id": 1, "title": 1, "url": 1, "description": 1}
    ))
    print(f"eBay deals missing mileage: {len(missing)}\n")

    text_hits = 0
    api_hits  = 0
    api_miss  = 0
    expired   = 0

    for deal in missing:
        _id   = deal["_id"]
        title = deal.get("title", "")
        desc  = deal.get("description", "")
        url   = deal.get("url", "")

        # Step 1 — regex on stored text
        mileage = extract_mileage_from_text(f"{title} {desc}")
        source  = "text"

        # Step 2 — eBay detail API
        if mileage is None:
            item_id = item_id_from_url(url)
            if item_id:
                detail = fetcher.fetch(item_id)
                mileage = detail.get("mileage")
                if mileage:
                    source = "api"
                    api_hits += 1
                else:
                    expired += 1
                    api_miss += 1
                time.sleep(REQUEST_DELAY)
            else:
                api_miss += 1
        else:
            text_hits += 1

        if mileage:
            print(f"  [{source}] {title[:60]}  →  {mileage:,} mi")
            if apply:
                db.deals.update_one({"_id": _id}, {"$set": {"mileage": mileage}})

    print(f"\nResults:")
    print(f"  Found via text regex : {text_hits}")
    print(f"  Found via eBay API   : {api_hits}")
    print(f"  Not found (expired)  : {expired}")
    print(f"  Total fillable       : {text_hits + api_hits}")

    if not apply:
        print("\nRe-run with --apply to write changes.")
    print()


if __name__ == "__main__":
    run("--apply" in sys.argv)
