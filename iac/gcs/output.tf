output "bucket_name" {
  description = "Name of the created GCS bucket"
  value       = google_storage_bucket.rent_data_lake.name
}

output "bucket_url" {
  description = "URL of the created GCS bucket"
  value       = "gs://${google_storage_bucket.rent_data_lake.name}"
}

output "bucket_console_url" {
  description = "Console URL of the created GCS bucket"
  value       = "https://console.cloud.google.com/storage/browser/${google_storage_bucket.rent_data_lake.name}"
}

output "bucket_location" {
  description = "Location of the GCS bucket"
  value       = google_storage_bucket.rent_data_lake.location
}

output "bucket_storage_class" {
  description = "Storage class of the GCS bucket"
  value       = google_storage_bucket.rent_data_lake.storage_class
}

output "bucket_folders" {
  description = "List of created folders in the bucket"
  value       = local.bucket_folders
}

# 給其他服務使用的輸出
output "raw_data_path" {
  description = "Path for raw data uploads"
  value       = "gs://${google_storage_bucket.rent_data_lake.name}/raw_data/rent591/"
}

output "processed_data_path" {
  description = "Path for processed data"
  value       = "gs://${google_storage_bucket.rent_data_lake.name}/processed_data/"
}