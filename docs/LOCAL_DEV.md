# 🖥️ Local Development Setup

## Quick Start

### 1. Set Up Python Environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```powershell
# Copy example file
cp .env.example .env

# Edit .env and add your MongoDB password
code .env
```

**Required changes in `.env`:**
- Replace `<password>` in `MONGODB_URI` with your actual MongoDB password
- Optionally add Foundry API key (not needed for scraping tests)

### 3. Test MongoDB Connection

```powershell
python scripts/test_mongodb_local.py
```

**Expected output:**
```
✅ Connected successfully!
📊 Using database: overland_finder
🏗️  Setting up collections for batch pattern:
   ✅ raw_listings - Raw scraped data (pending evaluation)
   ✅ deals - Evaluated deals with AI analysis
   ✅ batch_checkpoints - Batch state for resumability
   ✅ job_history - Audit trail of function executions
🎉 SUCCESS! MongoDB is ready for local development
```

## Local Function Development

### Run Individual Functions Locally

```powershell
# Test Craigslist scraper (no Azure deployment needed)
python src/scrapers/craigslist_scraper.py

# Test deal evaluator
python src/evaluator/deal_evaluator.py

# Test SMS sender
python src/jobs/sms_notifier.py
```

### Use Azure Functions Core Tools (Optional)

For testing actual Azure Functions locally:

```powershell
# Install Azure Functions Core Tools (if not installed)
# Download from: https://learn.microsoft.com/azure/azure-functions/functions-run-local

# Navigate to functions directory
cd functions

# Start local Functions runtime
func start
```

## Batch Pattern Testing

### Simulate Checkpoint/Resume

```python
# scripts/test_batch_pattern.py
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URI"))
db = client.overland_finder

# Simulate a scraper run with checkpointing
checkpoint = db.batch_checkpoints.find_one({"_id": "craigslist-scraper"}) or {
    "_id": "craigslist-scraper",
    "last_page": 0,
    "items_processed": 0
}

start_page = checkpoint["last_page"]
print(f"Resuming from page {start_page}")

# Simulate processing 5 pages
for page in range(start_page, start_page + 5):
    print(f"Processing page {page}...")
    
    # Update checkpoint after each page (resilience!)
    checkpoint["last_page"] = page + 1
    checkpoint["last_run"] = datetime.now()
    db.batch_checkpoints.replace_one(
        {"_id": "craigslist-scraper"},
        checkpoint,
        upsert=True
    )
    print(f"  ✅ Checkpoint saved at page {page + 1}")

print(f"✅ Completed! Next run will start from page {checkpoint['last_page']}")
```

## Development Workflow

1. **Write function code** in `src/` folders
2. **Test locally** with `python src/...`
3. **Verify MongoDB state** with MongoDB Compass or Atlas UI
4. **Commit working code** to git
5. **Deploy to Azure** when ready (via GitHub Actions or `func azure functionapp publish`)

## Useful Commands

```powershell
# View MongoDB collections in Atlas web UI
# https://cloud.mongodb.com → Browse Collections

# Check Python environment
python --version
pip list

# Run tests
pytest tests/

# Format code
black src/
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'pymongo'"
```powershell
# Make sure virtual environment is activated
.\.venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

### "MongoServerError: Authentication failed"
- Check MongoDB password in `.env`
- Verify network access is allowed (0.0.0.0/0) in MongoDB Atlas

### "Connection timeout"
- Check internet connection
- Verify MongoDB Atlas cluster is running (not paused)

## Next Steps

Once local development is working:
1. Build out scraper functions with checkpointing
2. Test batch processing with small datasets
3. Verify error handling and resumability
4. Deploy to Azure Functions when ready

**Cost: $0 while developing locally!** ✨
