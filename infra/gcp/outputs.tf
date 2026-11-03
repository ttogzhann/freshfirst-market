output "public_ip" {
  value = google_compute_instance.app.network_interface[0].access_config[0].nat_ip
}

output "healthcheck_url" {
  value = "http://${google_compute_instance.app.network_interface[0].access_config[0].nat_ip}/healthz"
}
