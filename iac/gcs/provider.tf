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
  # 假設你的 gcs-service 目錄在原本 terraform 目錄同層
  credentials = file("../../cred/iac_sa.json")
  project     = var.project_id
  region      = var.region
}