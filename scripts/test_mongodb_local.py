#!/usr/bin/env python3
"""
Local MongoDB Connection Test
Tests connection to MongoDB Atlas and demonstrates batch pattern
"""
import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def test_mongodb_connection():
    """Test MongoDB Atlas connection and create collections"""
    
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri or "<password>" in mongodb_uri:
        print("❌ ERROR: MongoDB URI not configured in .env file")
        print("   Copy .env.example to .env and add your MongoDB password")
        return False
    
    try:
        print("🔌 Connecting to MongoDB Atlas...")
        client = MongoClient(mongodb_uri)
        
        # Test connection
        client.admin.command('ping')
        print("✅ Connected successfully!")
        
        # Get database
        db = client.overland_finder
        print(f"📊 Using database: {db.name}")
        
        # List existing collections
        existing_collections = db.list_collection_names()
        print(f"📁 Existing collections: {existing_collections or 'None'}")
        
        # Create/verify collections needed for batch pattern
        collections_needed = {
            "raw_listings": "Raw scraped data (pending evaluation)",
            "deals": "Evaluated deals with AI analysis",
            "batch_checkpoints": "Batch state for resumability",
            "job_history": "Audit trail of function executions"
        }
        
        print("\n🏗️  Setting up collections for batch pattern:")
        for collection_name, description in collections_needed.items():
            collection = db[collection_name]
            
            # Create indexes based on collection type
            if collection_name == "raw_listings":
                collection.create_index([("url", 1)], unique=True)
                collection.create_index([("status", 1)])
                collection.create_index([("scraped_at", -1)])
                print(f"   ✅ {collection_name} - {description}")
                print(f"      Indexes: url (unique), status, scraped_at")
                
            elif collection_name == "deals":
                collection.create_index([("evaluation.value_score", -1)])
                collection.create_index([("timestamp", -1)])
                collection.create_index([("listing.vin", 1)])
                print(f"   ✅ {collection_name} - {description}")
                print(f"      Indexes: value_score, timestamp, vin")
                
            elif collection_name == "batch_checkpoints":
                collection.create_index([("status", 1)])
                print(f"   ✅ {collection_name} - {description}")
                
            elif collection_name == "job_history":
                collection.create_index([("started_at", -1)])
                collection.create_index([("function_name", 1)])
                print(f"   ✅ {collection_name} - {description}")
                print(f"      Indexes: started_at, function_name")
        
        # Insert a test checkpoint to verify write access
        print("\n🧪 Testing write access with sample checkpoint...")
        db.batch_checkpoints.replace_one(
            {"_id": "test-connection"},
            {
                "_id": "test-connection",
                "last_run": datetime.now(),
                "status": "test",
                "message": "Local connection test successful"
            },
            upsert=True
        )
        print("   ✅ Write successful!")
        
        # Count documents in each collection
        print("\n📈 Document counts:")
        for collection_name in collections_needed.keys():
            count = db[collection_name].count_documents({})
            print(f"   {collection_name}: {count} documents")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    print("=" * 60)
    print("MongoDB Atlas Connection Test")
    print("=" * 60)
    print()
    
    if test_mongodb_connection():
        print("\n🎉 SUCCESS! MongoDB is ready for local development")
        print("\nNext steps:")
        print("  1. Run scrapers locally to populate raw_listings")
        print("  2. Run evaluator to process pending listings")
        print("  3. Test checkpoint/resume pattern")
    else:
        print("\n❌ Setup failed. Fix errors above and try again.")
