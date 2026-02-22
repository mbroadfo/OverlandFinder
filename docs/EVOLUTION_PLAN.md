# 🚀 OverlandFinder Evolution Plan
## From Chatbot to Autonomous Deal-Finding Agent

---

## 🎯 Project Vision

**Transform OverlandFinder into an autonomous background agent that:**
- 🔍 Scrapes vehicle listings from multiple sources every 4 hours
- 🤖 Uses AI to evaluate deals and detect red flags
- 💾 Stores findings in MongoDB Atlas with full vehicle details
- 📱 Sends daily SMS digest with top deals
- 📊 Provides web dashboard for browsing deals (personal eBay for overlanding rigs)
- 💰 Runs on Azure for ~$5-10/month

---

## 🏗️ Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2-3: WEB SCRAPING & AI EVALUATION                         │
│ Azure Container Apps Job (Scheduled: Every 4 hours)             │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│ │ Craigslist  │  │ AutoTrader  │  │ Facebook    │             │
│ │ Scraper     │  │ Scraper     │  │ Marketplace │             │
│ └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│        │                │                │                      │
│        └────────────────┴────────────────┘                      │
│                         ↓                                       │
│              ┌──────────────────────┐                          │
│              │ VIN Decoder (NHTSA)  │                          │
│              │ AI Deal Evaluator    │                          │
│              │ (Azure Foundry GPT-4)│                          │
│              └──────────┬───────────┘                          │
│ Runtime: ~15 min | vCPU: 0.5 | RAM: 1GB                       │
│ Cost: $2-3/month                                               │
└────────────────────────┬───────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA STORAGE                                           │
│ MongoDB Atlas M0 (FREE - 512MB)                                 │
│ Collections:                                                    │
│ - deals (listings + evaluations + VIN data)                    │
│ - scrape_history (audit log)                                   │
│ - user_favorites (starred deals)                               │
│                                                                 │
│ Azure Blob Storage (~$0.10/month)                              │
│ - Vehicle images from listings                                 │
│ - Daily backup snapshots (JSON archives)                       │
│ - Scraper logs                                                 │
└────────────────────────┬───────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 5: NOTIFICATIONS                                          │
│ Azure Function (Timer Trigger: Daily @ 8:00 AM)                │
│ - Query MongoDB for top 3 deals (last 24h)                     │
│ - Send SMS via SMTP (Verizon gateway)                          │
│ Runtime: <10 sec | Cost: FREE (under 1M executions)           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 8: WEB DASHBOARD (Personal eBay UI)                      │
│ Azure Static Web App or App Service                            │
│ ┌─────────────────────────────────────────────────┐            │
│ │ Frontend: React/Next.js                          │            │
│ │ - Deal browsing with filters (make/model/price) │            │
│ │ - VIN decoder lookup                             │            │
│ │ - Favorite/star deals                            │            │
│ │ - Power BI Embedded (analytics)                  │            │
│ └─────────────────────────────────────────────────┘            │
│                         ↕                                       │
│ ┌─────────────────────────────────────────────────┐            │
│ │ Backend: FastAPI or Azure Functions             │            │
│ │ - REST API for MongoDB queries                  │            │
│ │ - Authentication (Entra ID)                      │            │
│ │ - Favorite management                            │            │
│ └─────────────────────────────────────────────────┘            │
│ Cost: $5-10/month (Static Web App or small App Service)       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CROSS-CUTTING CONCERNS                                          │
│                                                                 │
│ Key Vault (FREE):                                              │
│ - MongoDB URI, SMTP credentials, API keys                      │
│                                                                 │
│ Managed Identity:                                              │
│ - No secrets in code (Entra ID authentication)                 │
│ - ACA Jobs → Key Vault, Blob Storage, Foundry                 │
│                                                                 │
│ Application Insights (FREE - first 5GB):                       │
│ - Scraper telemetry, error tracking                            │
│ - KQL queries for debugging                                    │
│ - Alerts on job failures                                       │
│                                                                 │
│ GitHub Actions CI/CD:                                          │
│ - Auto-deploy on push to main                                  │
│ - Build Docker images → Azure Container Registry              │
│ - Update Container Apps Jobs + Functions                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📅 Implementation Phases

### **Phase 0: Foundation & Infrastructure** ⏱️ Week 1
**Goal:** Establish Azure infrastructure with Terraform and automated deployment pipeline

**Status:** 🔄 **IN PROGRESS**

**Tasks:**
1. ✅ **Project Structure Reorganization**
   - Created `src/` package structure (scrapers, evaluator, data, utils, jobs, api)
   - Created `infrastructure/terraform/` for IaC
   - Created `docs/`, `functions/`, `tests/`, `scripts/` folders
   - Moved files preserving git history (git mv)
   - Updated import paths for new structure

2. ✅ **Terraform Infrastructure as Code**
   - `infrastructure/terraform/providers.tf` - Azure/AzureAD providers config
   - `infrastructure/terraform/variables.tf` - Input variables with sensitive flags
   - `infrastructure/terraform/main.tf` - All Azure resources:
     - Resource Group (`rg-overland-finder-dev`)
     - Storage Account with containers (vehicle-images, logs)
     - Log Analytics Workspace + Application Insights
     - Azure Key Vault with secrets (MongoDB URI, SMTP, Foundry)
     - Azure Container Registry (Basic SKU)
     - 2x Managed Identities (Container Apps, Functions)
     - Key Vault access policies (3x for terraform/apps/functions)
     - RBAC assignments (Storage Blob Contributor, AcrPull)
     - Container Apps Environment + Job (cron schedule)
     - App Service Plan + Function App (Y1 consumption)
   - `infrastructure/terraform/outputs.tf` - Export RG, Key Vault, ACR, App Insights
   - `infrastructure/terraform/terraform.tfvars.example` - Template for user values
   - `infrastructure/terraform/README.md` - Deployment guide, cost estimates, troubleshooting
   - Cost: ~$7-8/month MVP

3. ⏳ **MongoDB Atlas Setup** (Next)
   - Create free M0 cluster at mongodb.com/cloud/atlas
   - Database: `overland_finder`
   - Collections: `deals`, `scrape_history`, `user_favorites`
   - Indexes: `value_score`, `timestamp`, `make`, `model`, `vin`
   - IP allowlist: `0.0.0.0/0` (for Azure Container Apps)
   - Add connection string to `terraform.tfvars`

4. ⏳ **Initial Terraform Deployment**
   ```bash
   cd infrastructure/terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with MongoDB URI, SMTP creds, Foundry endpoint
   
   terraform init
   terraform plan
   terraform apply
   ```

5. ⏳ **GitHub Actions CI/CD Pipeline**
   - Create service principal for GitHub
   - Configure GitHub Secrets (Azure credentials, ACR login)
   - Create `.github/workflows/deploy.yml`
   - Auto-build Docker images on push to `main`
   - Auto-deploy to Container Apps + Functions

6. ⏳ **Initial Dockerfile**
   ```dockerfile
   FROM python:3.13-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   CMD ["python", "background_scraper.py"]
   ```

5. ✅ **Test Deployment**
   - Push hello-world container
   - Verify GitHub Actions workflow runs
   - Confirm Container Apps Job created

**Deliverables:**
- ✅ All Azure resources provisioned
- ✅ CI/CD pipeline functional
- ✅ Managed Identity configured
- ✅ Secrets in Key Vault (no hardcoded credentials)

**Dependencies:** `azure-identity`, `azure-keyvault-secrets`, `azure-storage-blob`, `opencensus-ext-azure`

---

### **Phase 1: MongoDB Integration** ⏱️ Week 1
**Goal:** Replace JSON file with cloud database

**Tasks:**
1. ✅ **Create `mongodb_client.py` module**
   ```python
   from pymongo import MongoClient
   from azure.identity import DefaultAzureCredential
   from azure.keyvault.secrets import SecretClient
   
   # Get MongoDB URI from Key Vault (no hardcoded secrets!)
   credential = DefaultAzureCredential()
   vault_client = SecretClient(vault_url="https://kv-overland-finder.vault.azure.net/", credential=credential)
   mongodb_uri = vault_client.get_secret("mongodb-uri").value
   
   client = MongoClient(mongodb_uri)
   db = client.overland_finder
   
   # Collections
   deals_collection = db.deals
   scrape_history = db.scrape_history
   favorites = db.user_favorites
   ```

2. ✅ **Define MongoDB Schema**
   ```python
   # Deal document structure
   {
       "_id": ObjectId,
       "timestamp": ISODate,
       "source": "craigslist|autotrader|facebook",
       "url": "https://...",
       "listing": {
           "title": str,
           "make": str,
           "model": str,
           "year": int,
           "price": int,
           "mileage": int,
           "location": str,
           "description": str,
           "images": [str],  # Blob Storage URLs
           "vin": str | None
       },
       "evaluation": {
           "value_score": float,  # 0-100
           "market_value_estimate": int,
           "discount_percent": float,
           "platform_score": float,
           "recommended_action": str,
           "pros": [str],
           "cons": [str],
           "red_flags": [str],
           "ai_analysis": str
       },
       "vin_data": {  # Only if VIN decoded
           "make": str,
           "model": str,
           "trim": str,
           "engine": str,
           "drivetrain": str,
           # ... full NHTSA data
       },
       "is_duplicate": bool,
       "notified": bool,
       "favorited": bool
   }
   ```

3. ✅ **Create Indexes**
   ```python
   deals_collection.create_index([("value_score", -1)])  # Sort by best deals
   deals_collection.create_index([("timestamp", -1)])    # Recent first
   deals_collection.create_index([("url", 1)], unique=True)  # Deduplication
   deals_collection.create_index([("make", 1), ("model", 1)])  # Filter by vehicle
   deals_collection.create_index([("vin", 1)])  # VIN lookup
   ```

4. ✅ **Migration Script**
   - Convert existing `overlanding_deals.json` → MongoDB
   - Verify data integrity
   - Delete old JSON file

5. ✅ **Update existing modules**
   - Refactor `value_evaluator.py` to use MongoDB
   - Update `daily_monitor.py` to query MongoDB

**Deliverables:**
- ✅ MongoDB client with Managed Identity auth
- ✅ All data migrated from JSON
- ✅ Indexed collections for fast queries
- ✅ Local testing passes

**Dependencies:** `pymongo`, `azure-identity`, `azure-keyvault-secrets`

---

### **Phase 2: Web Scraper Modules** ⏱️ Week 2
**Goal:** Autonomous deal discovery from multiple sources

**Tasks:**
1. ✅ **Create Scraper Architecture**
   ```
   scrapers/
   ├── __init__.py
   ├── base_scraper.py          # Abstract base class
   ├── craigslist_scraper.py    # Start here (easiest)
   ├── autotrader_scraper.py    # Has public API
   ├── facebook_scraper.py      # Most complex (requires login)
   └── utils.py                 # Deduplication, rate limiting
   ```

2. ✅ **Implement Base Scraper**
   ```python
   # scrapers/base_scraper.py
   from abc import ABC, abstractmethod
   from typing import List, Dict
   
   class BaseScraper(ABC):
       @abstractmethod
       def scrape(self, search_params: Dict) -> List[Dict]:
           """Returns list of raw listing dicts"""
           pass
       
       def extract_vin(self, description: str) -> str | None:
           """Regex to find VIN in description"""
           import re
           vin_pattern = r'\b[A-HJ-NPR-Z0-9]{17}\b'
           match = re.search(vin_pattern, description)
           return match.group(0) if match else None
   ```

3. ✅ **Craigslist Scraper (MVP)**
   ```python
   # scrapers/craigslist_scraper.py
   import requests
   from bs4 import BeautifulSoup
   from .base_scraper import BaseScraper
   
   class CraigslistScraper(BaseScraper):
       def scrape(self, search_params):
           # Search: colorado craigslist, cars+trucks, query="jeep wrangler"
           # Parse HTML with BeautifulSoup
           # Extract: title, price, year, mileage, location, URL
           # Return structured list
           pass
   ```

4. ✅ **Anti-Detection Measures**
   - Rotating user agents
   - Random delays (2-5 seconds between requests)
   - Respect robots.txt
   - Request throttling (max 10 requests/minute)

5. ✅ **Deduplication Logic**
   - URL fingerprinting (check MongoDB before inserting)
   - Skip if listing already exists

6. ✅ **Image Download to Blob Storage**
   ```python
   from azure.storage.blob import BlobServiceClient
   from azure.identity import DefaultAzureCredential
   
   credential = DefaultAzureCredential()
   blob_client = BlobServiceClient(
       account_url="https://stoverlandfinder.blob.core.windows.net",
       credential=credential
   )
   
   # Upload images
   container = blob_client.get_container_client("vehicle-images")
   container.upload_blob(name=f"{listing_id}/image_1.jpg", data=image_bytes)
   ```

7. ✅ **Application Insights Integration**
   ```python
   from opencensus.ext.azure.log_exporter import AzureLogHandler
   import logging
   
   logger = logging.getLogger(__name__)
   logger.addHandler(AzureLogHandler(connection_string="..."))
   
   logger.info("Scrape started", extra={"custom_dimensions": {
       "source": "craigslist",
       "search_query": "jeep wrangler",
       "listings_found": 42
   }})
   ```

**Deliverables:**
- ✅ Working Craigslist scraper (MVP)
- ✅ Images stored in Blob Storage
- ✅ Telemetry in Application Insights
- ✅ Deduplication working
- 🔄 AutoTrader scraper (Phase 2.5)
- 🔄 Facebook Marketplace scraper (Phase 2.5)

**Dependencies:** `beautifulsoup4`, `aiohttp`, `playwright` (for JS-heavy sites), `azure-storage-blob`

**Challenges:**
- Facebook Marketplace requires login → may need Playwright with session cookies
- Rate limiting → use exponential backoff

---

### **Phase 3: AI Agent Refactor** ⏱️ Week 2
**Goal:** Transform chatbot into automated deal evaluator

**Tasks:**
1. ✅ **Create `deal_evaluator_agent.py`**
   - Remove conversational interface
   - Batch processing mode (evaluate 10+ deals per run)
   - Input: Raw listing data from scraper
   - Output: Structured evaluation + AI insights

2. ✅ **AI-Powered Enhancements**
   ```python
   # AI analyzes description for hidden details
   def extract_features_from_description(description: str) -> Dict:
       """
       AI extracts:
       - Modifications/upgrades mentioned
       - Damage/condition notes
       - Maintenance history clues
       - Title status (clean, salvage, rebuilt)
       """
       client = ChatCompletionsClient(endpoint=endpoint, credential=credential)
       response = client.complete(
           messages=[{
               "role": "system",
               "content": "Extract vehicle features, upgrades, damage, and red flags from listing."
           }, {
               "role": "user",
               "content": description
           }],
           model=deployment_name
       )
       return parse_ai_response(response)
   ```

3. ✅ **Integrate VIN Decoder**
   - If VIN found in description → decode via NHTSA
   - Store full specs in `vin_data` field
   - Cross-reference with listing (verify year/make/model)

4. ✅ **Keep Agent Framework Tools**
   - `decode_vin()` - VIN lookup
   - `calculate_value_score()` - Deal scoring
   - `check_red_flags()` - Safety checks

5. ✅ **Remove Chatbot Code**
   - Delete interactive loop from `deal_finder_agent.py`
   - No "Hi! I'm your agent" messages
   - Pure function calls, no natural language

**Deliverables:**
- ✅ Batch evaluator processes 50+ deals/run
- ✅ AI extracts insights from descriptions
- ✅ VIN decoder integration working
- ✅ Evaluation data stored in MongoDB

**Dependencies:** Keep existing `azure-ai-inference`, `azure-identity`

---

### **Phase 4: Background Scheduler** ⏱️ Week 3
**Goal:** Automate scraping + evaluation loop

**Tasks:**
1. ✅ **Create `background_scraper.py`** (Container Apps entry point)
   ```python
   # NO while True loop! Single execution, then exit.
   
   import logging
   from scrapers.craigslist_scraper import CraigslistScraper
   from deal_evaluator_agent import DealEvaluator
   from mongodb_client import deals_collection, scrape_history
   
   logger = logging.getLogger(__name__)
   
   def main():
       logger.info("Scrape job started")
       
       # 1. Run scrapers in parallel
       scrapers = [
           CraigslistScraper(),
           # AutoTraderScraper(),  # Add later
       ]
       
       all_listings = []
       for scraper in scrapers:
           listings = scraper.scrape({
               "location": "Colorado",
               "max_price": 15000,
               "keywords": ["jeep wrangler", "4runner", "tacoma"]
           })
           all_listings.extend(listings)
       
       logger.info(f"Found {len(all_listings)} total listings")
       
       # 2. Filter duplicates (check MongoDB)
       new_listings = [l for l in all_listings if not deals_collection.find_one({"url": l["url"]})]
       logger.info(f"{len(new_listings)} new listings to evaluate")
       
       # 3. Evaluate with AI
       evaluator = DealEvaluator()
       evaluations = evaluator.evaluate_batch(new_listings)
       
       # 4. Store in MongoDB
       if evaluations:
           deals_collection.insert_many(evaluations)
       
       # 5. Log scrape history
       scrape_history.insert_one({
           "timestamp": datetime.now(),
           "total_found": len(all_listings),
           "new_listings": len(new_listings),
           "sources": [s.__class__.__name__ for s in scrapers]
       })
       
       logger.info("Scrape job completed successfully")
       # Container exits here - ACA will restart in 4 hours per cron
   
   if __name__ == "__main__":
       main()
   ```

2. ✅ **Deploy as Container Apps Job**
   ```bash
   az containerapp job create \
     --name overland-scraper \
     --resource-group rg-overland-finder \
     --environment overland-env \
     --trigger-type "Schedule" \
     --cron-expression "0 */4 * * *" \  # Every 4 hours
     --image acroverlandfinder.azurecr.io/overland-finder:latest \
     --cpu 0.5 --memory 1Gi \
     --registry-server acroverlandfinder.azurecr.io \
     --registry-identity <managed-identity-id>
   ```

3. ✅ **Health Monitoring**
   - Application Insights auto-captures logs
   - Create alert: If scrape job fails 2x in row → email alert
   - Dashboard: Track listings found, new deals, evaluation scores

4. ✅ **Manual Trigger for Testing**
   ```bash
   # Run job on-demand (don't wait for cron)
   az containerapp job start --name overland-scraper --resource-group rg-overland-finder
   ```

**Deliverables:**
- ✅ Container Apps Job running every 4 hours
- ✅ Logs flowing to Application Insights
- ✅ Alerts configured for failures
- ✅ Scraper history tracked in MongoDB

**Dependencies:** `schedule` NOT needed (ACA handles cron)

---

### **Phase 5: SMS Notifications** ⏱️ Week 3
**Goal:** Daily text message with top deals

**Tasks:**
1. ✅ **Create Azure Function (Timer Trigger)**
   ```bash
   # Initialize Functions project
   func init DailySMSFunction --python
   cd DailySMSFunction
   func new --name DailySMSDigest --template "Timer trigger"
   ```

2. ✅ **Implement `__init__.py`**
   ```python
   import azure.functions as func
   from azure.identity import DefaultAzureCredential
   from azure.keyvault.secrets import SecretClient
   from pymongo import MongoClient
   import smtplib
   from email.mime.text import MIMEText
   
   def main(mytimer: func.TimerRequest) -> None:
       # 1. Get MongoDB URI from Key Vault
       credential = DefaultAzureCredential()
       vault_client = SecretClient(vault_url="https://kv-overland-finder.vault.azure.net/", credential=credential)
       mongodb_uri = vault_client.get_secret("mongodb-uri").value
       
       # 2. Query top 3 deals from last 24 hours
       client = MongoClient(mongodb_uri)
       db = client.overland_finder
       deals = list(db.deals.find({
           "timestamp": {"$gte": datetime.now() - timedelta(days=1)}
       }).sort("value_score", -1).limit(3))
       
       if not deals:
           message = "No new deals found in last 24 hours 😔"
       else:
           message = "🔥 Top deals:\n"
           for i, deal in enumerate(deals, 1):
               message += f"{i}. {deal['listing']['year']} {deal['listing']['make']} {deal['listing']['model']} - ${deal['listing']['price']:,} ({deal['evaluation']['value_score']:.0f}/100)\n{deal['url']}\n"
       
       # 3. Send SMS via SMTP
       smtp_user = vault_client.get_secret("smtp-username").value
       smtp_pass = vault_client.get_secret("smtp-password").value
       
       msg = MIMEText(message)
       msg['To'] = "7208399656@vtext.com"
       msg['From'] = smtp_user
       
       with smtplib.SMTP("smtp.gmail.com", 587) as server:
           server.starttls()
           server.login(smtp_user, smtp_pass)
           server.send_message(msg)
   ```

3. ✅ **Configure Timer Schedule**
   ```json
   // function.json
   {
     "scriptFile": "__init__.py",
     "bindings": [{
       "name": "mytimer",
       "type": "timerTrigger",
       "direction": "in",
       "schedule": "0 0 8 * * *"  // Daily at 8:00 AM MST
     }]
   }
   ```

4. ✅ **Deploy Azure Function**
   ```bash
   # Create Function App
   az functionapp create \
     --name overland-sms-function \
     --resource-group rg-overland-finder \
     --consumption-plan-location eastus \
     --runtime python \
     --runtime-version 3.11 \
     --functions-version 4 \
     --storage-account stoverlandfinder
   
   # Assign Managed Identity
   az functionapp identity assign --name overland-sms-function --resource-group rg-overland-finder
   
   # Grant Key Vault access
   az keyvault set-policy --name kv-overland-finder --object-id <identity-id> --secret-permissions get list
   
   # Deploy function
   func azure functionapp publish overland-sms-function
   ```

5. ✅ **Test SMS**
   - Trigger function manually
   - Verify text message received
   - Check Application Insights logs

**Deliverables:**
- ✅ Azure Function running daily at 8 AM
- ✅ SMS sent via Verizon email gateway
- ✅ No cost (under 1M executions)
- ✅ Managed Identity (no hardcoded SMTP credentials)

**Dependencies:** `azure-functions`, `pymongo`

---

### **Phase 6: Configuration & Secrets** ⏱️ Week 3
**Goal:** Finalize environment configuration with Managed Identity

**Tasks:**
1. ✅ **Azure Key Vault Secrets**
   ```bash
   # Store all secrets (no more .env files!)
   az keyvault secret set --vault-name kv-overland-finder --name "mongodb-uri" --value "mongodb+srv://..."
   az keyvault secret set --vault-name kv-overland-finder --name "smtp-username" --value "..."
   az keyvault secret set --vault-name kv-overland-finder --name "smtp-password" --value "..."
   az keyvault secret set --vault-name kv-overland-finder --name "foundry-endpoint" --value "https://..."
   az keyvault secret set --vault-name kv-overland-finder --name "foundry-model" --value "gpt-4o"
   ```

2. ✅ **Grant Managed Identity Access**
   ```bash
   # Container Apps Job
   IDENTITY_ID=$(az containerapp job show --name overland-scraper --resource-group rg-overland-finder --query identity.principalId -o tsv)
   az keyvault set-policy --name kv-overland-finder --object-id $IDENTITY_ID --secret-permissions get list
   
   # Azure Function
   FUNC_IDENTITY=$(az functionapp identity show --name overland-sms-function --resource-group rg-overland-finder --query principalId -o tsv)
   az keyvault set-policy --name kv-overland-finder --object-id $FUNC_IDENTITY --secret-permissions get list
   ```

3. ✅ **Update All Code to Use Key Vault**
   ```python
   # Replace all os.getenv() calls with Key Vault
   from azure.identity import DefaultAzureCredential
   from azure.keyvault.secrets import SecretClient
   
   credential = DefaultAzureCredential()
   vault_client = SecretClient(vault_url="https://kv-overland-finder.vault.azure.net/", credential=credential)
   
   # No more environment variables!
   mongodb_uri = vault_client.get_secret("mongodb-uri").value
   foundry_endpoint = vault_client.get_secret("foundry-endpoint").value
   ```

4. ✅ **Remove `.env` File**
   - Delete local `.env` (no longer needed)
   - Add `.env` to `.gitignore` (prevent accidental commits)

5. ✅ **Document Configuration**
   - Create `CONFIG.md` with Key Vault secret names
   - Document how to rotate secrets

**Deliverables:**
- ✅ All secrets in Key Vault
- ✅ Managed Identity for all services
- ✅ Zero hardcoded credentials
- ✅ UHC compliance-ready (SOC2, HIPAA patterns)

---

### **Phase 7: Documentation Updates** ⏱️ Week 4
**Goal:** Update docs to reflect new architecture

**Tasks:**
1. ✅ **Update README.md**
   - Remove chatbot usage examples
   - Add architecture diagram (ASCII art)
   - Document deployment process
   - Add cost breakdown
   - Link to new docs

2. ✅ **Create `DEPLOYMENT.md`**
   - Step-by-step Azure setup
   - GitHub Actions configuration
   - Secret management guide
   - Troubleshooting section

3. ✅ **Create `SCRAPERS.md`**
   - How to add new data sources
   - Scraper development guide
   - Anti-detection best practices

4. ✅ **Create `MONITORING.md`**
   - Application Insights queries (KQL)
   - Alert configuration
   - Common issues and fixes

5. ✅ **Create `CONFIG.md`**
   - Key Vault secret reference
   - MongoDB schema documentation
   - Environment-specific settings

**Deliverables:**
- ✅ Comprehensive documentation
- ✅ New contributor can set up in <1 hour
- ✅ Self-service troubleshooting

---

### **Phase 8: Web Dashboard (Personal eBay)** ⏱️ Week 5-6
**Goal:** Interactive web UI for browsing deals with Power BI analytics

**Tasks:**

#### **8.1: Backend API**
1. ✅ **Create FastAPI Backend**
   ```python
   # api/main.py
   from fastapi import FastAPI, Depends
   from fastapi.middleware.cors import CORSMiddleware
   from azure.identity import DefaultAzureCredential
   from azure.keyvault.secrets import SecretClient
   from pymongo import MongoClient
   from typing import List, Optional
   
   app = FastAPI(title="OverlandFinder API")
   
   # CORS for frontend
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://overlandfinder.azurewebsites.net"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   
   # MongoDB connection
   credential = DefaultAzureCredential()
   vault_client = SecretClient(vault_url="https://kv-overland-finder.vault.azure.net/", credential=credential)
   mongodb_uri = vault_client.get_secret("mongodb-uri").value
   client = MongoClient(mongodb_uri)
   db = client.overland_finder
   
   @app.get("/api/deals")
   async def get_deals(
       make: Optional[str] = None,
       model: Optional[str] = None,
       min_price: Optional[int] = None,
       max_price: Optional[int] = None,
       min_score: Optional[float] = 0,
       limit: int = 50,
       skip: int = 0
   ):
       """Get filtered deals with pagination"""
       query = {"evaluation.value_score": {"$gte": min_score}}
       if make:
           query["listing.make"] = {"$regex": make, "$options": "i"}
       if model:
           query["listing.model"] = {"$regex": model, "$options": "i"}
       if min_price or max_price:
           query["listing.price"] = {}
           if min_price:
               query["listing.price"]["$gte"] = min_price
           if max_price:
               query["listing.price"]["$lte"] = max_price
       
       deals = list(db.deals.find(query).sort("value_score", -1).skip(skip).limit(limit))
       total = db.deals.count_documents(query)
       
       return {
           "deals": deals,
           "total": total,
           "limit": limit,
           "skip": skip
       }
   
   @app.get("/api/deals/{deal_id}")
   async def get_deal_details(deal_id: str):
       """Get full details for a single deal"""
       from bson import ObjectId
       deal = db.deals.find_one({"_id": ObjectId(deal_id)})
       if not deal:
           raise HTTPException(status_code=404)
       return deal
   
   @app.post("/api/deals/{deal_id}/favorite")
   async def toggle_favorite(deal_id: str):
       """Favorite/unfavorite a deal"""
       from bson import ObjectId
       deal = db.deals.find_one({"_id": ObjectId(deal_id)})
       new_status = not deal.get("favorited", False)
       db.deals.update_one(
           {"_id": ObjectId(deal_id)},
           {"$set": {"favorited": new_status}}
       )
       return {"favorited": new_status}
   
   @app.get("/api/favorites")
   async def get_favorites():
       """Get all favorited deals"""
       deals = list(db.deals.find({"favorited": True}).sort("timestamp", -1))
       return {"deals": deals, "total": len(deals)}
   
   @app.get("/api/vin/{vin}")
   async def decode_vin(vin: str):
       """Decode VIN and return specs"""
       from vin_decoder import get_vehicle_info_from_vin
       return get_vehicle_info_from_vin(vin)
   
   @app.get("/api/stats")
   async def get_statistics():
       """Get dashboard statistics"""
       return {
           "total_deals": db.deals.count_documents({}),
           "deals_last_24h": db.deals.count_documents({
               "timestamp": {"$gte": datetime.now() - timedelta(days=1)}
           }),
           "top_deal_score": list(db.deals.find().sort("evaluation.value_score", -1).limit(1))[0]["evaluation"]["value_score"],
           "avg_price": db.deals.aggregate([{"$group": {"_id": None, "avg": {"$avg": "$listing.price"}}}]).next()["avg"],
           "total_scraped": db.scrape_history.aggregate([{"$group": {"_id": None, "total": {"$sum": "$total_found"}}}]).next()["total"]
       }
   ```

2. ✅ **Deploy FastAPI to Azure App Service**
   ```bash
   # Create App Service
   az webapp create \
     --name overland-finder-api \
     --resource-group rg-overland-finder \
     --plan overland-app-plan \  # Create B1 tier plan ($13/month)
     --runtime "PYTHON:3.11"
   
   # Assign Managed Identity
   az webapp identity assign --name overland-finder-api --resource-group rg-overland-finder
   
   # Grant Key Vault access
   az keyvault set-policy --name kv-overland-finder --object-id <identity-id> --secret-permissions get list
   
   # Deploy via GitHub Actions (add to existing workflow)
   ```

#### **8.2: Frontend UI**
1. ✅ **Create Next.js/React App**
   ```bash
   npx create-next-app@latest overland-finder-ui
   cd overland-finder-ui
   npm install @tanstack/react-query axios
   ```

2. ✅ **Key UI Components**

   **Deal List Page:**
   ```tsx
   // pages/deals.tsx
   import { useState } from 'react';
   import { useQuery } from '@tanstack/react-query';
   
   export default function DealsPage() {
     const [filters, setFilters] = useState({
       make: '',
       model: '',
       minPrice: 0,
       maxPrice: 15000,
       minScore: 70
     });
     
     const { data, isLoading } = useQuery({
       queryKey: ['deals', filters],
       queryFn: () => fetch(`/api/deals?${new URLSearchParams(filters)}`).then(r => r.json())
     });
     
     return (
       <div className="container">
         {/* Filters */}
         <div className="filters">
           <input placeholder="Make" onChange={e => setFilters({...filters, make: e.target.value})} />
           <input placeholder="Model" onChange={e => setFilters({...filters, model: e.target.value})} />
           <input type="range" min="0" max="100" value={filters.minScore} onChange={e => setFilters({...filters, minScore: e.target.value})} />
           <span>Min Score: {filters.minScore}</span>
         </div>
         
         {/* Deal Cards */}
         <div className="deals-grid">
           {data?.deals.map(deal => (
             <DealCard key={deal._id} deal={deal} />
           ))}
         </div>
       </div>
     );
   }
   
   function DealCard({ deal }) {
     const [favorited, setFavorited] = useState(deal.favorited);
     
     const toggleFavorite = async () => {
       await fetch(`/api/deals/${deal._id}/favorite`, { method: 'POST' });
       setFavorited(!favorited);
     };
     
     return (
       <div className="deal-card">
         <img src={deal.listing.images[0]} alt={deal.listing.title} />
         <h3>{deal.listing.year} {deal.listing.make} {deal.listing.model}</h3>
         <p className="price">${deal.listing.price.toLocaleString()}</p>
         <p className="score">Value Score: {deal.evaluation.value_score}/100</p>
         <button onClick={toggleFavorite}>
           {favorited ? '⭐ Favorited' : '☆ Favorite'}
         </button>
         <a href={`/deals/${deal._id}`}>View Details</a>
       </div>
     );
   }
   ```

   **Deal Detail Page:**
   ```tsx
   // pages/deals/[id].tsx
   import { useRouter } from 'next/router';
   import { useQuery } from '@tanstack/react-query';
   
   export default function DealDetailPage() {
     const router = useRouter();
     const { id } = router.query;
     
     const { data: deal } = useQuery({
       queryKey: ['deal', id],
       queryFn: () => fetch(`/api/deals/${id}`).then(r => r.json())
     });
     
     if (!deal) return <div>Loading...</div>;
     
     return (
       <div className="deal-detail">
         <h1>{deal.listing.title}</h1>
         
         {/* Image Gallery */}
         <div className="image-gallery">
           {deal.listing.images.map(img => <img key={img} src={img} />)}
         </div>
         
         {/* Key Info */}
         <div className="info-grid">
           <div>Price: ${deal.listing.price.toLocaleString()}</div>
           <div>Mileage: {deal.listing.mileage.toLocaleString()} mi</div>
           <div>Location: {deal.listing.location}</div>
           <div>Value Score: {deal.evaluation.value_score}/100</div>
         </div>
         
         {/* VIN Decoder Section */}
         {deal.listing.vin && (
           <div className="vin-section">
             <h2>VIN: {deal.listing.vin}</h2>
             <VINDetails vin={deal.listing.vin} />
           </div>
         )}
         
         {/* AI Analysis */}
         <div className="ai-analysis">
           <h2>AI Evaluation</h2>
           <p>{deal.evaluation.ai_analysis}</p>
           
           <h3>Pros</h3>
           <ul>{deal.evaluation.pros.map(p => <li key={p}>{p}</li>)}</ul>
           
           <h3>Cons</h3>
           <ul>{deal.evaluation.cons.map(c => <li key={c}>{c}</li>)}</ul>
           
           {deal.evaluation.red_flags.length > 0 && (
             <>
               <h3>Red Flags 🚩</h3>
               <ul>{deal.evaluation.red_flags.map(f => <li key={f}>{f}</li>)}</ul>
             </>
           )}
         </div>
         
         {/* Original Listing */}
         <div className="description">
           <h2>Original Description</h2>
           <pre>{deal.listing.description}</pre>
         </div>
         
         <a href={deal.url} target="_blank" className="view-listing-btn">
           View Original Listing →
         </a>
       </div>
     );
   }
   
   function VINDetails({ vin }) {
     const { data } = useQuery({
       queryKey: ['vin', vin],
       queryFn: () => fetch(`/api/vin/${vin}`).then(r => r.json())
     });
     
     if (!data) return <div>Decoding VIN...</div>;
     
     return (
       <table className="vin-table">
         <tr><td>Make</td><td>{data.make}</td></tr>
         <tr><td>Model</td><td>{data.model}</td></tr>
         <tr><td>Trim</td><td>{data.trim}</td></tr>
         <tr><td>Engine</td><td>{data.engine}</td></tr>
         <tr><td>Drivetrain</td><td>{data.drivetrain}</td></tr>
         <tr><td>Transmission</td><td>{data.transmission}</td></tr>
         {/* ... all NHTSA fields */}
       </table>
     );
   }
   ```

   **Favorites Page:**
   ```tsx
   // pages/favorites.tsx
   export default function FavoritesPage() {
     const { data } = useQuery({
       queryKey: ['favorites'],
       queryFn: () => fetch('/api/favorites').then(r => r.json())
     });
     
     return (
       <div className="container">
         <h1>⭐ My Favorites ({data?.total || 0})</h1>
         <div className="deals-grid">
           {data?.deals.map(deal => <DealCard key={deal._id} deal={deal} />)}
         </div>
       </div>
     );
   }
   ```

3. ✅ **Deploy Frontend to Azure Static Web Apps**
   ```bash
   # Create Static Web App (FREE tier or $9/month Standard)
   az staticwebapp create \
     --name overland-finder-ui \
     --resource-group rg-overland-finder \
     --source https://github.com/mbroadfo/OverlandFinder \
     --location "East US 2" \
     --branch main \
     --app-location "/frontend" \
     --output-location "out" \
     --sku Free
   
   # Configure API proxy (connects to FastAPI backend)
   # staticwebapp.config.json
   {
     "routes": [
       {
         "route": "/api/*",
         "rewrite": "https://overland-finder-api.azurewebsites.net/api/*"
       }
     ]
   }
   ```

#### **8.3: Power BI Embedded Integration**
1. ✅ **Create Power BI Report**
   - Connect Power BI Desktop to MongoDB (via connector)
   - Create visualizations:
     - **Deal Volume by Make/Model** (bar chart)
     - **Average Price Over Time** (line chart)
     - **Value Score Distribution** (histogram)
     - **Deals by Location** (map - Colorado heatmap)
     - **Top 10 Deals** (table with score, price, link)
   - Publish to Power BI Service

2. ✅ **Embed in Web Dashboard**
   ```tsx
   // components/PowerBIEmbed.tsx
   import { PowerBIEmbed } from 'powerbi-client-react';
   
   export default function DealAnalytics() {
     return (
       <div className="analytics-section">
         <h2>📊 Deal Analytics</h2>
         <PowerBIEmbed
           embedConfig={{
             type: 'report',
             id: '<report-id>',
             embedUrl: 'https://app.powerbi.com/reportEmbed',
             accessToken: '<access-token>',
             tokenType: models.TokenType.Embed,
             settings: {
               panes: {
                 filters: { expanded: false, visible: true }
               },
               background: models.BackgroundType.Transparent
             }
           }}
         />
       </div>
     );
   }
   ```

3. ✅ **Configure Power BI Embedded Capacity** (if using Standard)
   - Create Power BI Embedded resource in Azure
   - Cost: $1/hour when active, pause when not in use
   - OR use Power BI Pro license ($10/user/month - better for personal use)

4. ✅ **Refresh Schedule**
   - Configure Power BI dataset to refresh every 4 hours
   - Sync with scraper schedule

**Deliverables:**
- ✅ FastAPI backend with deal filtering, favorites, VIN lookup
- ✅ Next.js frontend with responsive design
- ✅ Deal browsing with filters (make, model, price, score)
- ✅ VIN decoder integration (view full specs)
- ✅ Favorite/star functionality (personal collection)
- ✅ Power BI Embedded dashboards
- ✅ Deployed to Azure Static Web Apps + App Service
- ✅ Entra ID authentication (optional - Phase 8.4)

**Dependencies:** `fastapi`, `uvicorn`, `powerbi-client-react` (npm)

**Cost:**
- FastAPI on App Service B1: $13/month (can scale down to F1 free tier for personal use)
- Static Web App: FREE tier
- Power BI Pro: $10/month (personal license)
- **Total Dashboard Cost: ~$10-23/month** (or FREE with F1 + Power BI Desktop only)

---

### **Phase 9: Advanced Features (Future)** ⏱️ Post-MVP
**Optional enhancements after dashboard launch:**

1. **Computer Vision for Damage Detection**
   - Azure Computer Vision API to analyze listing photos
   - Detect rust, dents, interior condition
   - Flag suspicious images

2. **Price Trend Tracking**
   - MongoDB time-series collection for historical prices
   - Track same VIN over time (price drops)
   - Predict future prices with ML (Databricks)

3. **Email Alerts (Alternative to SMS)**
   - SendGrid integration
   - HTML email templates with deal cards
   - Weekly digest option

4. **Additional Scrapers**
   - Cars.com
   - Carvana (salvage auctions)
   - IAA/Copart (insurance auctions)
   - eBay Motors

5. **Social Sharing**
   - Share deals to social media
   - Generate deal comparison reports

6. **Browser Extension**
   - Chrome/Firefox extension
   - Auto-evaluate deals while browsing listings
   - Save to favorites from any site

---

## 📊 Final Cost Breakdown

### **MVP (Phases 0-7) - No Dashboard**

| Service | Cost/Month |
|---------|------------|
| Azure Container Apps Job (scraper) | $2-3 |
| Azure Function (SMS) | FREE |
| MongoDB Atlas M0 | FREE |
| Blob Storage | $0.10 |
| Key Vault | FREE |
| Application Insights | FREE |
| Container Registry | $5 |
| **Total MVP** | **~$7-8/month** |

### **With Dashboard (Phase 8)**

| Service | Cost/Month |
|---------|------------|
| All MVP services | $7-8 |
| App Service B1 (FastAPI backend) | $13 OR FREE (F1 tier) |
| Static Web App | FREE |
| Power BI Pro | $10 (personal license) |
| **Total with Dashboard** | **$17-31/month** |

**Budget Option:**
- Use App Service F1 (free tier) for backend → $0
- Use Power BI Desktop only (no embedding) → $0
- **Dashboard cost: $0-10/month**

---

## 🎯 Success Metrics

**Phase 1-5 (MVP):**
- ✅ Scraping 100+ listings per day
- ✅ 10+ new deals evaluated daily
- ✅ SMS delivered successfully every morning
- ✅ Zero manual intervention needed

**Phase 8 (Dashboard):**
- ✅ Dashboard loads in <2 seconds
- ✅ Filter deals by make/model/price/score
- ✅ VIN decoder functional for 90%+ of listings
- ✅ Favorite 10+ deals in personal collection
- ✅ Power BI shows meaningful trends

**Overall:**
- 🎉 Find 1 goldilocks deal in first 30 days
- 🎉 <$10/month total operational cost (MVP)
- 🎉 99.9% uptime (Container Apps SLA)

---

## 🚀 Getting Started

**Prerequisites:**
- Azure subscription (free tier works for start)
- MongoDB Atlas account (free)
- GitHub account
- Azure CLI installed
- VS Code with Azure extensions

**Quick Start:**
```bash
# Clone repo
git clone https://github.com/mbroadfo/OverlandFinder
cd OverlandFinder

# Run Phase 0 setup script
./scripts/setup_azure.sh

# Configure GitHub Actions secrets
./scripts/configure_github_secrets.sh

# Deploy!
git push origin main  # GitHub Actions auto-deploys
```

---

## 📚 Documentation Index

- **README.md** - Project overview (this will be updated)
- **EVOLUTION_PLAN.md** - This document (implementation roadmap)
- **DEPLOYMENT.md** - Step-by-step Azure setup (TBD)
- **SCRAPERS.md** - Scraper development guide (TBD)
- **MONITORING.md** - Application Insights queries (TBD)
- **CONFIG.md** - Configuration reference (TBD)
- **DASHBOARD.md** - Web UI user guide (TBD)

---

## 🎉 Conclusion

This plan transforms OverlandFinder from a chatbot into a **production-grade autonomous deal-finding agent** with enterprise-level architecture:

✅ **Secure:** Managed Identity, Key Vault, Entra ID  
✅ **Scalable:** Containerized, serverless compute  
✅ **Observable:** Application Insights, KQL queries  
✅ **Cost-Effective:** ~$7-10/month for MVP, $17-31 with dashboard  
✅ **Maintainable:** CI/CD, Infrastructure as Code  
✅ **Enterprise-Ready:** UHC-approved Azure services  

**Ready to build?** Let's start with Phase 0! 🚀
