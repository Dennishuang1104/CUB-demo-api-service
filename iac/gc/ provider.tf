terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
  required_version = ">= 1.0"
}

provider "google" {
  credentials = file("../../cred/iac_sa.json")
  project     = var.project_id
  region      = var.region
  zone        = var.zone
}