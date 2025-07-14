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

variable "bucket_name" {
  description = "GCS bucket name for external table"
  type        = string
  default     = "adept-turbine-339912-rent-data-lake"
}