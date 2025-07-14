output "vm_external_ip" {
  description = "External IP address of the VM"
  value       = google_compute_address.static_ip.address
}

output "vm_internal_ip" {
  description = "Internal IP address of the VM"
  value       = google_compute_instance.vm_instance.network_interface[0].network_ip
}

output "vm_name" {
  description = "Name of the VM instance"
  value       = google_compute_instance.vm_instance.name
}

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}