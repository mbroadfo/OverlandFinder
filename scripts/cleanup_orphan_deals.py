"""Remove deals and raw_listings for vehicles no longer in wish_list.json."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
db = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]

wish_list = json.loads((Path(__file__).parent.parent / "wish_list.json").read_text())
valid = {item["name"] for item in wish_list}

orphan_deals = list(db.deals.find(
    {"wish_list_name": {"$nin": list(valid)}},
    {"_id": 1, "wish_list_name": 1, "title": 1, "url": 1},
))

if not orphan_deals:
    print("No orphaned deals found.")
else:
    print(f"Orphaned deals to remove ({len(orphan_deals)}):")
    urls = []
    for d in orphan_deals:
        print(f"  [{d.get('wish_list_name')}] {d.get('title', '?')}")
        if d.get("url"):
            urls.append(d["url"])

    db.deals.delete_many({"_id": {"$in": [d["_id"] for d in orphan_deals]}})
    print(f"Deleted {len(orphan_deals)} deals.")

    if urls:
        result = db.raw_listings.update_many(
            {"url": {"$in": urls}},
            {"$set": {"status": "skipped", "skip_reason": "orphaned_wish_list"}},
        )
        print(f"Marked {result.modified_count} raw_listings as skipped.")
