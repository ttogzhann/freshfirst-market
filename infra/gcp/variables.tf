variable "project_id" { type = string }

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "machine_type" {
  description = "e2-small gives the production Docker build more headroom than e2-micro."
  type        = string
  default     = "e2-small"
}

variable "postgres_disk_size_gb" {
  type    = number
  default = 30
}

variable "repository_url" {
  type    = string
  default = "https://github.com/ttogzhann/freshfirst-market.git"
}

variable "repository_ref" {
  description = "Pin to a reviewed commit or release branch before apply."
  type        = string
  default     = "feature/render-deployment"
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "auth_secret" {
  type      = string
  sensitive = true
}
