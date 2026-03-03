# 📱 SMS Notification Setup Guide

## Overview

SMS notifications in OverlandFinder are sent via **Azure Functions** using Verizon's email-to-SMS gateway (NO password required). The function runs daily at 8:00 AM and queries MongoDB for top deals.

## Architecture

```
Azure Function (Timer Trigger: Daily @ 8AM)
    ↓
Query MongoDB Atlas (top 3 deals, last 24h)
    ↓
Send email to: YOUR_NUMBER@vtext.com (your configured number)
    ↓
Verizon converts email → SMS (FREE)
```

**No SMTP authentication needed!** Verizon email-to-SMS gateway accepts emails from any sender.

## Setup Steps

### 1. Verify SMS Recipient in Terraform

Check `infrastructure/terraform/terraform.tfvars`:

```hcl
# SMS Recipient (Verizon email-to-SMS gateway)
sms_recipient = "YOUR_NUMBER@vtext.com"  # Replace with your 10-digit number
```

### 2. Deploy Azure Function

The Azure Function is automatically created by Terraform:

```bash
cd infrastructure/terraform
terraform apply
```

This creates:
- Function App (Consumption plan - FREE)
- Timer trigger (runs daily at 8:00 AM)
- Managed Identity for Key Vault access
- Connection to MongoDB Atlas

### 3. Deploy Function Code

After infrastructure is deployed:

```bash
# Navigate to Functions directory
cd functions/DailySMSDigest

# Deploy function code
func azure functionapp publish overland-sms-function-dev
```

## Message Format

Azure Function sends via email-to-SMS (max 140 characters):

```
🔥 Top deals:
1. 2014 Jeep Wrangler - $8,500 (85/100)
https://facebook.com/...
```

**Example (no deals):**
```
No new deals found in last 24 hours 😔
```

## Testing SMS Locally

Before deploying to Azure, test locally:

```powershell
# Navigate to functions directory
cd functions/DailySMSDigest

# Run function locally (requires Azure Functions Core Tools)
func start
```

Or test the SMS sending logic:

```python
# test_sms.py
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Test from OverlandFinder!")
msg['To'] = "YOUR_NUMBER@vtext.com"  # Replace with your number
msg['From'] = "test@overlandfinder.com"

with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.starttls()
    server.sendmail("test@overlandfinder.com", "YOUR_NUMBER@vtext.com", msg.as_string())
```

**Note:** No authentication required for Verizon email-to-SMS gateway!

## Monitoring

View function execution logs in Azure:

```bash
# Stream logs in real-time
func azure functionapp logstream overland-sms-function-dev

# Or view in Application Insights
# Azure Portal → Application Insights → Logs
```

**KQL Query for SMS history:**
```kusto
traces
| where operation_Name == "DailySMSDigest"
| where message contains "SMS sent" or message contains "No deals"
| project timestamp, message
| order by timestamp desc
```

## Troubleshooting

### "SMS not received"
- Check your number format is correct: `NUMBER@vtext.com`
- Verify Azure Function executed: Check Application Insights logs
- Check phone has cellular service
- Try other gateways:
  - AT&T: `number@txt.att.net`
  - T-Mobile: `number@tmomail.net`
  - Sprint: `number@messaging.sprintpcs.com`

### "Function not running"
```bash
# Check function status
az functionapp show --name overland-sms-function-dev --resource-group rg-overland-finder-dev

# Verify timer trigger
func azure functionapp list-functions overland-sms-function-dev
```

### "Can't access MongoDB"
- Verify Managed Identity has Key Vault access
- Check MongoDB URI in Key Vault is correct:
  ```bash
  az keyvault secret show --vault-name kv-overland-finder-dev --name "mongodb-uri"
  ```

## Email-to-SMS Gateway Reference

Different carriers have different gateways:

| Carrier | Gateway Format |
|---------|----------------|
| Verizon | `number@vtext.com` |
| AT&T | `number@txt.att.net` |
| T-Mobile | `number@tmomail.net` |
| Sprint | `number@messaging.sprintpcs.com` |
| Virgin Mobile | `number@vmobl.com` |

To change your carrier, update `terraform.tfvars` and re-run `terraform apply`.

## How It Works

1. **8:00 AM daily:** Azure Timer Trigger activates function
2. **Function authenticates** to Key Vault using Managed Identity
3. **Gets MongoDB URI** from Key Vault
4. **Queries MongoDB** for top 3 deals (last 24h, score ≥65)
5. **Formats SMS message** (<140 characters)
6. **Sends email** to configured SMS gateway (no auth required)
7. **Verizon gateway** converts email → SMS and delivers
8. **Logs execution** to Application Insights

**Cost:** $0/month (Consumption plan, <1M executions)

---

**Ready to deploy?** Follow Phase 5 in the Evolution Plan! 🚀
