# 🚀 Deployment Guide

Step-by-step instructions to go from local code to live Azure Functions.

---

## Prerequisites (one-time)

- [Terraform](https://www.terraform.io/downloads) ≥ 1.5 installed
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli) installed and `az login` done
- [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) (optional — for local `func start` testing)
- Active Azure subscription
- MongoDB Atlas cluster running (free M0) with connection string

---

## Step 1 — Provision Azure infrastructure with Terraform

```powershell
cd infrastructure/terraform

# First time only
terraform init

# Review what will be created
terraform plan

# Deploy (~2-3 minutes)
terraform apply
```

**Resources created:**
- Resource Group: `rg-overland-finder-dev`
- Storage Account (Functions runtime state)
- Log Analytics + Application Insights
- Key Vault: `kv-overland-finder-dev`
- User-assigned Managed Identity: `id-overland-finder-func-dev`
- App Service Plan (Y1 Consumption)
- Function App: `func-overland-finder-dev`

---

## Step 2 — Add secrets to Key Vault

Terraform intentionally does NOT write secrets (keeps them out of state files and git).  
Run these once after `terraform apply`:

```bash
VAULT=kv-overland-finder-dev

# MongoDB Atlas connection string
az keyvault secret set --vault-name $VAULT \
  --name mongodb-uri \
  --value "mongodb+srv://mbroadfo_db_user:<PASSWORD>@overland-finder-cluster.tfehxpn.mongodb.net/?appName=overland-finder-cluster"

# Gmail App Password for SMTP → Verizon SMS gateway
# Get from: https://myaccount.google.com/apppasswords
az keyvault secret set --vault-name $VAULT \
  --name smtp-username \
  --value "your-gmail@gmail.com"

az keyvault secret set --vault-name $VAULT \
  --name smtp-password \
  --value "xxxx-xxxx-xxxx-xxxx"
```

The Function App resolves these at startup via Key Vault references in `app_settings`  
(Terraform already wired `MONGODB_URI`, `SMTP_USERNAME`, `SMTP_PASSWORD` as KV references).

---

## Step 3 — Set up GitHub Secrets for CI/CD

### 3a. Create a Service Principal with Federated Identity (OIDC)

```bash
# Create app registration
APP_ID=$(az ad app create --display-name "OverlandFinder-GH-Deploy" --query appId -o tsv)
echo "App ID: $APP_ID"

# Create service principal
SP_OBJ_ID=$(az ad sp create --id $APP_ID --query id -o tsv)

# Grant Contributor on the resource group
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
az role assignment create \
  --role "Contributor" \
  --assignee-object-id $SP_OBJ_ID \
  --assignee-principal-type ServicePrincipal \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-overland-finder-dev

# Add federated credential for GitHub Actions (main branch)
az ad app federated-credential create --id $APP_ID --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:mbroadfo/OverlandFinder:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'

# Print values to add as GitHub Secrets
TENANT_ID=$(az account show --query tenantId -o tsv)
echo ""
echo "=== Add these to GitHub Settings → Secrets → Actions ==="
echo "AZURE_CLIENT_ID:       $APP_ID"
echo "AZURE_TENANT_ID:       $TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION_ID"
```

### 3b. Add Secrets in GitHub

Go to **github.com/mbroadfo/OverlandFinder → Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Value |
|---|---|
| `AZURE_CLIENT_ID` | App ID from above |
| `AZURE_TENANT_ID` | Tenant ID from above |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID from above |

---

## Step 4 — Deploy via GitHub Actions

After pushing `function_app.py`, `host.json`, and `requirements.txt` to `main`:

```bash
git add function_app.py host.json .github/
git commit -m "feat: add Azure Functions + CI/CD pipeline"
git push origin main
```

The workflow at [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) will:
1. Run `ruff` lint (warn only)
2. Run `pytest tests/` (warn only)
3. Login to Azure via OIDC
4. Zip-deploy the repo to `func-overland-finder-dev` (Oryx builds `requirements.txt` in Azure)
5. Print function app status

---

## Step 5 — Verify functions are registered

```bash
az functionapp function list \
  --name func-overland-finder-dev \
  --resource-group rg-overland-finder-dev \
  --output table
```

Expected output:
```
Name               ResourceGroup          ScriptFile
-----------------  ---------------------  ----------------
scraper_job        rg-overland-finder-dev function_app.py
daily_sms_digest   rg-overland-finder-dev function_app.py
```

---

## Step 6 — Test functions manually

```bash
# Trigger scraper job on demand (don't wait for cron)
az rest --method post \
  --url "https://management.azure.com/subscriptions/<SUB>/resourceGroups/rg-overland-finder-dev/providers/Microsoft.Web/sites/func-overland-finder-dev/functions/scraper_job/invoke?api-version=2022-03-01"

# Or use the Azure Portal → Function App → Functions → scraper_job → Test/Run
```

---

## Function Schedules

| Function | Schedule | Effect |
|---|---|---|
| `scraper_job` | `0 30 */4 * * *` | Every 4 hours at :30 — scrape Craigslist + evaluate raw listings |
| `daily_sms_digest` | `0 0 14 * * *` | Daily at 14:00 UTC = 8:00 AM MDT — send SMS with top 3 deals |

---

## Key Vault secrets reference

| Secret name | Used by | Set via |
|---|---|---|
| `mongodb-uri` | All functions | `az keyvault secret set` |
| `smtp-username` | `daily_sms_digest` | `az keyvault secret set` |
| `smtp-password` | `daily_sms_digest` | `az keyvault secret set` |

---

## Local Function testing (optional)

To test Azure Functions locally with `func start`:

```powershell
# Create local.settings.json (gitignored — do NOT commit)
@"
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "MONGODB_URI": "mongodb+srv://...",
    "SMTP_USERNAME": "your@gmail.com",
    "SMTP_PASSWORD": "xxxx-xxxx-xxxx-xxxx",
    "SMS_RECIPIENT": "7208399656@vtext.com"
  }
}
"@ | Out-File local.settings.json -Encoding utf8

# Start functions runtime
func start
```

---

## Cost estimate (production)

| Resource | Cost |
|---|---|
| Function App (Consumption Y1) | FREE (first 1M executions) |
| Storage Account | ~$0.10/month |
| Application Insights | FREE (first 5 GB) |
| Log Analytics | FREE (first 5 GB) |
| Key Vault | FREE (first 10K operations) |
| **Total** | **~$0.10/month** |
