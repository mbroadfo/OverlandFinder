# Deal Finder — Terraform Infrastructure

Provisions all Azure resources for the Deal Finder Function App.
Deployment is split between Terraform (infrastructure) and GitHub Actions (code + secrets).

## Resources created

| Resource | Name | Purpose |
|---|---|---|
| Resource Group | `rg-overland-finder-dev` | Container for all app resources |
| Storage Account | `stoverlandfinderdev` | Function App host storage (managed identity, no access key) |
| Service Plan | `asp-overland-finder-dev` | Consumption (Y1) — free tier |
| Function App | `func-overland-finder-dev` | Hosts scraper, evaluator, SMS timer functions |
| Key Vault | `kv-overland-finder-dev` | Runtime secrets (resolved via KV references, never in app settings) |
| Managed Identity | `id-overland-finder-func-dev` | Runtime identity for Function App → KV + Storage |
| Log Analytics | `log-overland-finder-dev` | Centralized log sink |
| Application Insights | `appi-overland-finder-dev` | Telemetry, function traces |

Terraform state is stored separately in `rg-tf-state` / `stoverlandtfstate` — outside this resource group so it survives a `terraform destroy`.

## Identity model

```
GitHub Actions (external)
└── Service Principal  sp-deal-finder-github
      ├── OIDC federated credential — no client secret, short-lived tokens only
      ├── Role: Contributor on subscription
      ├── Role: User Access Administrator (conditioned to 3 storage roles only)
      ├── Role: Storage Blob Data Contributor on state storage account
      └── Key Vault access policy: Get/List/Set/Delete

Function App (runtime, internal to Azure)
└── Managed Identity  id-overland-finder-func-dev
      ├── Role: Storage Blob Data Owner on function storage
      ├── Role: Storage Queue Data Contributor on function storage
      ├── Role: Storage Table Data Contributor on function storage
      └── Key Vault access policy: Get/List (read-only)
```

## First-time setup (run once, locally)

```bash
cd infrastructure/terraform
chmod +x bootstrap.sh
./bootstrap.sh
```

This script:
1. Creates `rg-tf-state` and the Terraform state storage account
2. Creates the `sp-deal-finder-github` App Registration and Service Principal
3. Adds the OIDC federated credential scoped to your GitHub `dev` environment
4. Assigns minimum RBAC roles with conditions
5. Prints all values needed for GitHub Environment configuration

After running the script:

1. Add the printed values to your GitHub Environment (`Settings → Environments → dev`)
2. Add `github_actions_principal_id` to `terraform.tfvars`
3. Migrate local state to remote:
   ```bash
   terraform init -migrate-state
   ```
4. Push to `main` — GitHub Actions handles all future deploys

## GitHub Environment configuration

### Variables (viewable in GitHub UI)

| Variable | Value |
|---|---|
| `AZURE_CLIENT_ID` | App Registration client ID (from bootstrap output) |
| `AZURE_TENANT_ID` | Azure AD tenant ID (from bootstrap output) |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID (from bootstrap output) |
| `TF_VAR_github_actions_principal_id` | Service principal object ID (from bootstrap output) |
| `PROJECT_NAME` | `overland-finder` |
| `ENVIRONMENT` | `dev` |
| `LOCATION` | `eastus` |
| `SMS_RECIPIENT` | `<your-number>@vtext.com` |
| `KEY_VAULT_NAME` | `kv-overland-finder-dev` |
| `FUNCTION_APP_NAME` | `func-overland-finder-dev` |

### Secrets (write-only, pushed to Key Vault by CI/CD)

| Secret | Description |
|---|---|
| `MONGODB_URI` | MongoDB Atlas connection string |
| `SMTP_USERNAME` | Gmail address for email-to-SMS |
| `SMTP_PASSWORD` | Gmail app password |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude evaluator |

## Day-to-day workflow

```
git push → GitHub Actions
              ├── terraform init        (reads state from blob via OIDC)
              ├── terraform apply       (infra changes only if .tf files changed)
              ├── az keyvault secret set (pushes GitHub Secrets → Key Vault)
              └── func deploy           (packages Python, deploys to Function App)
```

## Common commands

```bash
# Validate configuration
terraform validate

# Preview changes
terraform plan

# Apply manually (when running locally)
terraform apply

# Show current state
terraform show

# List resources in state
terraform state list

# Destroy all app resources (state storage in rg-tf-state is NOT affected)
terraform destroy
```

## Troubleshooting

**`storage account name already taken`**
Storage account names are globally unique. Edit `STATE_STORAGE_ACCOUNT` in `bootstrap.sh` and `storage_account_name` in `providers.tf` to add a short suffix (e.g. `stoverlandtfstate2`).

**`Key Vault name already exists`**
Key Vault names are globally unique and soft-deleted vaults hold the name for 7 days. Either wait 7 days or change `project_name` or `environment` in `terraform.tfvars`.

**`insufficient privileges to complete the operation`**
The service principal needs `Contributor` + conditioned `User Access Administrator`. Check assignments:
```bash
az role assignment list --assignee <SP_OBJECT_ID> --output table
```

**`AuthorizationFailed` on state storage**
The service principal needs `Storage Blob Data Contributor` on `stoverlandtfstate`. The bootstrap script assigns this — re-run if it was skipped.

**Provider namespace not registered**
```bash
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Insights
```
