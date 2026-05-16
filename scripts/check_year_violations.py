"""Quick check for deals and raw_listings outside wish_list year windows."""
import json, os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
db = MongoClient(os.getenv("MONGODB_URI"))["overland_finder"]

wish_list = json.loads((Path(__file__).parent.parent / "wish_list.json").read_text())

for item in wish_list:
    name = item["name"]
    min_y = item.get("min_year")
    max_y = item.get("max_year")

    deals_old  = db.deals.count_documents({"wish_list_name": name, "year": {"$lt": min_y}}) if min_y else 0
    deals_new  = db.deals.count_documents({"wish_list_name": name, "year": {"$gt": max_y}}) if max_y else 0
    raw_old    = db.raw_listings.count_documents({"wish_list_name": name, "year": {"$lt": min_y}, "status": {"$ne": "skipped"}}) if min_y else 0
    raw_new    = db.raw_listings.count_documents({"wish_list_name": name, "year": {"$gt": max_y}, "status": {"$ne": "skipped"}}) if max_y else 0

    print(f"{name}  (min={min_y}, max={max_y})")
    print(f"  deals:        {deals_old} too old,  {deals_new} too new")
    print(f"  raw_listings: {raw_old} too old,  {raw_new} too new")
