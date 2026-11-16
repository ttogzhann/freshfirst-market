# Milestone 1: immutable GCP releases

Repository preparation only; none of these prerequisites has been installed or
verified against production by this change. Existing VM, Terraform resources,
persistent disk, Caddy URL and `render.yml` CI are retained.

## Release path

Successful **push** CI on `feature/render-deployment` triggers `gcp.yml` to check
out that CI run's exact SHA, build one release image, publish its SHA tag to
Artifact Registry, and deploy its immutable digest to dev. Existing CI image
builds remain checks; the published release is never rebuilt on either VM.
The `healthy-dev-release` artifact records source SHA, digest and run IDs only
after the helper reports healthy. Production runs only through manual dispatch
with the successful dev run ID, digest and source SHA. It validates both run
records and the artifact before OIDC authentication, then pulls that same digest.

## Operator prerequisites (separate approval required)

- Merge/install the reviewed `gcp.yml` workflow **and its promotion verifier** on
  the repository default branch: `workflow_run` does not activate just because
  its file exists on a feature branch. Dispatch production from
  `feature/render-deployment`. Existing Render CI/deploy workflow is unchanged.
- Create/reuse one regional Docker Artifact Registry repository, preferably
  `us-central1`, and enable its API. Retain deployed/rollback digests; cleanup
  must not delete them. Artifact retention here is 90 days: archive release
  metadata before expiry if a longer rollback window is required.
- Configure `gcp-development` (automatic, no approval gate) and `gcp-production`
  (required reviewers, restricted deployment branch). In each set
  `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`,
  `GCP_VM_NAME`, `GCP_ZONE`. Dev also needs `GCP_ARTIFACT_REGISTRY_HOST`
  (`us-central1-docker.pkg.dev`) and `GCP_IMAGE_REPOSITORY`
  (`us-central1-docker.pkg.dev/PROJECT/REPOSITORY/app`).
- Reuse keyless OIDC, restrict trust to this repository/approved workflow and
  environments. Dev builder needs Artifact Registry Writer on this repository;
  runtime VM identity needs Reader. Deploy identities need only existing IAP/
  SSH permissions and permission to invoke the root-owned release helper.
  The VM's existing OAuth access scopes must permit Artifact Registry access;
  IAM alone is insufficient. Changing scopes/identity is an operator task,
  never a reason to recreate this VM or disk. No service-account JSON key.
- Review host memory/disk headroom for two app/PostgreSQL stacks on the current
  VM. Both use the same Docker data-root on the existing persistent disk, but
  distinct named volumes; no mandatory new cloud resources.

## One-time host setup

After reviewing a pinned checkout, install `freshfirst-release.sh` as
`/usr/local/sbin/freshfirst-release` (root:root, mode 0750), the reviewed
`compose.image.yaml` and `compose.dev.yaml` into `/opt/freshfirst/infra/gcp/`, and
`deploy.conf.example` as `/etc/freshfirst/deploy.conf` (root:root, mode 0600).
Set its exact image repository allowlist. Retain the old helper as a legacy
tool; the new workflow never invokes its branch-reset/build behavior.

Keep production `/opt/freshfirst/.env` values unchanged; ensure root ownership
and mode 0600. Use an independent `/etc/freshfirst/dev.env` (root:root, 0600)
from `dev.env.example`, replacing both secret placeholders with independently
generated values. Never copy production secrets or data into dev.

| Environment | Compose project         | PostgreSQL volume                                | App endpoint                                  |
| ----------- | ----------------------- | ------------------------------------------------ | --------------------------------------------- |
| prod        | `freshfirst` (existing) | `freshfirst_freshfirst-postgres-data` (existing) | existing Caddy `https://34.171.30.130.nip.io` |
| dev         | `freshfirst-dev`        | `freshfirst-dev_freshfirst-postgres-data`        | `http://127.0.0.1:8081` via SSH tunnel        |

Project-scoped networks and containers are separate. Bootstrap only the dev
database once (operator-approved command on the VM):

```bash
sudo docker compose --project-directory /opt/freshfirst --project-name freshfirst-dev \
  --env-file /etc/freshfirst/dev.env -f /opt/freshfirst/compose.yaml \
  -f /opt/freshfirst/infra/gcp/compose.dev.yaml up -d db
```

Dev requires Docker Compose >= 2.24.4. The release helper automatically adds
`compose.dev.yaml` only for dev; production uses only the base and image files.
The overlay limits app to 384 MiB/0.25 CPU and PostgreSQL to 128 MiB/0.15 CPU,
disables swap and automatic restart for both, and reduces PostgreSQL buffers,
per-operation memory and connection count. Dev binds only `127.0.0.1:8081` and
removes Caddy entirely, including when the HTTPS profile is requested. These
are resource ceilings, not evidence of runtime capacity on the shared VM.
Bootstrap must include the overlay so the database receives its limits;
app-only releases do not retrofit limits onto an existing database container.

Verify the existing production project/volume identities before installation;
if they differ from this table, reconcile the reviewed configuration first.
Normal releases require a healthy existing database and update **only app**;
they do not recreate PostgreSQL, Caddy, networks or volumes. Secrets remain in
their env files. The helper uses the VM token through ephemeral Docker login.

## Deploy, health and rollback

After external prerequisites, the next step is a reviewed push/CI run (not
performed here). Confirm successful automatic dev health and save `release.json`.
Test dev through an IAP SSH local-forward tunnel to port 8081. Promote manually
in the GCP workflow with that exact run ID/SHA/digest, then verify production
`https://34.171.30.130.nip.io/healthz` and an authenticated smoke journey.

The helper stores `current-image`, `previous-image` and, on failure,
`pending-image` under `/var/lib/freshfirst-releases/{dev,prod}`. It waits up to
150 seconds for container health; failed health fails the workflow and does
not mark the release current. It does not automatically restore a database.
Inspect app logs without printing environment secrets. After checking schema
compatibility, roll back by dispatching the **previous successful dev run**
and its recorded digest/SHA; this promotes the old image without rebuilding.
An operator may invoke `sudo /usr/local/sbin/freshfirst-release prod IMAGE@sha256:DIGEST`
with that same approved previous digest if Actions/artifacts are unavailable.

Before first image-based promotion, record and retain the currently running
legacy local image ID and a tested PostgreSQL backup. Its local image may not
have an Artifact Registry digest: restoring that initial legacy image is a
separate reviewed Compose operation using the retained image, not a dispatch
of an invented digest. Never prune the retained image during this transition.
Image rollback is safe only across compatible database schemas. Review startup
migrations and back up before incompatible changes; never delete/reset a
database or use `down -v` to make a deployment succeed.
