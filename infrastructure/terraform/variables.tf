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

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default = {
    Project   = "OverlandFinder"
    ManagedBy = "Terraform"
    Repo      = "github.com/mbroadfo/OverlandFinder"
  }
}
