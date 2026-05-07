variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "deal-finder"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "sms_recipient" {
  description = "SMS recipient via Verizon email-to-SMS gateway (e.g. 3035551234@vtext.com)"
  type        = string
}

variable "github_actions_principal_id" {
  description = "Object ID of the GitHub Actions service principal — granted Key Vault write access so CI/CD can push secrets"
  type        = string
}

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default = {
    Project   = "DealFinder"
    ManagedBy = "Terraform"
    Repo      = "github.com/mbroadfo/OverlandFinder"
  }
}
