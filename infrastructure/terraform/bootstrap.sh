#!/usr/bin/env bash
# Bootstrap script — run ONCE manually before the first pipeline run.
# Creates Terraform remote state storage and the GitHub Actions service principal.
#
# Run in Git Bash or WSL on Windows, or any bash shell on Mac/Linux.
# Prerequisites: Azure CLI installed and logged in (az login)
#
# Usage:
#   chmod +x bootstrap.sh
#   ./bootstrap.sh

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
# Change STATE_STORAGE_ACCOUNT if this name is already taken (globally unique).
# Must be lowercase, no hyphens, 3-24 characters.

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
STATE_RG="rg-tf-state"
STATE_STORAGE_ACCOUNT="stoverlandtfstate"
STATE_CONTAINER="tfstate"
SP_NAME="sp-deal-finder-github"
GITHUB_ORG="mbroadfo"
GITHUB_REPO="OverlandFinder"
GITHUB_ENVIRONMENT="dev"

echo ""
echo "=== Deal Finder — Bootstrap ==="
echo "Subscription: $SUBSCRIPTION_ID"
echo "Tenant:       $TENANT_ID"
echo ""

# ── Step 1: Terraform state storage ──────────────────────────────────────────

echo "[ 1/5 ] Creating Terraform state resource group..."
az group create \
  --name "$STATE_RG" \
  --location eastus \
  --output none

echo "[ 2/5 ] Creating Terraform state storage account ($STATE_STORAGE_ACCOUNT)..."
az storage account create \
  --name "$STATE_STORAGE_ACCOUNT" \
  --resource-group "$STATE_RG" \
  --sku Standard_LRS \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --output none

echo "        Enabling blob versioning for state recovery..."
az storage account blob-service-properties update \
  --account-name "$STATE_STORAGE_ACCOUNT" \
  --resource-group "$STATE_RG" \
  --enable-versioning true \
  --output none

echo "        Creating tfstate container..."
az storage container create \
  --name "$STATE_CONTAINER" \
  --account-name "$STATE_STORAGE_ACCOUNT" \
  --auth-mode login \
  --output none

# ── Step 2: GitHub Actions service principal ──────────────────────────────────

echo "[ 3/5 ] Creating App Registration and Service Principal ($SP_NAME)..."
APP_ID=$(az ad app create \
  --display-name "$SP_NAME" \
  --query appId -o tsv)

SP_OBJECT_ID=$(az ad sp create \
  --id "$APP_ID" \
  --query id -o tsv)

echo "        Adding OIDC federated credential for GitHub Environment '$GITHUB_ENVIRONMENT'..."
az ad app federated-credential create \
  --id "$APP_ID" \
  --parameters "{
    \"name\": \"github-actions-${GITHUB_ENVIRONMENT}\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:${GITHUB_ORG}/${GITHUB_REPO}:environment:${GITHUB_ENVIRONMENT}\",
    \"description\": \"GitHub Actions OIDC for ${GITHUB_ENVIRONMENT} environment\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }" \
  --output none

# ── Step 3: RBAC role assignments ─────────────────────────────────────────────

echo "[ 4/5 ] Assigning RBAC roles to service principal..."

# Contributor on subscription — create/manage all resources
az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Contributor" \
  --scope "/subscriptions/$SUBSCRIPTION_ID" \
  --output none

# User Access Administrator — restricted to the three storage roles Terraform assigns
# GUIDs: Storage Blob Data Owner, Storage Queue Data Contributor, Storage Table Data Contributor
az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "User Access Administrator" \
  --scope "/subscriptions/$SUBSCRIPTION_ID" \
  --condition-version "2.0" \
  --condition "((!(ActionMatches{'Microsoft.Authorization/roleAssignments/write'})) OR (@Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {ba92f5b4-2d11-453d-a403-e96b0029c9fe, 974c5e8b-45b9-4653-ba55-5f855dd0fb88, 0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3}))" \
  --output none

# Storage Blob Data Contributor on state storage — read/write Terraform state
STATE_STORAGE_ID=$(az storage account show \
  --name "$STATE_STORAGE_ACCOUNT" \
  --resource-group "$STATE_RG" \
  --query id -o tsv)

az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope "$STATE_STORAGE_ID" \
  --output none

# ── Step 4: Print GitHub configuration ───────────────────────────────────────

echo "[ 5/5 ] Bootstrap complete."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GitHub Environment VARIABLES  (Settings → Environments → dev)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AZURE_CLIENT_ID                = $APP_ID"
echo "  AZURE_TENANT_ID                = $TENANT_ID"
echo "  AZURE_SUBSCRIPTION_ID          = $SUBSCRIPTION_ID"
echo "  TF_VAR_github_actions_principal_id = $SP_OBJECT_ID"
echo "  PROJECT_NAME                   = overland-finder"
echo "  ENVIRONMENT                    = dev"
echo "  LOCATION                       = eastus"
echo "  SMS_RECIPIENT                  = (your Verizon number @vtext.com)"
echo "  KEY_VAULT_NAME                 = kv-overland-finder-dev"
echo "  FUNCTION_APP_NAME              = func-overland-finder-dev"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GitHub Environment SECRETS  (write-only)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MONGODB_URI                    (your Atlas connection string)"
echo "  SMTP_USERNAME                  (your Gmail address)"
echo "  SMTP_PASSWORD                  (your Gmail app password)"
echo "  ANTHROPIC_API_KEY              (your Anthropic API key)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  terraform.tfvars addition"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  github_actions_principal_id = \"$SP_OBJECT_ID\""
echo ""
echo "  Next steps:"
echo "  1. Add the variables and secrets above to your GitHub Environment"
echo "  2. Add github_actions_principal_id to terraform.tfvars"
echo "  3. Run: terraform init -migrate-state  (moves local state to blob)"
echo "  4. Push to main — GitHub Actions handles all future deploys"
echo ""
