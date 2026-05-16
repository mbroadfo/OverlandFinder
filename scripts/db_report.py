"""Quick MongoDB stats report across all collections."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from collections import Counter

load_dotenv()
db = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]

# Collection sizes
print("=== Collections ===")
for col in sorted(db.list_collection_names()):
    print(f"  {col}: {db[col].count_documents({}):,} docs")

print()

# raw_listings by status
print("=== Raw Listings by Status ===")
for r in db.raw_listings.aggregate([
    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
]):
    print(f"  {r['_id']}: {r['count']:,}")

print()

# raw_listings by source
print("=== Raw Listings by Source ===")
for r in db.raw_listings.aggregate([
    {"$group": {"_id": "$source", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
]):
    print(f"  {r['_id']}: {r['count']:,}")

print()

# deals summary
deals = list(db.deals.find({}, {
    "value_score": 1, "recommended_action": 1, "wish_list_name": 1,
    "source": 1, "price": 1, "mileage": 1, "year": 1, "title": 1, "discount_percent": 1,
}))
print(f"=== Deals ({len(deals)} total) ===")
action_counts = Counter(d.get("recommended_action", "?") for d in deals)
for a in ["STRONG BUY", "GOOD DEAL", "FAIR", "PASS", "RED FLAG"]:
    print(f"  {a}: {action_counts.get(a, 0)}")

print()
print("=== Deals by Vehicle ===")
for r in db.deals.aggregate([
    {"$group": {"_id": "$wish_list_name", "count": {"$sum": 1}, "avg_score": {"$avg": "$value_score"}}},
    {"$sort": {"count": -1}},
]):
    print(f"  {r['_id'] or '(unknown)'}: {r['count']} deals | avg score {r['avg_score']:.0f}")

print()
print("=== Deals by Source ===")
for r in db.deals.aggregate([
    {"$group": {"_id": "$source", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
]):
    print(f"  {r['_id']}: {r['count']}")

print()
print("=== Top 10 Deals ===")
top = db.deals.find({}, {
    "title": 1, "wish_list_name": 1, "year": 1, "price": 1,
    "mileage": 1, "value_score": 1, "recommended_action": 1,
    "source": 1, "discount_percent": 1, "url": 1,
}).sort("value_score", -1).limit(10)

for d in top:
    mi = f"{d['mileage']:,} mi" if d.get("mileage") else "no mileage"
    score = d.get("value_score", 0)
    action = d.get("recommended_action", "?")
    year = d.get("year", "?")
    name = d.get("wish_list_name", "?")
    price = d.get("price", 0) or 0
    disc = d.get("discount_percent") or 0
    source = d.get("source", "?")
    title = (d.get("title") or "")[:70]
    print(f"  [{score:.0f}] {action} | {year} {name} | ${price:,} | {mi} | {source}")
    print(f"       {title}")
    if disc:
        print(f"       {disc:.0f}% below market est")
    print()

print("=== Price Observations ===")
obs_count = db.price_observations.count_documents({})
print(f"  Total: {obs_count:,}")
for r in db.price_observations.aggregate([
    {"$group": {"_id": "$wish_list_name", "count": {"$sum": 1}, "avg_market": {"$avg": "$claude_market_est"}}},
    {"$sort": {"count": -1}},
]):
    print(f"  {r['_id']}: {r['count']} observations | avg market est ${r['avg_market']:,.0f}")
