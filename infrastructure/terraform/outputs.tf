output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "function_app_name" {
  value = azurerm_linux_function_app.main.name
}

output "function_app_hostname" {
  value = azurerm_linux_function_app.main.default_hostname
}

output "app_insights_connection_string" {
  value     = azurerm_application_insights.main.connection_string
  sensitive = true
}

output "managed_identity_client_id" {
  value = azurerm_user_assigned_identity.functions.client_id
}

output "managed_identity_principal_id" {
  value = azurerm_user_assigned_identity.functions.principal_id
}
