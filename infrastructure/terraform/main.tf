# OverlandFinder Infrastructure - Main Configuration

# NOTE: This infrastructure is a draft. Update after local development is complete.
# Last sync: [date] - Reflects initial architecture design

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location
  tags     = var.tags
}

# Storage Account (for Blob Storage - images, logs, backups)
resource "azurerm_storage_account" "main" {
  name                     = "st${replace(var.project_name, "-", "")}${var.environment}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  
  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }
  
  tags = var.tags
}

# Application Insights (Monitoring)
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "other"
  tags                = var.tags
}

# Key Vault (Secrets Management)
data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                        = "kv-${var.project_name}-${var.environment}"
  location                    = azurerm_resource_group.main.location
  resource_group_name         = azurerm_resource_group.main.name
  enabled_for_disk_encryption = false
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false
  sku_name                    = "standard"
  
  tags = var.tags
}

# Key Vault Access Policy for current user/service principal
resource "azurerm_key_vault_access_policy" "terraform" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id
  
  secret_permissions = [
    "Get", "List", "Set", "Delete", "Purge"
  ]
}

# Secrets Management:
# Terraform does NOT create any secrets in Key Vault.
# Add these manually after deployment:
#
# az keyvault secret set --vault-name kv-overland-finder-dev --name "mongodb-uri"     --value "mongodb+srv://..."
# az keyvault secret set --vault-name kv-overland-finder-dev --name "smtp-username"   --value "you@gmail.com"
# az keyvault secret set --vault-name kv-overland-finder-dev --name "smtp-password"   --value "xxxx-xxxx-xxxx-xxxx"

# Managed Identity for Azure Functions
resource "azurerm_user_assigned_identity" "functions" {
  name                = "id-${var.project_name}-func-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

# Grant Functions Identity access to Key Vault
resource "azurerm_key_vault_access_policy" "functions" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = azurerm_user_assigned_identity.functions.tenant_id
  object_id    = azurerm_user_assigned_identity.functions.principal_id
  
  secret_permissions = [
    "Get", "List"
  ]
}

# Azure Function App Service Plan (Consumption - FREE tier)
resource "azurerm_service_plan" "functions" {
  name                = "plan-${var.project_name}-func-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = "Y1"  # Consumption plan (pay per execution, first 1M free)
  
  tags = var.tags
}

# Azure Function App (hosts all functions: scrapers + evaluator + SMS)
resource "azurerm_linux_function_app" "main" {
  name                       = "func-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  service_plan_id            = azurerm_service_plan.functions.id
  storage_account_name       = azurerm_storage_account.main.name
  storage_account_access_key = azurerm_storage_account.main.primary_access_key
  
  site_config {
    application_insights_key               = azurerm_application_insights.main.instrumentation_key
    application_insights_connection_string = azurerm_application_insights.main.connection_string
    
    application_stack {
      python_version = "3.11"
    }
  }
  
  app_settings = {
    # Runtime configuration
    "FUNCTIONS_WORKER_RUNTIME"        = "python"
    "AzureWebJobsFeatureFlags"        = "EnableWorkerIndexing"
    "ENABLE_ORYX_BUILD"               = "true"
    "SCM_DO_BUILD_DURING_DEPLOYMENT"  = "true"

    # Managed Identity — tells DefaultAzureCredential which identity to use
    "AZURE_CLIENT_ID"                 = azurerm_user_assigned_identity.functions.client_id

    # Key Vault URL (code can use this to build references if needed)
    "KEY_VAULT_URL"                   = azurerm_key_vault.main.vault_uri

    # Static app settings
    "SMS_RECIPIENT"                   = var.sms_recipient

    # Key Vault references — values resolved at runtime by the Functions host
    # Secrets must be created manually: az keyvault secret set --vault-name ... --name ... --value ...
    "MONGODB_URI"     = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=mongodb-uri;ClientId=${azurerm_user_assigned_identity.functions.client_id})"
    "SMTP_USERNAME"   = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=smtp-username;ClientId=${azurerm_user_assigned_identity.functions.client_id})"
    "SMTP_PASSWORD"   = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=smtp-password;ClientId=${azurerm_user_assigned_identity.functions.client_id})"
  }
  
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.functions.id]
  }
  
  tags = merge(var.tags, {
    "Functions" = "scraper_job,daily_sms_digest"
  })
}
