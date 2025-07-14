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

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "asia-east1-b"
}

variable "machine_type" {
  description = "Machine type for VM"
  type        = string
  default     = "e2-standard-2"
}

variable "vm_name" {
  description = "Name of the VM instance"
  type        = string
  default     = "app-vm"
}