"""Quick count of eBay deals missing mileage and what's recoverable from text."""
import os, re, sys
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

MILEAGE_RE = re.compile(
    r"(?:odometer|mileage|miles?)[:\s]*([0-9]{1,3}(?:,?[0-9]{3})*)\s*(?:mi(?:les?)?)?",
    re.IGNORECASE,
)
INLINE_MI_RE = re.compile(r"\b([0-9]{1,3}(?:,?[0-9]{3})+)\s*(?:mi|miles)\b", re.IGNORECASE)

db = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]

total   = db.deals.count_documents({})
has_mil = db.deals.count_documents({"mileage": {"$ne": None}})
missing = list(db.deals.find({"source": "ebay", "mileage": None}, {"title": 1, "description": 1, "url": 1}))

print(f"Total deals       : {total}")
print(f"Have mileage      : {has_mil}")
print(f"eBay missing mil  : {len(missing)}")

text_hits = 0
for d in missing:
    text = f"{d.get('title','')} {d.get('description','')}"
    m = MILEAGE_RE.search(text) or INLINE_MI_RE.search(text)
    if m:
        text_hits += 1

print(f"Recoverable (text): {text_hits}")
print(f"Need API call     : {len(missing) - text_hits}")
