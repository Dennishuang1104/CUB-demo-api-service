# 啟用必要的 API
resource "google_project_service" "storage_api" {
  service = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_api" {
  service = "bigquery.googleapis.com"
  disable_on_destroy = false
}

# 主要資料湖 Bucket
resource "google_storage_bucket" "rent_data_lake" {
  name     = "${var.project_id}-${var.bucket_name_suffix}"
  location = var.region

  # 基本設定
  storage_class = var.bucket_storage_class
  force_destroy = var.bucket_force_destroy

  # 啟用版本控制
  versioning {
    enabled = var.enable_bucket_versioning
  }

  # 生命週期管理
  lifecycle_rule {
    condition {
      age = var.bucket_lifecycle_age_nearline
    }
    action {
      type = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = var.bucket_lifecycle_age_coldline
    }
    action {
      type = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  # 統一存取控制
  uniform_bucket_level_access = true

  # 標籤
  labels = merge(
    var.bucket_labels,
    {
      environment = var.environment
      created_by  = "terraform"
    }
  )

  depends_on = [google_project_service.storage_api]
}

# 建立目錄結構
locals {
  bucket_folders = [
    "raw_data/",
    "raw_data/rent591/",
    "processed_data/",
    "processed_data/cleaned/",
    "processed_data/enriched/",
    "archive/",
    "logs/",
    "temp/"
  ]
}

resource "google_storage_bucket_object" "folders" {
  for_each = toset(local.bucket_folders)

  name    = each.value
  bucket  = google_storage_bucket.rent_data_lake.name
  content = " "
}

# 取得服務帳戶
data "google_service_account" "existing_sa" {
  account_id = var.service_account_id
}

# 取得專案資訊
data "google_project" "current" {}

# IAM 權限設定
resource "google_storage_bucket_iam_member" "bucket_admin" {
  bucket = google_storage_bucket.rent_data_lake.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${data.google_service_account.existing_sa.email}"
}

resource "google_storage_bucket_iam_member" "bucket_object_admin" {
  bucket = google_storage_bucket.rent_data_lake.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_service_account.existing_sa.email}"
}

# # BigQuery 存取權限（外部表用）
# resource "google_storage_bucket_iam_member" "bq_access" {
#   bucket = google_storage_bucket.rent_data_lake.name
#   role   = "roles/storage.objectViewer"
#   member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-bigquery.iam.gserviceaccount.com"
# }

# Compute Engine 預設服務帳戶存取權限（VM 用）
resource "google_storage_bucket_iam_member" "compute_access" {
  bucket = google_storage_bucket.rent_data_lake.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}