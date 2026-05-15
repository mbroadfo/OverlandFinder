"""
Cleanup script: removes junk from raw_listings and deals collections.

Targets three categories:
  1. Keyword matches  — salvage title, flood damage, airbags deployed, etc.
  2. Bad title_status — salvage, rebuilt, reconstructed (Craigslist structured field)
  3. Low-score deals  — value_score < 50 saved before the threshold was raised

Usage:
    python scripts/cleanup_blocklist.py           # dry run (default)
    python scripts/cleanup_blocklist.py --apply   # make changes
"""
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

SKIP_KEYWORDS = [
    "salvage title", "rebuilt title", "reconstructed title",
    "flood title", "flood damage", "flood car",
    "frame damage", "bent frame", "structural damage",
    "airbag deployed", "airbags deployed", "no airbags",
    "for parts", "parts only", "parts car",
    "blown head gasket", "seized engine", "locked engine",
    "no title",
]

SALVAGE_TITLE_STATUSES = ["salvage", "rebuilt", "reconstructed", "parts only", "lemon"]

MIN_SCORE = 50


def keyword_filter(fields: list[str]) -> dict:
    """MongoDB $or filter matching any SKIP_KEYWORD in any of the given fields."""
    clauses = [
        {field: {"$regex": kw, "$options": "i"}}
        for kw in SKIP_KEYWORDS
        for field in fields
    ]
    return {"$or": clauses}


def run(apply: bool) -> None:
    tag = "APPLY" if apply else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"  cleanup_blocklist.py — {tag}")
    print(f"{'='*60}\n")

    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI not set in .env")
        sys.exit(1)

    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    db = client["overland_finder"]

    # ------------------------------------------------------------------
    # raw_listings — mark skipped (preserve for audit trail)
    # ------------------------------------------------------------------
    raw_kw_filter = {
        **keyword_filter(["title", "description"]),
        "status": {"$ne": "skipped"},
    }
    raw_ts_filter = {
        "title_status": {"$in": SALVAGE_TITLE_STATUSES},
        "status": {"$ne": "skipped"},
    }

    raw_kw_count = db.raw_listings.count_documents(raw_kw_filter)
    raw_ts_count = db.raw_listings.count_documents(raw_ts_filter)

    print("raw_listings:")
    print(f"  keyword matches (to mark skipped) : {raw_kw_count}")
    print(f"  bad title_status (to mark skipped): {raw_ts_count}")

    if apply:
        if raw_kw_count:
            r = db.raw_listings.update_many(
                raw_kw_filter,
                {"$set": {"status": "skipped", "skip_reason": "keyword_cleanup"}},
            )
            print(f"  -> Marked {r.modified_count} raw_listings skipped (keyword)")
        if raw_ts_count:
            r = db.raw_listings.update_many(
                raw_ts_filter,
                {"$set": {"status": "skipped", "skip_reason": "title_status_cleanup"}},
            )
            print(f"  -> Marked {r.modified_count} raw_listings skipped (title_status)")

    # ------------------------------------------------------------------
    # deals — hard delete (these should never have been saved)
    # ------------------------------------------------------------------
    deals_kw_filter  = keyword_filter(["title", "description"])
    deals_ts_filter  = {"title_status": {"$in": SALVAGE_TITLE_STATUSES}}
    deals_low_filter = {"value_score": {"$lt": MIN_SCORE}}

    deals_kw_count   = db.deals.count_documents(deals_kw_filter)
    deals_ts_count   = db.deals.count_documents(deals_ts_filter)
    deals_low_count  = db.deals.count_documents(deals_low_filter)

    print(f"\ndeals:")
    print(f"  keyword matches (to delete)      : {deals_kw_count}")
    print(f"  bad title_status (to delete)     : {deals_ts_count}")
    print(f"  score < {MIN_SCORE} (to delete)         : {deals_low_count}")

    if apply:
        for f, label in [
            (deals_kw_filter,  "keyword"),
            (deals_ts_filter,  "title_status"),
            (deals_low_filter, f"score<{MIN_SCORE}"),
        ]:
            r = db.deals.delete_many(f)
            if r.deleted_count:
                print(f"  -> Deleted {r.deleted_count} deals ({label})")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total_raw = raw_kw_count + raw_ts_count
    total_deals = deals_kw_count + deals_ts_count + deals_low_count

    print(f"\n{'='*60}")
    if apply:
        print(f"Done. {total_raw} raw_listings marked skipped, {total_deals} deals deleted.")
    else:
        print(f"DRY RUN: would mark {total_raw} raw_listings skipped "
              f"and delete {total_deals} deals.")
        print("Re-run with --apply to make changes.")
    print()


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    run(apply)
