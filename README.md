# 🚙 Overland Finder

AI-powered agent platform that finds and evaluates incredible VALUE on overlanding-capable vehicles. Built with Microsoft Agent Framework.

## 🎯 Mission

Find you a goldilocks deal on a sweet overlanding rig for Colorado, Utah, Wyoming, Montana, and Idaho adventures - with maximum bang for your buck!

### Your Criteria:
- **Budget:** ~$10k purchase + $5k upgrades = $15k total
- **Priority:** Best value ratio (price vs condition/capability)
- **Vehicles:** Open to ALL capable platforms (Wrangler, 4Runner, Tacoma, Land Cruiser, GX, Xterra, Frontier, Bronco, Colorado)
- **Deal Types:** Higher mileage if maintained, older but reliable, cosmetic damage OK, salvage if registerable
- **Location:** Colorado (must be registerable!)

## 🏗️ Architecture

This is an intelligent multi-agent system that:

1. **Vehicle Knowledge Base** - Deep knowledge of 12+ overlanding platforms (reliability, capability, upgrade potential, common issues)
2. **Value Evaluator** - Calculates market value, discount percentages, and value scores
3. **AI Agent** - Uses GPT-4 to analyze listings like your ChatGPT advisor, but actively hunting deals 24/7
4. **Tools** - Web scraping, VIN lookup, deal evaluation, data storage

## 📋 Features

### Current (V1):
- ✅ Comprehensive vehicle knowledge database
- ✅ Value evaluation engine with scoring
- ✅ AI agent with natural language interface
- ✅ Deal evaluation and ranking
- ✅ Colorado title compliance checking
- ✅ Upgrade cost estimation
- ✅ HTTP server mode for production
- ✅ VS Code debugging integration

### Planned (V2):
- 🔄 Automated web scraping (Facebook Marketplace, Craigslist, AutoTrader, auction sites)
- 🔄 Scheduled monitoring (check every 4 hours)
- 🔄 Email/SMS notifications for hot deals
- 🔄 VIN decode integration
- 🔄 Market price API integration
- 🔄 Web dashboard for viewing deals

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- Microsoft Foundry project with deployed model
- VS Code (recommended)

### 2. Install Dependencies

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install packages
pip install -r requirements.txt
```

### 3. Configure

Update `.env` file with your Foundry details:

```env
# Get these from Microsoft Foundry:
FOUNDRY_PROJECT_ENDPOINT=https://your-project.openai.azure.com/
FOUNDRY_MODEL_DEPLOYMENT_NAME=gpt-4o

# Adjust search criteria as needed:
MAX_PURCHASE_PRICE=10000
TARGET_VEHICLES=Jeep Wrangler,Toyota 4Runner,Toyota Tacoma,...
```

### 4. Run the Agent

**Option A: Interactive CLI Mode**
```powershell
python deal_finder_agent.py
```

**Option B: HTTP Server Mode**
```powershell
python deal_finder_server.py --server
```

**Option C: VS Code Debug Mode (Recommended)**
1. Press `F5` or click "Run and Debug"
2. Select "Debug Deal Finder HTTP Server"
3. AI Toolkit Agent Inspector will open automatically

## 💬 Usage Examples

```
You: What vehicles are you looking for?
Agent: [Lists all target vehicles with search parameters]

You: Tell me about the Jeep Wrangler JK platform
Agent: [Detailed breakdown: reliability 7/10, overlanding 9/10, common issues, red flags, expert notes]

You: Evaluate this deal: 2014 Jeep Wrangler Unlimited, 106k miles, $12,500, hail damage, clean title
Agent: [Full evaluation with value score, market comparison, pros/cons, recommendation]

You: Show me saved deals
Agent: [List of top deals sorted by value score]
```

## 🧠 How It Works

### Value Scoring Algorithm

```
Value Score (0-100) = 
  Discount % (0-40 points) +
  Platform Quality (0-30 points) +
  Price/Budget Ratio (0-20 points) +
  Mileage Factor (0-10 points) -
  Red Flag Penalties (30 points each)
```

### Recommendationss:
- **80-100:** 🔥 STRONG BUY - ACT FAST
- **65-79:** ✅ GOOD DEAL - INVESTIGATE
- **50-64:** ⚖️ FAIR - CONSIDER IF INSPECTED  
- **0-49:** 👎 PASS - WEAK VALUE
- **Red Flags:** 🚫 AUTO-REJECT

### Red Flags (Auto-Reject):
- ⛔ "Export Only" / "Cannot be registered in CO"
- ⛔ Rollover, undercarriage, flood, or fire damage
- ⛔ Over budget without exceptional value

## 📊 Vehicle Database

Currently tracking **12 overlanding platforms:**

| Platform | Reliability | Overlanding | Upgrades | Price Range |
|----------|-------------|-------------|----------|-------------|
| Jeep Wrangler JK | 7/10 | 9/10 | 10/10 | $8k-$25k |
| Jeep Wrangler TJ | 7/10 | 8/10 | 10/10 | $5k-$15k |
| Toyota 4Runner 4th  | 9/10 | 8/10 | 8/10 | $8k-$18k |
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

## 🔧 Upgrade Cost Estimates

Example upgrades with cost estimates:

```
All-Terrain Tires: $1,200
Basic Lift (2-3"): $800
Rock Sliders: $600
Skid Plates: $400
Roof Rack: $800
Recovery Gear: $300
LED Lighting: $400
Dual Battery: $600
Rooftop Tent: $1,500
```

## 📁 Project Structure

```
OverlandFinder/
├── deal_finder_agent.py       # Main CLI agent
├── deal_finder_server.py      # HTTP server mode
├── daily_monitor.py           # Daily check & SMS notifications
├── sms_notifier.py            # SMS via Verizon email gateway
├── vehicle_database.py        # Knowledge base of 12 platforms
├── value_evaluator.py         # Scoring and evaluation logic
├── requirements.txt           # Python dependencies
├── .env                       # Configuration
├── .vscode/
│   ├── launch.json           # Debug configurations
│   └── tasks.json            # Build/run tasks
├── overlanding_deals.json    # Saved deals database
└── README.md                 # This file
```

## 🎯 Next Steps (V2 Development)

### Web Scraping Integration
Add automated scraping for:
- Facebook Marketplace
- Craigslist
- AutoTrader.com
- Cars.com
- Auction sites (Copart via brokers)

### Monitoring System
- Schedule checks every 4 hours
- Track seen listings to avoid duplicates
- Send notifications for hot deals (>80 value score)

### Enhanced Evaluation
- Integrate actual market price APIs
- Add VIN decode for accurate specs
- Photo analysis for damage assessment

### Deployment
- Run as containerized service
- Deploy to Azure or local server
- Web dashboard for viewing/managing deals

## 🤝 Contributing

Want to add vehicle platforms or improve the scoring? Edit:
- `vehicle_database.py` - Add new platforms
- `value_evaluator.py` - Adjust scoring weights

## 📜 License

MIT License - Build cool stuff!

## 💡 Tips for Success

1. **Be Patient:** Great deals take time to surface
2. **Act Fast:** When value score > 80, move quickly  
3. **Inspect In Person:** Never buy sight unseen
4. **Check Title:** Verify Colorado registration eligibility
5. **Budget for Repairs:** Even "good" deals may need work
6. **Join Communities:** Overlanding forums can help evaluate

Happy hunting! 🏔️🚙

---

---

## 📱 SMS Notifications (New!)

Get **one daily text message** with your top deals via Verizon's email-to-SMS gateway.

### Setup:

1. **Get Gmail App Password** (if using Gmail):
   - Visit: https://support.google.com/accounts/answer/185833
   - Generate an App Password for "Mail"

2. **Update `.env`:**
```env
ENABLE_SMS_NOTIFICATIONS=true
SMS_RECIPIENT=7208399656@vtext.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

3. **Test it:**
```powershell
python sms_notifier.py --test
```

4. **Run daily checks:**
```powershell
python daily_monitor.py
```

### SMS Format:
```
Daily update:
3 deals! Top: 2014 Wrangler $8,500
https://facebook.com/...
```

- **Sent:** Once per day maximum
- **Length:** Under 140 characters
- **Retry:** 3 attempts if sending fails

## 📝 Changelog

### v1.0.0 (2026-02-21)

**Initial Release - Fully Functional**

**Bug Fixes:**
- Fixed syntax error in docstrings (removed duplicate `"""` markers in `deal_finder_agent.py` and `deal_finder_server.py`)
- Fixed type hint errors: Changed `str` with `None` defaults to `Optional[str]` in `evaluate_deal()` parameters
- Fixed datetime subtraction error in `daily_monitor.py` by adding None check for `last_notification_time`
- Added type ignore comments for Azure AI SDK preview API false positives in `deal_finder_server.py`
- Suppressed optional Azure telemetry environment variable warnings by adding empty values to `.env`
- Added missing default excludes (`**/.*`, `**/node_modules`) to `pyrightconfig.json` and `pyproject.toml`

**Configuration:**
- Created comprehensive Pylance/Pyright configuration (`pyrightconfig.json`, `pyproject.toml`) with type checking mode: basic
- Created `.markdownlint.json` to suppress cosmetic markdown linting rules
- Configured `.vscode/settings.json` for optimal Python analysis experience

**Quality:**
- ✅ All Python modules import cleanly without errors or warnings
- ✅ 0 syntax errors, 0 type errors, 0 linting errors
- ✅ Full type hint compatibility with Python 3.13
- ✅ All dependencies installed and verified

---

*Built with Microsoft Agent Framework | Powered by AI | Tuned for Colorado overlanding*
