# 基本變數
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "adept-turbine-339912"
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "asia-east1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "demo"

  validation {
    condition = contains([
      "dev",
      "staging",
      "prod",
      "demo"
    ], var.environment)
    error_message = "Environment must be dev, staging, prod, or demo."
  }
}

# GCS 相關變數
variable "bucket_name_suffix" {
  description = "Suffix for the GCS bucket name"
  type        = string
  default     = "rent-data-lake"
}

variable "bucket_storage_class" {
  description = "Default storage class for GCS bucket"
  type        = string
  default     = "STANDARD"

  validation {
    condition = contains([
      "STANDARD",
      "NEARLINE",
      "COLDLINE",
      "ARCHIVE"
    ], var.bucket_storage_class)
    error_message = "Storage class must be STANDARD, NEARLINE, COLDLINE, or ARCHIVE."
  }
}

variable "enable_bucket_versioning" {
  description = "Enable versioning for GCS bucket"
  type        = bool
  default     = true
}

variable "bucket_force_destroy" {
  description = "Allow Terraform to destroy bucket with objects"
  type        = bool
  default     = true
}

variable "bucket_lifecycle_age_nearline" {
  description = "Age in days to transition to NEARLINE storage"
  type        = number
  default     = 30

  validation {
    condition     = var.bucket_lifecycle_age_nearline > 0
    error_message = "Lifecycle age must be greater than 0."
  }
}

variable "bucket_lifecycle_age_coldline" {
  description = "Age in days to transition to COLDLINE storage"
  type        = number
  default     = 90

  validation {
    condition     = var.bucket_lifecycle_age_coldline > 0
    error_message = "Lifecycle age must be greater than 0."
  }
}

variable "bucket_labels" {
  description = "Labels to apply to the GCS bucket"
  type        = map(string)
  default = {
    purpose = "data-lake"
    project = "rent-analysis"
    service = "gcs-storage"
  }
}

variable "service_account_id" {
  description = "Service account ID for bucket access"
  type        = string
  default     = "terraform-sa"
}