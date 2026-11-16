# Milestone 1: immutable GCP releases

Repository preparation only; none of these prerequisites has been installed or
verified against production by this change. Existing VM, Terraform resources,
persistent disk, Caddy URL and `render.yml` CI are retained.

Optional backend telemetry is documented in [the observability setup](../observability/README.md).
It is disabled by default and its separate overlay is not loaded by the release helper.

## Release path

**Current state: check-only pushes; dev activation is held.** The Render workflow
is now named `FreshFirst checks`, so its completion does not match the legacy
default-branch GCP workflow's `FreshFirst Render CI/CD` listener. All five test/
build jobs are retained. Render deployment requires manual dispatch with
`deploy=true`, the feature branch, successful checks and the `render-production`
environment gate. Keep Render service auto-deploy disabled (`render.yaml`).
Existing queued/running deployments and older workflow revisions are not
cancelled by these local changes; review them before any authorized push.

The prepared `gcp.yml` listens to the new CI name but its dev job has an explicit
`false &&` activation hold. Do not remove it until every prerequisite below is
verified. GCP production requires manual dispatch with `deploy=true`, exact
successful dev metadata and the `gcp-production` environment gate. Required
environment reviewers must be configured externally; YAML alone cannot install
approval protection. No deployment is enabled or performed by this local work.

After activation, successful **push** CI on `feature/render-deployment` triggers `gcp.yml` to check
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
  `feature/render-deployment`. Replace the legacy GCP listener with this reviewed
  revision; do not restore its old CI-name listener. Configure `render-production`
  required reviewers and deployment branch restrictions before manual Render use.
- Create/reuse one regional Docker Artifact Registry repository, preferably
  `us-central1`, and enable its API. Retain deployed/rollback digests; cleanup
  must not delete them. Artifact retention here is 90 days: archive release
  metadata before expiry if a longer rollback window is required.
- Configure `gcp-development` (automatic, no approval gate) and `gcp-production`
  (required reviewers, restricted deployment branch). In each set
  `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_PROJECT_ID`, `GCP_VM_NAME`, `GCP_ZONE`.
  Dev uses `GCP_DEPLOY_SERVICE_ACCOUNT`; production uses `GCP_SERVICE_ACCOUNT`.
  Dev also needs `GCP_ARTIFACT_REGISTRY_HOST`
  (`us-central1-docker.pkg.dev`) and `GCP_IMAGE_REPOSITORY`
  (`us-central1-docker.pkg.dev/PROJECT/REPOSITORY/app`).
- Reuse keyless OIDC, restrict trust to this repository/approved workflow and
  environments. Dev builder needs Artifact Registry Writer on this repository;
  the existing federated deployer must be allowed to mint its access token through
  the restricted `roles/iam.workloadIdentityUser` binding on that service account.
  Deploy identities also need existing IAP/SSH permissions and noninteractive
  permission to invoke the root-owned release helper. Dev needs no attached VM
  service account, metadata token, VM scope change or restart. No permanent key.
  Production retains its previous metadata-token login; its separate runtime
  identity/scope prerequisite remains for any future production promotion.
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
Dev secret independence is established by generating new values at installation;
the dev helper does not read or compare production's environment file.

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
their env files. Dev uses the short-lived stdin credential described below;
production retains its existing metadata-token login.

## Short-lived dev registry authentication

After the build, a second existing OIDC auth action requests a **600-second**
OAuth access token for `GCP_DEPLOY_SERVICE_ACCOUNT`. It also refreshes the runner's
temporary federated credential file for IAP/SSH, so a long build cannot leave SSH
using an expired original GitHub OIDC credential. Action post-job cleanup removes
both auth steps' temporary files; no service-account key is created. The action
masks its token output. The deploy step receives it via an environment value and
pipes it directly to `gcloud compute ssh --ssh-flag=-T`, then
`sudo -n /usr/local/sbin/freshfirst-release dev IMAGE@sha256:DIGEST --registry-token-stdin`.
The token never appears in the SSH command, process arguments, release metadata,
artifacts or persistent environment files. Do not upload auth-generated
`gha-creds-*.json` files or the workspace wholesale. Shell tracing is disabled
before handling the token.

The helper requires a bounded, nonempty token line for dev, never falls back to
metadata, and passes it to `docker login --password-stdin` against the configured
registry only. Missing/malformed tokens fail before Docker is called; rejected or
expired tokens fail login/pull without updating app. Docker credentials live in
a root-only temporary `/run/freshfirst-registry.*` directory with `umask 077`.
They are deleted immediately after pull and on ordinary failure/INT/TERM; the
token shell variable is unset after login. No app-container credential is added.
An uncatchable kill can leave the private temporary config until operator cleanup
or reboot; the credential still expires. Never archive `/run` credentials.

Before activation, verify the existing sudo policy permits the exact dev command
without a password or TTY, and that SSH/sudo/session auditing does **not record
stdin** for this command (for example, applicable sudo `log_input` must be off).
Do not use `sudo -S`, PTY allocation, shell tracing, verbose request dumps or token
files to work around access failures. Tokens inherit the deployer's IAM scope;
keep Artifact Registry Writer repository-scoped rather than project-wide.

This prepares dev authentication only. Production token-stdin mode is rejected;
its workflow and manual approval gate are unchanged. Operator CLI dev invocations
must also supply a freshly minted token on stdin, never as a command argument.

Reference: [OIDC auth action](https://github.com/google-github-actions/auth) and
[Artifact Registry access-token login](https://docs.cloud.google.com/artifact-registry/docs/docker/authentication).

Activation requires separate approvals, in this order:

1. Verify/create the registry and restricted OIDC/IAM/IAP configuration; set the
   documented environment variables and production environment reviewer gates.
2. Install this exact helper and reviewed Compose files on the existing VM;
   verify `/run` is temporary/private, the sudo/stdin conditions above, host
   headroom, independent `0600` dev secrets, project/volume isolation and the
   healthy dev database. Do not attach an identity or restart the VM for dev pulls.
3. Publish the reviewed branch, run check-only CI, and install the held workflow
   and promotion verifier on the default branch while GCP remains disabled.
4. Only after prerequisites pass, separately review removal of `false &&`,
   enable the new GCP workflow and authorize a feature push. Save the healthy dev
   artifact and verify dev through the SSH tunnel. Do not dispatch production.

## Deploy, health and rollback

After external prerequisites are verified, a separately reviewed change may remove
the dev job's `false &&` hold. The next step is an authorized push/CI run (not
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
