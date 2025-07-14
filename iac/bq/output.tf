output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.cathay_bank_demo.dataset_id
}

output "table_id" {
  description = "BigQuery table ID"
  value       = google_bigquery_table.rent_data.table_id
}

output "console_url" {
  description = "BigQuery console URL"
  value       = "https://console.cloud.google.com/bigquery?project=${var.project_id}"
}

output "phone_policy_tag" {
  description = "Phone policy tag name"
  value       = google_data_catalog_policy_tag.phone_tag.name
}