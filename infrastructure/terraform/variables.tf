variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "overland-finder"
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

variable "mongodb_uri" {
  description = "MongoDB Atlas connection string"
  type        = string
  sensitive   = true
}

variable "smtp_username" {
  description = "Gmail address for email-to-SMS"
  type        = string
  sensitive   = true
}

variable "smtp_password" {
  description = "Gmail app password for email-to-SMS"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude evaluator"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default = {
    Project   = "OverlandFinder"
    ManagedBy = "Terraform"
    Repo      = "github.com/mbroadfo/OverlandFinder"
  }
}
