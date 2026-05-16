"""
Cleanup script: marks raw_listings as skipped and removes deals for vehicles
outside each wish list item's [min_year, max_year] window.

Usage:
    python scripts/cleanup_old_vehicles.py           # dry run (default)
    python scripts/cleanup_old_vehicles.py --apply   # actually make changes
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

WISH_LIST_PATH = Path(__file__).parent.parent / "wish_list.json"


def load_year_windows() -> list[dict]:
    """Return wish list items that have at least one year bound."""
    with open(WISH_LIST_PATH, encoding="utf-8") as f:
        items = json.load(f)
    return [i for i in items if "min_year" in i or "max_year" in i]


def run(apply: bool) -> None:
    tag = "APPLY" if apply else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"  cleanup_old_vehicles.py — {tag}")
    print(f"{'='*60}\n")

    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI not set in .env")
        sys.exit(1)

    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    db = client["overland_finder"]

    items = load_year_windows()
    total_raw_updated = 0
    total_deals_deleted = 0

    for item in items:
        name     = item["name"]
        min_year = item.get("min_year")
        max_year = item.get("max_year")
        print(f"{name}  (min={min_year}, max={max_year})")

        buckets = []
        if min_year:
            buckets.append(("too old",  {"$lt": min_year}, f"year_below_{min_year}"))
        if max_year:
            buckets.append(("too new",  {"$gt": max_year}, f"year_above_{max_year}"))

        for label, year_filter, skip_reason in buckets:
            raw_filter = {
                "wish_list_name": name,
                "year": year_filter,
                "status": {"$ne": "skipped"},
            }
            deals_filter = {"wish_list_name": name, "year": year_filter}

            raw_count   = db.raw_listings.count_documents(raw_filter)
            deals_count = db.deals.count_documents(deals_filter)

            print(f"  [{label}]  raw_listings: {raw_count}  |  deals: {deals_count}")

            if apply:
                if raw_count:
                    r = db.raw_listings.update_many(
                        raw_filter,
                        {"$set": {"status": "skipped", "skip_reason": skip_reason}},
                    )
                    print(f"    -> Marked {r.modified_count} raw_listings skipped")
                if deals_count:
                    r = db.deals.delete_many(deals_filter)
                    print(f"    -> Deleted {r.deleted_count} deals")

            total_raw_updated   += raw_count
            total_deals_deleted += deals_count

        print()

    print(f"{'='*60}")
    if apply:
        print(f"Done. {total_raw_updated} raw_listings marked skipped, "
              f"{total_deals_deleted} deals deleted.")
    else:
        print(f"DRY RUN complete. Would mark {total_raw_updated} raw_listings skipped "
              f"and delete {total_deals_deleted} deals.")
        print("Re-run with --apply to make changes.")
    print()


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    run(apply)
