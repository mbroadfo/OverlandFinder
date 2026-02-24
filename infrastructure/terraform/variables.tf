# Input Variables for OverlandFinder Infrastructure

variable "project_name" {
  description = "Name of the project (used in resource naming)"
  type        = string
  default     = "overland-finder"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus"
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "OverlandFinder"
    ManagedBy   = "Terraform"
    Repository  = "github.com/mbroadfo/OverlandFinder"
  }
}

# Container Apps Configuration
variable "scraper_schedule" {
  description = "Cron schedule for scraper job (every 4 hours by default)"
  type        = string
  default     = "0 */4 * * *"
}

variable "sms_schedule" {
  description = "Cron schedule for daily SMS (8 AM by default)"
  type        = string
  default     = "0 8 * * *"
}

variable "scraper_cpu" {
  description = "CPU allocation for scraper job"
  type        = number
  default     = 0.5
}

variable "scraper_memory" {
  description = "Memory allocation for scraper job (in GB)"
  type        = string
  default     = "1Gi"
}

# SMS Configuration
variable "sms_recipient" {
  description = "SMS recipient (Verizon email gateway format)"
  type        = string
  default     = "7208399656@vtext.com"
}
