# FreshFirst on Google Cloud Compute Engine

This approval-gated deployment uses the existing production [Dockerfile](../../Dockerfile) and [Compose file](../../compose.yaml), one Debian 12 Compute Engine VM, and one attached persistent disk. Caddy provides automatic Let's Encrypt HTTPS using the free `nip.io` hostname `34.171.30.130.nip.io`; PostgreSQL remains private inside Compose. TCP/UDP ports 80 and 443 are public, while SSH remains IAP-only.

The default `e2-small` is modest but gives the production image build more headroom than `e2-micro`. The VM, disks, and network traffic can incur charges after trial credits/free allowances. Check current pricing and Free Trial limits for the selected region before applying.

## Google Cloud Shell

Run these commands in Cloud Shell. `terraform.tfvars` is ignored and must not be committed. Terraform state contains sensitive values, so keep this directory private.

```bash
gcloud auth list
gcloud config set project YOUR_PROJECT_ID
gcloud services enable compute.googleapis.com iap.googleapis.com oslogin.googleapis.com
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

The first boot installs Docker, mounts the persistent disk as Docker's data root, clones the selected public Git ref, builds the existing production image, and starts Compose. HTTPS is enabled after the one-time Caddy setup below; Compose waits for PostgreSQL's existing health check before starting the app.

The startup script configures Docker's official Debian repository before installing Docker CE and the Compose plugin. This is required on Debian 12; the distribution `docker.io` package does not reliably provide `docker-compose-plugin`.

## Verified deployment

The existing VM was provisioned without recreation or `terraform destroy` and verified at `http://34.171.30.130/`. The application returned HTTP 200 from `/healthz`, and both the Compose application and PostgreSQL services were running. This evidence does not authorize future applies or deployments.

## Approval-gated GitHub Actions deployment

The repository workflow `.github/workflows/gcp.yml` deploys only after a successful Render CI/CD workflow and only when the protected GitHub environment `gcp-production` approves the deployment job. Configure that environment with required reviewers and these environment secrets/variables:

- `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` for keyless GitHub OIDC authentication.
- `GCP_PROJECT_ID`, `GCP_VM_NAME`, and `GCP_ZONE` as non-secret environment variables.

Grant the deploy service account only the permissions required to connect through the approved administration path and restart this VM. Do not use a JSON service-account key. The workflow does not run `terraform apply`; review and apply Terraform separately with the Cloud Shell procedure above.

Install the root-owned deployment helper once on the existing VM from Cloud Shell. Run these commands from a checkout of this repository, replacing only the project and zone values; they do not stop the database volume or change the existing `.env`:

```bash
gcloud config set project freshfirst-513520
gcloud compute scp infra/gcp/freshfirst-deploy.sh freshfirst:/tmp/freshfirst-deploy.sh \
  --zone us-central1-a --tunnel-through-iap
gcloud compute ssh freshfirst --zone us-central1-a --tunnel-through-iap --command \
  'sudo install -o root -g root -m 0750 /tmp/freshfirst-deploy.sh /usr/local/sbin/freshfirst-deploy && sudo rm -f /tmp/freshfirst-deploy.sh'
```

Before starting the HTTPS profile, set the existing `/opt/freshfirst/.env` values through an interactive editor or another private method (never commit or print them):

```bash
gcloud compute ssh freshfirst --zone us-central1-a --tunnel-through-iap
# Run these commands inside the VM. They change only the two public-origin settings:
sudo sh -c 'grep -q "^FRESHFIRST_DOMAIN=" /opt/freshfirst/.env && sed -i "s#^FRESHFIRST_DOMAIN=.*#FRESHFIRST_DOMAIN=34.171.30.130.nip.io#" /opt/freshfirst/.env || echo "FRESHFIRST_DOMAIN=34.171.30.130.nip.io" >> /opt/freshfirst/.env'
sudo sh -c 'grep -q "^FRESHFIRST_TRUSTED_ORIGINS=" /opt/freshfirst/.env && sed -i "s#^FRESHFIRST_TRUSTED_ORIGINS=.*#FRESHFIRST_TRUSTED_ORIGINS=https://34.171.30.130.nip.io#" /opt/freshfirst/.env || echo "FRESHFIRST_TRUSTED_ORIGINS=https://34.171.30.130.nip.io" >> /opt/freshfirst/.env'
sudo docker compose --profile https up -d
exit
```

The approved workflow then connects through IAP and invokes only
`sudo /usr/local/sbin/freshfirst-deploy`. The helper fetches the approved branch and runs
`docker compose build --pull` and `docker compose --profile https up -d`; it never uses `down -v`.
Caddy redirects HTTP to HTTPS, obtains the certificate for the configured hostname, and persists
certificates/configuration in `freshfirst-caddy-data` and `freshfirst-caddy-config`. Do not remove
those named volumes. Replace the `nip.io` hostname with a domain you control if one becomes available.

## Operations and cleanup

```bash
gcloud compute ssh freshfirst --zone YOUR_ZONE --tunnel-through-iap
sudo docker compose -f /opt/freshfirst/compose.yaml ps
sudo docker compose -f /opt/freshfirst/compose.yaml logs --tail=100 app db
```

Before migrations or destructive operations, create and test a PostgreSQL backup. To remove only the VM and firewall while preserving the database disk:

```bash
terraform destroy -target=google_compute_instance.app -target=google_compute_firewall.http
```

Do not destroy `google_compute_disk.postgres` without a verified backup and explicit approval. Full `terraform destroy` deletes the persistent disk and is not routine cleanup.

The only administration ingress is TCP 22 from Google's IAP TCP forwarding range, used with `--tunnel-through-iap`; application traffic remains the only public ingress. Before using SSH or the GitHub workflow, grant the deploy identity only the required IAP tunnel and OS Login permissions. There is no Cloud SQL, Kubernetes, load balancer, static IP, or managed secret service.
