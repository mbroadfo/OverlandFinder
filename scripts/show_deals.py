"""Show deal evaluation summary from MongoDB."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["overland_finder"]

print("=== Raw Listings Status ===")
for s in ["pending", "evaluated", "skipped", "processing", "error"]:
    n = db.raw_listings.count_documents({"status": s})
    if n:
        print(f"  {s}: {n}")

print("\n=== Deals Found (sorted by score) ===")
deals = list(
    db.deals.find(
        {}, {"title": 1, "price": 1, "value_score": 1, "recommended_action": 1, "red_flags": 1, "_id": 0}
    ).sort("value_score", -1)
)
print(f"Total deals: {len(deals)}")
for d in deals:
    flags = " ⚠️" if d.get("red_flags") else ""
    print(f"  {d['value_score']:5.1f}  ${d['price']:>7,}  {d.get('recommended_action','')[:30]:<30}  {d['title'][:50]}{flags}")
