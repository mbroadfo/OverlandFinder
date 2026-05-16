"""Purge price_observations for wish list items no longer being tracked."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
db = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]

VALID = {"Jeep Wrangler", "Jeep Gladiator", "Toyota 4Runner", "Lexus GX460", "Toyota FJ Cruiser"}

rows = list(db.price_observations.aggregate([
    {"$group": {"_id": "$wish_list_name", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
]))

stale = [r for r in rows if r["_id"] not in VALID]
keep  = [r for r in rows if r["_id"] in VALID]

print("Will DELETE:")
total_delete = 0
for r in stale:
    print(f"  {r['_id']}: {r['count']:,}")
    total_delete += r["count"]

print(f"\nWill KEEP:")
total_keep = 0
for r in keep:
    print(f"  {r['_id']}: {r['count']:,}")
    total_keep += r["count"]

print(f"\nDeleting {total_delete:,} stale observations, keeping {total_keep:,}...")
stale_names = [r["_id"] for r in stale]
result = db.price_observations.delete_many({"wish_list_name": {"$in": stale_names}})
print(f"Done — {result.deleted_count:,} documents deleted.")
