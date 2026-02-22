# OverlandFinder Infrastructure - Terraform

This directory contains Terraform configuration to provision all Azure resources for the OverlandFinder project.

## 🏗️ Resources Created

- **Resource Group** - Container for all Azure resources
- **Key Vault** - Stores secrets (MongoDB URI, SMTP credentials, Foundry API keys)
- **Storage Account** - Blob storage for vehicle images and logs
- **Container Registry** - Stores Docker images
- **Container Apps Environment** - Hosts container apps jobs
- **Container Apps Job (Scraper)** - Runs every 4 hours to scrape and evaluate deals
- **Application Insights** - Telemetry and monitoring
- **Function App** - Daily SMS notifications (Consumption plan - FREE)
- **Managed Identities** - Passwordless authentication for all services

## 📋 Prerequisites

1. **Azure CLI** - Install from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
2. **Terraform** - Install from https://www.terraform.io/downloads
3. **Azure Subscription** - Free tier works to start
4. **MongoDB Atlas Account** - Free M0 cluster

## 🚀 Getting Started

### 1. Login to Azure

```bash
az login
az account set --subscription "<your-subscription-id>"
```

### 2. Configure Variables

```bash
# Copy example file
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
code terraform.tfvars
```

Required variables:
- `mongodb_uri` - Get from MongoDB Atlas
- `smtp_username` - Your Gmail address
- `smtp_password` - Gmail app-specific password
- `foundry_endpoint` - Azure Foundry/OpenAI endpoint
- `foundry_model_deployment` - Model name (e.g., gpt-4o)

### 3. Initialize Terraform

```bash
cd infrastructure/terraform
terraform init
```

### 4. Review Plan

```bash
terraform plan
```

This shows what resources will be created. Review carefully!

### 5. Apply Configuration

```bash
terraform apply
```

Type `yes` to confirm. This will:
- Create all Azure resources (~5-10 minutes)
- Store secrets in Key Vault
- Output important values (container registry URL, resource group name, etc.)

### 6. Save Outputs

```bash
# Save outputs for GitHub Actions
terraform output -json > ../../terraform-outputs.json

# Get specific values
terraform output resource_group_name
terraform output container_registry_login_server
terraform output -raw container_registry_admin_password
```

## 🔧 Common Commands

```bash
# Show current state
terraform show

# List all resources
terraform state list

# Get specific output
terraform output key_vault_uri

# Format code
terraform fmt

# Validate configuration
terraform validate

# Plan changes
terraform plan -out=tfplan

# Apply saved plan
terraform apply tfplan

# Destroy all resources (WARNING: Deletes everything!)
terraform destroy
```

## 🔄 Updating Infrastructure

After modifying `.tf` files:

```bash
terraform plan    # Review changes
terraform apply   # Apply changes
```

Terraform tracks state and only applies incremental changes.

## 📊 Cost Estimates

Run `terraform plan` and check the Azure Pricing Calculator for accurate estimates.

**Expected monthly costs:**
- Key Vault: FREE (under 10k ops/month)
- Storage Account: ~$0.10 (minimal usage)
- Container Registry (Basic): ~$5
- Container Apps Job: ~$2-3 (scraper running every 4h)
- Function App: FREE (Consumption plan, under 1M executions)
- Application Insights: FREE (first 5GB/month)

**Total: ~$7-8/month**

## 🔐 Security Best Practices

1. **Never commit `terraform.tfvars`** - Contains secrets (already in .gitignore)
2. **Use Managed Identity** - No passwords in code (configured automatically)
3. **Enable Key Vault access logs** - Audit who accessed secrets
4. **Use Azure Policy** - Enforce security standards (optional for personal projects)
5. **Remote state** - Store tfstate in Azure Storage for team collaboration (commented out in providers.tf)

## 🐛 Troubleshooting

**Error: "The subscription is not registered to use namespace 'Microsoft.App'"**
```bash
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
```

**Error: "Key Vault name already exists"**
- Key Vault names are globally unique
- Change `project_name` or `environment` in `terraform.tfvars`
- Or wait 7 days for soft-deleted vault to purge

**Error: "Insufficient permissions"**
```bash
# Check your Azure role
az role assignment list --assignee <your-email> --output table

# You need "Owner" or "Contributor" + "User Access Administrator"
```

## 📚 Learn More

- [Terraform Azure Provider Docs](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure Key Vault Best Practices](https://learn.microsoft.com/en-us/azure/key-vault/general/best-practices)
