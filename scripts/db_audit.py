"""Pre-scrape DB audit — identify cleanup candidates."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
db = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]

VALID = {"Jeep Wrangler", "Jeep Gladiator", "Toyota 4Runner",
         "Lexus GX460", "Toyota FJ Cruiser", "Toyota Tacoma TRD"}

errors   = db.raw_listings.count_documents({"status": "error"})
stuck    = db.raw_listings.count_documents({"status": "processing"})
stale_p  = db.raw_listings.count_documents({"status": "pending", "wish_list_name": {"$nin": list(VALID)}})
renegade = db.deals.count_documents({"wish_list_name": "Jeep Renegade Trailhawk"})
below_55 = db.deals.count_documents({"value_score": {"$gte": 50, "$lt": 55}})
pending  = db.raw_listings.count_documents({"status": "pending"})

print(f"Pending raw_listings         : {pending}")
print(f"Stuck processing docs        : {stuck}  {'← needs reset' if stuck else ''}")
print(f"Error raw_listings           : {errors}  ← won't retry without manual reset")
print(f"Stale pending (removed items): {stale_p}  ← evaluator will skip anyway")
print(f"Renegade Trailhawk deals     : {renegade}  ← orphaned, safe to delete")
print(f"Deals scored 50-54           : {below_55}  ← below new threshold, safe to delete")
