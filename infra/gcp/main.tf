data "google_compute_image" "debian" {
  family  = "debian-12"
  project = "debian-cloud"
}

data "google_compute_network" "default" {
  name = "default"
}

resource "google_compute_disk" "postgres" {
  name = "freshfirst-postgres"
  type = "pd-standard"
  zone = var.zone
  size = var.postgres_disk_size_gb
}

resource "google_compute_firewall" "http" {
  name    = "freshfirst-allow-http"
  network = data.google_compute_network.default.id

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["freshfirst-http"]
}

resource "google_compute_firewall" "iap_ssh" {
  name    = "freshfirst-allow-iap-ssh"
  network = data.google_compute_network.default.id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["freshfirst-iap-ssh"]
}

resource "google_compute_instance" "app" {
  name         = "freshfirst"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["freshfirst-http", "freshfirst-iap-ssh"]

  boot_disk {
    initialize_params {
      image = data.google_compute_image.debian.self_link
      type  = "pd-standard"
      size  = 20
    }
  }

  attached_disk {
    source      = google_compute_disk.postgres.id
    device_name = "freshfirst-postgres"
  }

  network_interface {
    network = data.google_compute_network.default.id
    access_config {}
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh.tftpl", {
    auth_secret       = var.auth_secret
    postgres_password = var.postgres_password
    repository_ref    = var.repository_ref
    repository_url    = var.repository_url
  })
}
