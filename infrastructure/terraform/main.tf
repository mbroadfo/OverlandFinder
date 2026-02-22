# OverlandFinder Infrastructure - Main Configuration

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

resource "azurerm_storage_container" "vehicle_images" {
  name                  = "vehicle-images"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "logs" {
  name                  = "logs"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
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

# Store secrets in Key Vault
resource "azurerm_key_vault_secret" "mongodb_uri" {
  name         = "mongodb-uri"
  value        = var.mongodb_uri
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "smtp_username" {
  name         = "smtp-username"
  value        = var.smtp_username
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "smtp_password" {
  name         = "smtp-password"
  value        = var.smtp_password
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "foundry_endpoint" {
  name         = "foundry-endpoint"
  value        = var.foundry_endpoint
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "foundry_model" {
  name         = "foundry-model"
  value        = var.foundry_model_deployment
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

# Container Registry (for Docker images)
resource "azurerm_container_registry" "main" {
  name                = "acr${replace(var.project_name, "-", "")}${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
  
  tags = var.tags
}

# Managed Identity for Container Apps
resource "azurerm_user_assigned_identity" "container_apps" {
  name                = "id-${var.project_name}-aca-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

# Grant Managed Identity access to Key Vault
resource "azurerm_key_vault_access_policy" "container_apps" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = azurerm_user_assigned_identity.container_apps.tenant_id
  object_id    = azurerm_user_assigned_identity.container_apps.principal_id
  
  secret_permissions = [
    "Get", "List"
  ]
}

# Grant Managed Identity access to Blob Storage
resource "azurerm_role_assignment" "container_apps_storage" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.container_apps.principal_id
}

# Grant Managed Identity access to Container Registry
resource "azurerm_role_assignment" "container_apps_acr" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.container_apps.principal_id
}

# Container Apps Environment
resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  
  tags = var.tags
}

# Container Apps Job - Scraper (runs every 4 hours)
resource "azurerm_container_app_job" "scraper" {
  name                         = "caj-${var.project_name}-scraper-${var.environment}"
  location                     = azurerm_resource_group.main.location
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  
  replica_timeout_in_seconds = 1800  # 30 minutes max
  replica_retry_limit        = 1
  
  schedule_trigger_config {
    cron_expression          = var.scraper_schedule
    parallelism              = 1
    replica_completion_count = 1
  }
  
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_apps.id]
  }
  
  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.container_apps.id
  }
  
  template {
    container {
      name   = "scraper"
      image  = "${azurerm_container_registry.main.login_server}/overland-finder:latest"
      cpu    = var.scraper_cpu
      memory = var.scraper_memory
      
      env {
        name  = "KEY_VAULT_URL"
        value = azurerm_key_vault.main.vault_uri
      }
      
      env {
        name  = "APPINSIGHTS_INSTRUMENTATIONKEY"
        value = azurerm_application_insights.main.instrumentation_key
      }
      
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.container_apps.client_id
      }
      
      env {
        name  = "STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.main.name
      }
    }
  }
  
  tags = var.tags
}

# Managed Identity for Functions
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

# Azure Function App (for daily SMS notifications)
resource "azurerm_service_plan" "functions" {
  name                = "plan-${var.project_name}-func-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = "Y1"  # Consumption plan (free tier)
  
  tags = var.tags
}

resource "azurerm_linux_function_app" "sms" {
  name                       = "func-${var.project_name}-sms-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  service_plan_id            = azurerm_service_plan.functions.id
  storage_account_name       = azurerm_storage_account.main.name
  storage_account_access_key = azurerm_storage_account.main.primary_access_key
  
  site_config {
    application_insights_key = azurerm_application_insights.main.instrumentation_key
    
    application_stack {
      python_version = "3.11"
    }
  }
  
  app_settings = {
    "KEY_VAULT_URL"                   = azurerm_key_vault.main.vault_uri
    "AZURE_CLIENT_ID"                 = azurerm_user_assigned_identity.functions.client_id
    "SMS_RECIPIENT"                   = var.sms_recipient
    "FUNCTIONS_WORKER_RUNTIME"        = "python"
    "AzureWebJobsFeatureFlags"        = "EnableWorkerIndexing"
  }
  
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.functions.id]
  }
  
  tags = var.tags
}
