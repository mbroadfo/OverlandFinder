# OverlandFinder 🏔️🚙

**Autonomous background agent for discovering undervalued overland vehicles**

Automatically scrapes marketplaces (Facebook Marketplace, eBay Motors, Craigslist, etc.) and identifies high-value deals on 4x4 trucks and SUVs using AI-powered evaluation with VIN decoding for accurate pricing analysis. Maintains a curated database of deals and sends daily SMS summaries of the hottest opportunities.

**Architecture**: Production-grade Azure deployment with Container Apps Jobs for batch processing, Azure Functions for notifications, MongoDB Atlas for data persistence, and Application Insights for observability. All managed via Terraform - Infrastructure as Code for UHC-style enterprise deployments.

**Current Status**: Phase 0 (Infrastructure Setup) - Project restructured with Terraform IaC, ready for MongoDB integration and scraper development.

## 🎯 Project Mission

Build an intelligent agent that monitors online vehicle marketplaces 24/7, evaluates deals using AI and market data, and surfaces only the best opportunities. No more manual searching - just daily text alerts when genuine values appear.

### Target Criteria
- **Budget:** ~$10k purchase + $5k upgrades = $15k total
- **Priority:** Best value ratio (price vs condition/capability)
- **Vehicles:** ALL capable platforms (Wrangler, 4Runner, Tacoma, Land Cruiser, GX, Xterra, Frontier, Bronco, Colorado)
- **Deal Types:** Higher mileage if maintained, older but reliable, cosmetic damage OK, salvage if registerable
- **Location:** Colorado (must be registerable!)

### Key Capabilities
- **VIN Decoding**: Accurate year/make/model/trim/engine identification from listings
- **AI Evaluation**: GPT-4 analyzes condition, pricing, modifications, maintenance history
- **Market Intelligence**: Compares against Kelly Blue Book, NADA, and historical sales
- **Smart Filtering**: Focuses on overland-ready platforms (4Runner, Tacoma, Land Cruiser, 4x4 Silverado/F-150)
- **Daily Digest**: SMS summaries with top 5 deals ranked by value score

## 🏗️ Architecture

### Infrastructure (Terraform-managed Azure)

```
┌─────────────────────────────────────────────────────────┐
│                  Azure Subscription                      │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  Azure Function: scraper_job (every 4h)        │    │
│  │  ┌──────────────┐  ┌──────────────────┐       │    │
│  │  │   Craigslist │→ │  Deal Evaluator  │       │    │
│  │  │   Scraper    │  │  (value scoring) │       │    │
│  │  └──────────────┘  └──────────────────┘       │    │
│  └────────────────────────────────────────────────┘    │
│                          ↓                              │
│  ┌────────────────────────────────────────────────┐    │
│  │  MongoDB Atlas M0 (FREE)                       │    │
│  │  • raw_listings (pending evaluation)           │    │
│  │  • deals (scored opportunities)                │    │
│  │  • batch_checkpoints (resume state)            │    │
│  └────────────────────────────────────────────────┘    │
│                          ↓                              │
│  ┌────────────────────────────────────────────────┐    │
│  │  Azure Function: daily_sms_digest (8 AM daily) │    │
│  │  ┌──────────────────────────────────┐          │    │
│  │  │  Top 3 deals → Gmail → Verizon   │          │    │
│  │  └──────────────────────────────────┘          │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Supporting Services (all free tier):                   │
│  • Azure Key Vault (MongoDB URI, SMTP credentials)      │
│  • Storage Account (Functions runtime state only)       │
│  • Application Insights (telemetry)                     │
│  • Managed Identity (passwordless Key Vault access)     │
└─────────────────────────────────────────────────────────┘
```

**Cost Estimate**: ~$0.02/month (Storage ~$0.02, everything else FREE tier)

## 🚀 Quick Start

### Prerequisites

- Azure subscription ([create free account](https://azure.microsoft.com/free/))
- [Terraform](https://www.terraform.io/downloads) >= 1.5
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli)
- [Python](https://www.python.org/downloads/) >= 3.11
- MongoDB Atlas account ([free tier](https://www.mongodb.com/cloud/atlas/register))

### 1. Deploy Infrastructure

```bash
# Clone the repository
git clone https://github.com/mbroadfo/OverlandFinder.git
cd OverlandFinder

# Authenticate with Azure
az login

# Configure Terraform variables
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values:
#   - sms_recipient (your Verizon number@vtext.com)

# Deploy infrastructure
terraform init
terraform plan
terraform apply

# Save outputs for next steps
terraform output -json > ../../terraform-outputs.json
```

See [infrastructure/terraform/README.md](infrastructure/terraform/README.md) for detailed deployment guide.

### 2. Install Python Dependencies

```powershell
# Return to project root
cd ..\..

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Test VIN Decoder

```python
from src.utils.vin_decoder import decode_vin

result = decode_vin("1FTEW1E50KFA12345")
print(f"{result['year']} {result['make']} {result['model']}")
# 2019 Ford F-150
```

### 4. Configure MongoDB (Coming in Phase 1)

```powershell
# Will initialize collections and indexes
python -m src.data.vehicle_database --setup
```

## 📁 Project Structure

```
OverlandFinder/
├── src/                          # Main application package
│   ├── scrapers/                 # Web scrapers (Phase 2-3)
│   │   ├── facebook_scraper.py   # (TBD)
│   │   ├── ebay_scraper.py       # (TBD)
│   │   └── craigslist_scraper.py # (TBD)
│   ├── evaluator/                # AI deal evaluation (Phase 4)
│   │   └── deal_finder_agent.py  # Agent orchestration
│   ├── data/                     # Data layer (Phase 1)
│   │   └── vehicle_database.py   # MongoDB operations
│   ├── utils/                    # Utilities
│   │   └── vin_decoder.py        # ✅ NHTSA vPIC integration
│   ├── jobs/                     # Background jobs
│   │   ├── daily_monitor.py      # Scheduled scraping
│   │   ├── deal_finder_server.py # HTTP server mode
│   │   └── sms_notifier.py       # SMS notifications
│   └── api/                      # FastAPI backend (Phase 8)
│
├── infrastructure/               # Terraform IaC
│   └── terraform/
│       ├── main.tf               # Core Azure resources
│       ├── variables.tf          # Input variables
│       ├── outputs.tf            # Export values
│       ├── providers.tf          # Azure/AzureAD config
│       ├── terraform.tfvars.example
│       ├── .gitignore
│       └── README.md             # Deployment guide
│
├── functions/                    # Azure Functions
│   └── DailySMSDigest/           # Timer-triggered SMS (Phase 5)
│
├── tests/                        # Test suite (Phase 6)
│   ├── test_vin_decoder.py       # (TBD)
│   ├── test_scrapers.py          # (TBD)
│   └── test_evaluator.py         # (TBD)
│
├── scripts/                      # Utility scripts
│   ├── backfill_vins.py          # (TBD)
│   └── export_deals.py           # (TBD)
│
├── docs/                         # Documentation
│   ├── EVOLUTION_PLAN.md         # 9-phase roadmap
│   └── SMS_SETUP.md              # SMS configuration
│
├── pyproject.toml                # Project metadata
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image (TBD)
└── README.md                     # This file
```

## 🧬 VIN Decoder

**Status**: ✅ **Complete and tested** (Phase 0)

The VIN decoder uses the NHTSA API to retrieve accurate vehicle specifications from 17-character VINs found in marketplace listings.

### Features

- ✅ Validates VIN format (17 characters, valid check digit)
- ✅ Decodes year, make, model, trim, engine, drive type
- ✅ Extracts GVWR, fuel type, body class
- ✅ Caches results to minimize API calls
- ✅ Comprehensive error handling

### Usage

```python
from src.utils.vin_decoder import decode_vin, batch_decode_vins

# Single VIN
vehicle_info = decode_vin("1FTEW1E50KFA12345")
print(vehicle_info)
{
    'vin': '1FTEW1E50KFA12345',
    'year': 2019,
    'make': 'Ford',
    'model': 'F-150',
    'trim': 'XLT SuperCrew 4WD',
    'engine': '3.5L V6 EcoBoost',
    'drive_type': '4WD',
    'fuel_type': 'Gasoline',
    'gvwr': '7050 lbs',
    'body_class': 'Pickup',
    'raw_nhtsa_data': {...}
}

# Batch processing
vins = ["1FTEW1E50KFA12345", "JTEBU5JR5K5212345"]
results = batch_decode_vins(vins)
```

**Note**: Migrated from [VehicleWellnessCenter](https://github.com/mbroadfo/VehicleWellnessCenter) project with enhancements for marketplace data parsing.

## 🛤️ Development Roadmap

See [docs/EVOLUTION_PLAN.md](docs/EVOLUTION_PLAN.md) for the complete 9-phase evolution plan.

### Current Phase: Phase 0 - Infrastructure Setup ✅

- [x] GitHub repository setup
- [x] VIN decoder implementation
- [x] Terraform infrastructure as code
- [x] Project structure reorganization
- [ ] Initial Terraform deployment
- [ ] Dockerfile creation
- [ ] GitHub Actions CI/CD pipeline

### Upcoming Phases

- **Phase 1**: MongoDB integration (collections, indexes, CRUD operations)
- **Phase 2**: Facebook Marketplace scraper
- **Phase 3**: eBay Motors & Craigslist scrapers
- **Phase 4**: AI deal evaluation (GPT-4 + market data)
- **Phase 5**: Daily SMS notifications
- **Phase 6**: Testing & quality assurance
- **Phase 7**: Deployment automation (GitHub Actions)
- **Phase 8**: Web dashboard (FastAPI + Power BI)
- **Phase 9**: Advanced features (price alerts, saved searches, ML scoring)

**Timeline**: ~6 weeks to MVP (Phase 5), 8-10 weeks to dashboard

## 📊 Vehicle Knowledge Base

Currently tracking **12 overlanding platforms:**

| Platform | Reliability | Overlanding | Upgrades | Price Range |
|----------|-------------|-------------|----------|-------------|
| Jeep Wrangler JK | 7/10 | 9/10 | 10/10 | $8k-$25k |
| Jeep Wrangler TJ | 7/10 | 8/10 | 10/10 | $5k-$15k |
| Toyota 4Runner 4th | 9/10 | 8/10 | 8/10 | $8k-$18k |
| Toyota 4Runner 5th | 9/10 | 9/10 | 8/10 | $15k-$45k |
| Toyota Tacoma | 9/10 | 8/10 | 9/10 | $8k-$35k |
| Land Cruiser 100 | 9/10 | 9/10 | 7/10 | $8k-$20k |
| Lexus GX470 | 9/10 | 8/10 | 7/10 | $8k-$20k |
| Lexus GX460 | 9/10 | 8/10 | 7/10 | $18k-$50k |
| Nissan Xterra | 7/10 | 7/10 | 8/10 | $4k-$12k |
| Nissan Frontier | 7/10 | 7/10 | 8/10 | $5k-$18k |
| Ford Bronco (Classic) | 6/10 | 8/10 | 9/10 | $5k-$25k |
| Chevy Colorado ZR2 | 7/10 | 8/10 | 7/10 | $15k-$40k |

Each platform includes:
- Typical price ranges
- Reliability & capability ratings
- Key features and ideal trims
- Common issues and red flags
- Platform-specific expert notes

## 🧠 Value Scoring Algorithm

```
Value Score (0-100) = 
  Discount % (0-40 points) +
  Platform Quality (0-30 points) +
  Price/Budget Ratio (0-20 points) +
  Mileage Factor (0-10 points) -
  Red Flag Penalties (30 points each)
```

### Recommendations
- **80-100:** 🔥 STRONG BUY - ACT FAST
- **65-79:** ✅ GOOD DEAL - INVESTIGATE
- **50-64:** ⚖️ FAIR - CONSIDER IF INSPECTED  
- **0-49:** 👎 PASS - WEAK VALUE
- **Red Flags:** 🚫 AUTO-REJECT

### Red Flags (Auto-Reject)
- ⛔ "Export Only" / "Cannot be registered in CO"
- ⛔ Rollover, undercarriage, flood, or fire damage
- ⛔ Over budget without exceptional value

## 🔧 Technology Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Cloud Platform** | Microsoft Azure | Hosting, compute, storage |
| **Infrastructure** | Terraform 1.5+ | IaC for all Azure resources |
| **Compute** | Azure Container Apps Jobs | Scheduled scraper + evaluator |
| | Azure Functions (Y1) | Daily SMS timer trigger |
| **Database** | MongoDB Atlas M0 | Deal storage (FREE tier) |
| **Storage** | Azure Blob Storage | Images, logs, backups |
| **Secrets** | Azure Key Vault | Credentials, API keys (FREE) |
| **Registry** | Azure Container Registry | Docker images (Basic SKU) |
| **Monitoring** | Application Insights | Telemetry, alerts (FREE 5GB) |
| **Auth** | Managed Identity (Entra ID) | Passwordless Azure services |
| **AI** | Azure AI Foundry (GPT-4) | Deal evaluation |
| **Language** | Python 3.11+ | Application code |
| **CI/CD** | GitHub Actions | Automated deployment |
| **Dashboard** | FastAPI + Power BI | Web UI (Phase 8) |

## 📈 Cost Breakdown

**MVP (Phases 1-5)**: ~$7-8/month
- Container Apps Jobs (4h schedule): ~$2-3
- Container Registry (Basic): ~$5
- Storage Account: ~$0.10
- MongoDB Atlas M0: FREE
- Azure Functions (Consumption): FREE
- Key Vault: FREE
- Application Insights (< 5GB): FREE

**With Dashboard (Phase 8)**: ~$17-31/month
- Add Container App (API): ~$10-15
- Add Power BI Embedded (if used): ~$0-$8
- All above: same costs

## 🔐 Security Best Practices

- **No hardcoded secrets**: All credentials in Azure Key Vault
- **Managed Identity**: Passwordless authentication to Azure services
- **Least privilege RBAC**: Service principals with minimal permissions
- **Network isolation**: Container Apps in virtual network (optional for Phase 9)
- **Terraform state**: Remote backend with encryption (recommended for teams)
- **Secrets rotation**: Automated via Key Vault alerts (Phase 9)

## 📈 Monitoring & Alerts

**Application Insights** tracks:
- Scraper success/failure rates
- VIN decoding performance
- AI evaluation latency
- Deal count per run
- SMS delivery status

**Alerts** (configured in Terraform):
- Job failures (>2 consecutive failures)
- High latency (>30s average)
- Storage quota (>80%)

Access dashboards: Azure Portal → Application Insights → `ai-overland-finder-dev`

## 🤝 Contributing

This is a personal project, but suggestions welcome! Open an issue or PR for:
- New marketplace scrapers
- Evaluation criteria improvements
- Dashboard features
- Cost optimizations

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- **NHTSA vPIC API** for VIN decoding
- **Azure Developer CLI** team for excellent IaC tooling
- **UHC EA Team** for Terraform and Azure best practices inspiration

---

**Questions?** Open an issue or contact [@mbroadfo](https://github.com/mbroadfo)

**Status**: 🚧 Active development - Phase 0 (Infrastructure Setup)
