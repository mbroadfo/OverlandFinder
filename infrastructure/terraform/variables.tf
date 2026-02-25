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


  type        = string
  default     = "7208399656@vtext.com"
}
