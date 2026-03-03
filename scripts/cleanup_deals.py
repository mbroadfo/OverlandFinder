"""Remove misclassified deals where the stored title doesn't match the inferred make."""
import os, re
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["overland_finder"]

# Keyword map: if a deal's make is X, the title should contain at least one keyword
MAKE_TITLE_KEYWORDS = {
    "Toyota":     ["toyota", "4runner", "tacoma", "fj cruiser", "land cruiser"],
    "Lexus":      ["lexus", "gx470", "gx460"],
    "Jeep":       ["jeep", "wrangler", "cherokee"],
    "Nissan":     ["nissan", "xterra", "frontier"],
    "Ford":       ["ford", "bronco"],
    "Chevrolet":  ["chevrolet", "chevy", "colorado"],
}

removed = 0
for deal in db.deals.find({}):
    make = deal.get("make", "")
    title = deal.get("title", "").lower()
    keywords = MAKE_TITLE_KEYWORDS.get(make, [])
    if keywords and not any(kw in title for kw in keywords):
        db.deals.delete_one({"_id": deal["_id"]})
        print(f"Removed misclassified deal: '{deal['title']}' (make={make})")
        removed += 1

print(f"\nRemoved {removed} bad deal(s)")
print(f"Remaining deals: {db.deals.count_documents({})}")
