"""One-time script: remove misclassified deals and reset listings for re-test."""
import os, re
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["overland_finder"]

# Remove any deals for non-target vehicles (Honda, etc.)
target_makes = ["Toyota", "Jeep", "Lexus", "Nissan", "Ford", "Chevrolet"]
bad = db.deals.delete_many({"make": {"$nin": target_makes}})
print(f"Deleted {bad.deleted_count} non-target deal(s)")

# Reset all listings back to pending
result = db.raw_listings.update_many(
    {"status": {"$in": ["processing", "error", "evaluated", "skipped"]}},
    {"$set": {"status": "pending"}}
)
print(f"Reset {result.modified_count} listings back to pending")

# Status summary
for status in ["pending", "skipped", "evaluated", "processing", "error"]:
    count = db.raw_listings.count_documents({"status": status})
    if count:
        print(f"  {status}: {count}")

print(f"Deals in DB: {db.deals.count_documents({})}")
