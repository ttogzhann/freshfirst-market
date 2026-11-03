# FreshFirst on Google Cloud Compute Engine

This approval-gated deployment uses the existing production [Dockerfile](../../Dockerfile) and [Compose file](../../compose.yaml), one Debian 12 Compute Engine VM, and one attached persistent disk. PostgreSQL remains private inside Compose; only TCP port 80 is allowed by the firewall.

The default `e2-small` is modest but gives the production image build more headroom than `e2-micro`. The VM, disks, and network traffic can incur charges after trial credits/free allowances. Check current pricing and Free Trial limits for the selected region before applying.

## Google Cloud Shell

Run these commands in Cloud Shell. `terraform.tfvars` is ignored and must not be committed. Terraform state contains sensitive values, so keep this directory private.

```bash
gcloud auth list
gcloud config set project YOUR_PROJECT_ID
gcloud services enable compute.googleapis.com
cd infra/gcp
cp terraform.tfvars.example terraform.tfvars
chmod 600 terraform.tfvars
openssl rand -hex 24  # put the result in postgres_password
openssl rand -hex 32  # put the result in auth_secret
# Edit terraform.tfvars and pin repository_ref to the reviewed commit.
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform show tfplan
# Requires explicit operator approval:
terraform apply tfplan
PUBLIC_IP="$(terraform output -raw public_ip)"
curl --fail --retry 30 --retry-delay 5 "http://${PUBLIC_IP}/healthz"
```

The first boot installs Docker, mounts the persistent disk as Docker's data root, clones the selected public Git ref, builds the existing production image, and starts Compose. Compose waits for PostgreSQL's existing health check before starting the app.

## Operations and cleanup

```bash
gcloud compute ssh freshfirst --zone YOUR_ZONE
sudo docker compose -f /opt/freshfirst/compose.yaml ps
sudo docker compose -f /opt/freshfirst/compose.yaml logs --tail=100 app db
```

Before migrations or destructive operations, create and test a PostgreSQL backup. To remove only the VM and firewall while preserving the database disk:

```bash
terraform destroy -target=google_compute_instance.app -target=google_compute_firewall.http
```

Do not destroy `google_compute_disk.postgres` without a verified backup and explicit approval. Full `terraform destroy` deletes the persistent disk and is not routine cleanup.

This configuration intentionally has no SSH firewall rule, Cloud SQL, Kubernetes, load balancer, static IP, or managed secret service. Administration requires an approved access path such as Cloud Console/IAP; adding SSH/IAP is a separate reviewed change.
