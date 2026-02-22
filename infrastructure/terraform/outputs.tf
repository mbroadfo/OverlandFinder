# Terraform Outputs

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = azurerm_key_vault.main.vault_uri
}

output "storage_account_name" {
  description = "Name of the storage account"
  value       = azurerm_storage_account.main.name
}

output "container_registry_login_server" {
  description = "Login server of the container registry"
  value       = azurerm_container_registry.main.login_server
}

output "container_registry_admin_username" {
  description = "Admin username for container registry"
  value       = azurerm_container_registry.main.admin_username
  sensitive   = true
}

output "container_registry_admin_password" {
  description = "Admin password for container registry"
  value       = azurerm_container_registry.main.admin_password
  sensitive   = true
}

output "application_insights_instrumentation_key" {
  description = "Application Insights instrumentation key"
  value       = azurerm_application_insights.main.instrumentation_key
  sensitive   = true
}

output "application_insights_connection_string" {
  description = "Application Insights connection string"
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

output "container_apps_environment_id" {
  description = "ID of the Container Apps environment"
  value       = azurerm_container_app_environment.main.id
}

output "scraper_job_name" {
  description = "Name of the scraper Container Apps Job"
  value       = azurerm_container_app_job.scraper.name
}

output "function_app_name" {
  description = "Name of the Function App"
  value       = azurerm_linux_function_app.sms.name
}

output "managed_identity_client_id" {
  description = "Client ID of the Container Apps managed identity"
  value       = azurerm_user_assigned_identity.container_apps.client_id
}

output "functions_identity_client_id" {
  description = "Client ID of the Functions managed identity"
  value       = azurerm_user_assigned_identity.functions.client_id
}
