project_id   = "adept-turbine-339912"
region       = "asia-east1"
environment  = "demo"

# GCS 設定
bucket_name_suffix               = "rent-data-lake"
bucket_storage_class             = "STANDARD"
enable_bucket_versioning         = true
bucket_force_destroy             = true
bucket_lifecycle_age_nearline    = 30
bucket_lifecycle_age_coldline    = 90

# 服務帳戶
service_account_id = "terraform-sa"

# 標籤
bucket_labels = {
  purpose = "data-lake"
  project = "rent-analysis"
  service = "gcs-storage"
  owner   = "data-team"
}