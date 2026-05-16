"""Reset error raw_listings to pending so they get retried."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
db = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]

result = db.raw_listings.update_many(
    {"status": "error"},
    {"$set": {"status": "pending"}, "$unset": {"error": ""}},
)
print(f"Reset {result.modified_count} error docs to pending")
