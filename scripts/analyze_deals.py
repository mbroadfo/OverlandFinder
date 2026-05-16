"""Analyze deals collection and print a summary."""
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from collections import defaultdict, Counter

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["overland_finder"]

deals = list(db.deals.find({}, {
    "title": 1, "make": 1, "model": 1, "year": 1, "price": 1, "mileage": 1,
    "value_score": 1, "recommended_action": 1, "source": 1, "location": 1,
    "discount_percent": 1, "market_value_est": 1, "analysis": 1, "url": 1,
    "wish_list_name": 1,
}).sort("value_score", -1))

print(f"Total deals: {len(deals)}")
print()

# By rating
action_counts = Counter(d.get("recommended_action", "?") for d in deals)
print("=== By Rating ===")
for action in ["STRONG BUY", "GOOD DEAL", "FAIR", "PASS", "RED FLAG"]:
    print(f"  {action}: {action_counts.get(action, 0)}")
print()

# By make/model
print("=== By Make/Model ===")
model_groups = defaultdict(list)
for d in deals:
    key = d.get("wish_list_name") or f"{d.get('make', '')} {d.get('model', '')}".strip()
    model_groups[key].append(d)

for name, items in sorted(model_groups.items()):
    scores = [d.get("value_score", 0) for d in items if d.get("value_score")]
    avg = sum(scores) / len(scores) if scores else 0
    actions = Counter(d.get("recommended_action", "?") for d in items)
    print(f"  {name}: {len(items)} deals | avg score {avg:.0f} | {dict(actions)}")
print()

# By year bucket
print("=== By Year ===")
year_groups = defaultdict(list)
for d in deals:
    y = d.get("year")
    if y:
        bucket = f"{(y // 5) * 5}-{(y // 5) * 5 + 4}"
        year_groups[bucket].append(d)
    else:
        year_groups["unknown"].append(d)
for bucket in sorted(year_groups.keys()):
    items = year_groups[bucket]
    scores = [d.get("value_score", 0) for d in items if d.get("value_score")]
    avg = sum(scores) / len(scores) if scores else 0
    print(f"  {bucket}: {len(items)} deals | avg score {avg:.0f}")
print()

# By source
print("=== By Source ===")
src_counts = Counter(d.get("source", "?") for d in deals)
for src, cnt in src_counts.most_common():
    print(f"  {src}: {cnt}")
print()

# Top 15 deals
print("=== Top 15 Deals (by score) ===")
for d in deals[:15]:
    score = d.get("value_score", 0)
    action = d.get("recommended_action", "?")
    year = d.get("year", "?")
    price = d.get("price", 0)
    mileage = d.get("mileage")
    mi_str = f"{mileage:,} mi" if mileage else "no mileage"
    name = d.get("wish_list_name") or d.get("title", "?")
    discount = d.get("discount_percent", 0) or 0
    title = d.get("title", "")
    print(f"  [{score:.0f}] {action} | {year} {name}")
    print(f"        {title}")
    print(f"        ${price:,} | {mi_str} | {discount:.0f}% below market est")
    print(f"        {(d.get('url') or '')[:90]}")
    print()
