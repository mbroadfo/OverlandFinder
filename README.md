# OverlandFinder

Automated deal-hunting pipeline that monitors Craigslist and eBay Motors for overlanding vehicles, scores them with AI, and texts you the best finds every morning.

## What It Does

Twice a day, GitHub Actions scrapes Craigslist across 7 cities (CO, NM, UT) and eBay Motors nationwide for your target vehicles. Each listing is filtered for relevance and mileage, then scored 0–100 by Claude Haiku using a formula anchored to estimated market value. Every morning at 8 AM MDT, the top 3 unnotified deals land on your phone as SMS messages.

```
OverlandFinder 1/3 [eBay] GREAT
'05 4Runner $4.5k (82) Denver
https://ebay.com/itm/...
```

## Architecture

```
GitHub Actions (cron)
  ├── scraper.yml  — 6 AM & 6 PM UTC
  │     ├── Craigslist scraper  (7 cities, HTML)
  │     ├── eBay scraper        (nationwide, Browse API)
  │     └── Deal evaluator      (Claude Haiku, loops until queue empty)
  └── sms-digest.yml — 8 AM MDT daily
        └── Top 3 deals → Gmail SMTP → Verizon SMS gateway

MongoDB Atlas (M0 free)
  ├── raw_listings     — scraped, pending → evaluated
  ├── deals            — scored results
  └── price_observations — market price history

Azure Key Vault — single source of truth for all secrets
```

No always-on servers. Everything runs on GitHub Actions cron triggers.

## Scoring

Claude Haiku evaluates each listing against estimated market value:

| Price vs Market | Base Score |
|-----------------|-----------|
| < 50% of market | 90 |
| 50–65% | 80 |
| 65–80% | 68 |
| 80–95% | 54 |
| 95–110% | 44 |
| > 110% | 30 |

Adjustments: clean title/service history +5, rebuilt/salvage title −10, flood/fire/frame damage −25.

| Score | Action |
|-------|--------|
| 80–100 | STRONG BUY |
| 65–79 | GOOD DEAL |
| 50–64 | FAIR |
| 30–49 | PASS |
| < 30 | RED FLAG — not saved |

## Target Vehicles (`wish_list.json`)

| Vehicle | Price Range | Max Mileage |
|---------|------------|-------------|
| Toyota 4Runner | $4k–$48k | 180k |
| Toyota Tacoma 4x4 | $3k–$40k | 175k |
| Toyota FJ Cruiser | $8k–$45k | 175k |
| Toyota Land Cruiser | $4k–$35k | 200k |
| Lexus GX470 | $4k–$28k | 175k |
| Lexus GX460 | $10k–$55k | 150k |
| Jeep Wrangler | $2k–$35k | 150k |
| Jeep Cherokee XJ | $1k–$16k | 200k |
| Nissan Xterra Pro-4X | $2k–$18k | 150k |
| Ford Bronco Classic | $3k–$30k | 150k |
| Chevy Colorado ZR2 | $10k–$45k | 125k |

## Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Orchestration | GitHub Actions (cron) | Free |
| Craigslist | HTML scraping (requests + BeautifulSoup) | Free |
| eBay | Browse API (OAuth client credentials) | Free |
| AI evaluation | Claude Haiku (Anthropic API) | ~$1–2/month |
| Database | MongoDB Atlas M0 | Free |
| Secret storage | Azure Key Vault | Free |
| Notifications | Gmail SMTP → Verizon email-to-SMS | Free |

**Total monthly cost: ~$1–2**

## Setup

### Prerequisites
- GitHub account
- MongoDB Atlas account (free M0 cluster)
- Anthropic API account (pay-as-you-go, ~$5 lasts months)
- Azure subscription (free tier for Key Vault)
- Gmail account with App Password enabled
- Verizon phone (or any carrier with email-to-SMS gateway)
- eBay Developer account (production keyset)

### 1. Clone and install

```bash
git clone https://github.com/mbroadfo/OverlandFinder.git
cd OverlandFinder
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Deploy Azure Key Vault

```bash
cd infrastructure/terraform
terraform init
terraform apply
```

Then push secrets to Key Vault:
```bash
az keyvault secret set --vault-name kv-overland-finder-dev --name mongodb-uri --value "..."
az keyvault secret set --vault-name kv-overland-finder-dev --name anthropic-api-key --value "..."
az keyvault secret set --vault-name kv-overland-finder-dev --name smtp-username --value "..."
az keyvault secret set --vault-name kv-overland-finder-dev --name smtp-password --value "..."
az keyvault secret set --vault-name kv-overland-finder-dev --name ebay-app-id --value "..."
az keyvault secret set --vault-name kv-overland-finder-dev --name ebay-cert-id --value "..."
```

### 3. Configure GitHub Secrets

Add these secrets to your repo (Settings → Secrets → Actions):

| Secret | Description |
|--------|-------------|
| `MONGODB_URI` | MongoDB Atlas connection string |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `EBAY_APP_ID` | eBay production App ID |
| `EBAY_CERT_ID` | eBay production Cert ID |
| `SMTP_USERNAME` | Gmail address |
| `SMTP_PASSWORD` | Gmail App Password |
| `SMS_RECIPIENT` | `number@vtext.com` |

### 4. Customize your wish list

Edit `wish_list.json` to set target vehicles, price ranges, mileage limits, and evaluation notes.

### 5. Run locally

```bash
# Scrape Craigslist
python src/scrapers/craigslist_scraper.py

# Scrape eBay
python src/scrapers/ebay_scraper.py

# Evaluate pending listings
python src/evaluator/deal_evaluator.py

# Preview SMS digest (dry run)
python src/jobs/sms_digest.py --dry-run
```

## Project Structure

```
OverlandFinder/
├── src/
│   ├── scrapers/
│   │   ├── base_scraper.py          # Shared MongoDB upsert logic
│   │   ├── craigslist_scraper.py    # HTML scraper, 7 cities
│   │   └── ebay_scraper.py          # Browse API, nationwide
│   ├── evaluator/
│   │   ├── claude_evaluator.py      # Claude Haiku tool-use scoring
│   │   └── deal_evaluator.py        # Batch processor, enrichment, filters
│   └── jobs/
│       └── sms_digest.py            # Daily SMS via SMTP gateway
├── .github/workflows/
│   ├── deploy.yml                   # Terraform + Key Vault secrets
│   ├── scraper.yml                  # Twice-daily scrape + evaluate
│   └── sms-digest.yml              # Daily 8 AM SMS
├── infrastructure/terraform/        # Azure Key Vault + state backend
├── tests/
│   └── test_smoke.py               # Import + unit tests (no external deps)
├── wish_list.json                   # Target vehicles configuration
└── ARCHITECTURE.md                  # Mermaid pipeline diagram
```

## CI/CD

- **`deploy.yml`** — runs on push to main, provisions Azure resources and syncs secrets
- **`scraper.yml`** — cron `0 6,18 * * *`, scrapes both sources then evaluates until queue empty
- **`sms-digest.yml`** — cron `0 14 * * *` (8 AM MDT), sends top 3 unnotified deals
