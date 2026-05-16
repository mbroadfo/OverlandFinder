"""
Backfill mileage on eBay deals where odometer was never recorded.
Also removes deals (and marks raw_listings skipped) when the eBay
listing is no longer available — no point holding stale data.

Strategy per deal:
  1. Regex on stored title/description (no API cost)
  2. EbayDetailFetcher API call using item ID from URL
     - Got mileage → update deal
     - Listing gone → delete deal + mark raw_listing skipped

Usage:
    python -u scripts/backfill_mileage.py           # dry run
    python -u scripts/backfill_mileage.py --apply   # apply changes
"""
import os
import re
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.enrichment.ebay_detail import EbayDetailFetcher

MILEAGE_RE   = re.compile(
    r"(?:odometer|mileage|miles?)[:\s]*([0-9]{1,3}(?:,?[0-9]{3})*)\s*(?:mi(?:les?)?)?",
    re.IGNORECASE,
)
INLINE_MI_RE = re.compile(r"\b([0-9]{1,3}(?:,?[0-9]{3})+)\s*(?:mi|miles)\b", re.IGNORECASE)
EBAY_ITEM_RE = re.compile(r"/itm/(\d+)")
REQUEST_DELAY = 0.5


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
    print(f"\n{'='*60}", flush=True)
    print(f"  backfill_mileage.py — {tag}", flush=True)
    print(f"{'='*60}\n", flush=True)

    db      = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]
    fetcher = EbayDetailFetcher()

    missing = list(db.deals.find(
        {"source": "ebay", "mileage": None},
        {"_id": 1, "title": 1, "url": 1, "description": 1},
    ))
    total = len(missing)
    print(f"eBay deals missing mileage: {total}\n", flush=True)

    text_hits = api_hits = expired = no_id = 0

    for i, deal in enumerate(missing, 1):
        _id   = deal["_id"]
        title = deal.get("title", "")
        desc  = deal.get("description", "")
        url   = deal.get("url", "")

        # Step 1 — regex on stored text (free)
        mileage = extract_mileage_from_text(f"{title} {desc}")
        if mileage:
            text_hits += 1
            print(f"  [{i}/{total}] text  {title[:55]}  →  {mileage:,} mi", flush=True)
            if apply:
                db.deals.update_one({"_id": _id}, {"$set": {"mileage": mileage}})
            continue

        # Step 2 — eBay detail API
        item_id = item_id_from_url(url)
        if not item_id:
            no_id += 1
            continue

        detail  = fetcher.fetch(item_id)
        mileage = detail.get("mileage")
        time.sleep(REQUEST_DELAY)

        if mileage:
            api_hits += 1
            print(f"  [{i}/{total}] api   {title[:55]}  →  {mileage:,} mi", flush=True)
            if apply:
                db.deals.update_one({"_id": _id}, {"$set": {"mileage": mileage}})
        else:
            # Listing is gone — clean it out of both collections
            expired += 1
            print(f"  [{i}/{total}] gone  {title[:55]}", flush=True)
            if apply:
                db.deals.delete_one({"_id": _id})
                db.raw_listings.update_many(
                    {"url": url},
                    {"$set": {"status": "skipped", "skip_reason": "listing_removed"}},
                )

    print(f"\n{'='*60}", flush=True)
    print(f"Results ({tag}):", flush=True)
    print(f"  Mileage found (text) : {text_hits}", flush=True)
    print(f"  Mileage found (API)  : {api_hits}", flush=True)
    print(f"  Listing gone/expired : {expired}  {'← deleted' if apply else '← would delete'}", flush=True)
    print(f"  No item ID in URL    : {no_id}", flush=True)
    print(f"  Total deals updated  : {text_hits + api_hits}", flush=True)
    if apply:
        print(f"  Total deals deleted  : {expired}", flush=True)
    print(flush=True)


if __name__ == "__main__":
    run("--apply" in sys.argv)
