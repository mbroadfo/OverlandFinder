data "azurerm_client_config" "current" {}

# ── Resource Group ────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location
  tags     = var.tags
}

# ── Storage Account ───────────────────────────────────────────────────────────
# Used by the Function App host (no access key — managed identity only)

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

# Grant the Functions managed identity the roles required for keyless storage access
resource "azurerm_role_assignment" "func_storage_blob" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_user_assigned_identity.functions.principal_id
}

resource "azurerm_role_assignment" "func_storage_queue" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_user_assigned_identity.functions.principal_id
}

resource "azurerm_role_assignment" "func_storage_table" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.functions.principal_id
}

# ── Monitoring ────────────────────────────────────────────────────────────────

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

# ── Key Vault ─────────────────────────────────────────────────────────────────

resource "azurerm_key_vault" "main" {
  name                       = "kv-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false
  tags                       = var.tags
}

# Terraform deployer — full management (whoever runs terraform apply locally or in CI)
resource "azurerm_key_vault_access_policy" "terraform" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
}

# GitHub Actions service principal — write secrets during deployment
resource "azurerm_key_vault_access_policy" "github_actions" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = var.github_actions_principal_id

  secret_permissions = ["Get", "List", "Set", "Delete"]
}

# Functions managed identity — read secrets at runtime
resource "azurerm_key_vault_access_policy" "functions" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = azurerm_user_assigned_identity.functions.tenant_id
  object_id    = azurerm_user_assigned_identity.functions.principal_id

  secret_permissions = ["Get", "List"]
}

# ── Managed Identity ──────────────────────────────────────────────────────────

resource "azurerm_user_assigned_identity" "functions" {
  name                = "id-${var.project_name}-func-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

# ── Function App ──────────────────────────────────────────────────────────────

resource "azurerm_service_plan" "main" {
  name                = "asp-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = "Y1"
  tags                = var.tags
}

resource "azurerm_linux_function_app" "main" {
  name                = "func-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  service_plan_id     = azurerm_service_plan.main.id

  storage_account_name          = azurerm_storage_account.main.name
  storage_uses_managed_identity = true

  https_only                      = true
  key_vault_reference_identity_id = azurerm_user_assigned_identity.functions.id

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.functions.id]
  }

  site_config {
    application_insights_key               = azurerm_application_insights.main.instrumentation_key
    application_insights_connection_string = azurerm_application_insights.main.connection_string

    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    # Functions runtime
    "FUNCTIONS_WORKER_RUNTIME"       = "python"
    "AzureWebJobsFeatureFlags"       = "EnableWorkerIndexing"
    "ENABLE_ORYX_BUILD"              = "true"
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"

    # Tells DefaultAzureCredential which user-assigned identity to use
    "AZURE_CLIENT_ID" = azurerm_user_assigned_identity.functions.client_id

    # Key Vault URL available to application code
    "KEY_VAULT_URL" = azurerm_key_vault.main.vault_uri

    # Non-sensitive config (managed as GitHub Environment Variables → TF_VAR_*)
    "SMS_RECIPIENT" = var.sms_recipient

    # Secrets resolved at runtime from Key Vault
    # Values are pushed by GitHub Actions: az keyvault secret set --vault-name ... --name ... --value ...
    "MONGODB_URI"       = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=mongodb-uri;ClientId=${azurerm_user_assigned_identity.functions.client_id})"
    "SMTP_USERNAME"     = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=smtp-username;ClientId=${azurerm_user_assigned_identity.functions.client_id})"
    "SMTP_PASSWORD"     = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=smtp-password;ClientId=${azurerm_user_assigned_identity.functions.client_id})"
    "ANTHROPIC_API_KEY" = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=anthropic-api-key;ClientId=${azurerm_user_assigned_identity.functions.client_id})"
  }

  tags = var.tags

  depends_on = [
    azurerm_role_assignment.func_storage_blob,
    azurerm_role_assignment.func_storage_queue,
    azurerm_role_assignment.func_storage_table,
  ]
}
