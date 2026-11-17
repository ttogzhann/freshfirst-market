# Held dev image transfer without VM registry credentials

Draft PR #98 remains blocked and must not be merged as-is. This replacement
prepares the alternative transport; **dev and both production jobs stay held**.
This comparison fix performs no live transfer/import or deployment. The
operator's separate import-test evidence is recorded below.

## Chain of verification

1. Existing successful feature-push CI remains the source gate. Build/publish one
   linux/amd64 release image; retain the original Artifact Registry digest.
2. Refresh the existing GitHub OIDC deployer's runner credentials after building.
   Pull that exact digest on the authenticated runner and require Docker's
   `RepoDigests` to contain the requested immutable reference. Record its content
   image ID (the SHA-256 of the image configuration).
3. Save by image ID, without tags, to a runner temporary archive. Compute its
   SHA-256 and byte size. Send only archive bytes over existing IAP SSH without a
   TTY. The remote arguments contain only the allowlisted registry reference,
   archive hash/size and image ID. No credential output, registry token, login
   config, environment file or database is transferred. Runner cleanup removes
   the archive on success/failure; OIDC action cleanup removes runner credentials.
4. The reviewed root helper bounds stdin to the declared size (maximum 1 GiB),
   checks disk headroom (3x archive size + 512 MiB), and stages the archive in a
   root-only directory under `/var/lib/freshfirst-releases/dev`. It checks the full
   archive hash/size, image-config hash, linux/amd64 architecture and every
   uncompressed layer hash against the config's `rootfs.diff_ids`. Uncompressed
   and gzip layers are supported, with a 1 GiB combined expansion cap and a second
   disk-headroom check on the actual Docker data-root filesystem requiring
   2x expanded bytes + 512 MiB free for content/unpacked layers. Staging and
   Docker storage can be on different disks. Other compression fails closed.
5. Before any image bytes reach Docker, the verifier rejects tagged/multi-image
   archives, invalid paths/types, duplicate members and oversized metadata. It
   emits a normalized archive containing only the verified config/layers and an
   untagged manifest. Extra OCI annotations/metadata never reach Docker, so load
   cannot replace a production tag. No files are extracted by the verifier.
6. Import without registry access. Require the imported ID and running dev
   container's ID to match. Use `FRESHFIRST_IMAGE=sha256:CONFIG_DIGEST` with the
   existing image/dev overlays and `up --no-deps --no-build --pull never app`.
   Preserve existing database/network/volume/port/resource isolation.

Docker-save/load need not retain `RepoDigests`. The registry digest is verified
on the trusted authenticated runner, then bound to the archive checksum and
config/layer hashes over authenticated SSH. Do not invent a registry digest on
the loaded image or treat a mutable tag as equivalent. This is not a standalone
signed archive: it trusts the reviewed Actions runner and existing SSH identity.

## Release evidence and cleanup

`release.json` retains image/digest/source SHA/CI run/dev run/healthy fields and
adds `transport=verified-image-archive`, `image_id`, `archive_sha256`,
`archive_size`. It is uploaded only after helper health succeeds. The helper
retains the original registry reference in `dev/current-image`, local ID in
`dev/current-image-id` and archive hash/size in `dev/current-archive`. Pending
records survive an unhealthy app for diagnosis; no database rollback is attempted.
The temporary VM archive is removed before app recreation and on handled errors
or signals. An uncatchable kill can leave noncredential image bytes for operator
cleanup; no registry credential is ever created by the dev path.

For rollback, re-deliver a previously approved registry digest through this same
verified transport after schema review. `previous-image` can be a local config ID;
do not pass it to the registry-digest interface as a replacement digest.

## Remaining activation requirements (separate approval)

- Review/merge this held PR; keep draft PR #98 blocked. Do not remove any holds.
- Install `freshfirst-release.sh` separately as
  `/usr/local/sbin/freshfirst-release-dev-archive` (root:root, 0750) and the verifier
  at `/usr/local/lib/freshfirst-dev-archive/verify-image-archive.py` (root:root, 0644).
  Never overwrite `/usr/local/sbin/freshfirst-release`, existing Compose/env/
  allowlist files or volumes. The new entry point rejects production mode.
- Verify the exact archive-mode arguments are allowed by noninteractive sudo.
  The updated manual preflight sends EOF with dummy nonsecret hashes/size and
  expects `Missing image archive on stdin` before any Docker call. Re-run only
  after separate approval. The operator has already installed the archive helper.
- The operator reports the approved BusyBox import passed with resource headroom,
  as described below. Compare the saved evidence using the normalizer; do not
  repeat installation or import for this fix.
- Only after transport verification, approve removal of **dev's** hold in a
  separate PR and coordinate a fresh feature-push CI run. Preserve both production
  holds and manual preflight. Verify app health, ID/digest metadata, resource
  limits, dev database volume and unchanged production metadata/URL/records.

The previous audit limitations are not declared resolved. If stdin/session
recording exists, it may capture image contents (reviewed application code), but
not a registry bearer token. The image must remain free of baked credentials and
personal data; never add credentials to build args, layers or archive metadata.
The existing legacy production helper is not replaced or activated by this PR.

## One Cloud Shell installation/import-only procedure (approval required)

**Existing VM: do not repeat installation/import.** The operator reports that
the helper/verifier from `9d786f5` imported the approved BusyBox digest
`sha256:63bb1322b9692d0a4ba0084a8168277d767a73048fc79a4869b912fe32d26bee`
with config/layer/archive checks passing, 825 MiB available RAM and 26 GiB free
Docker disk. Production/container/volume/Compose evidence was unchanged except
Caddy's mount-array ordering; dev PostgreSQL stayed healthy. These are operator
observations, not a new live verification by this change.

`normalize-production-snapshot.py` sorts complete mount objects, JSON object keys
and container records, while preserving every mount field and all other metadata
and file hashes. It supports both the earlier raw format and new JSON lines. For
the already collected evidence, run only this local comparison in Cloud Shell
from a checkout containing the new normalizer (set `CHECK_DIR` to the saved path):

```bash
python3 infra/gcp/normalize-production-snapshot.py "$CHECK_DIR/production.before" > "$CHECK_DIR/production.before.normalized"
python3 infra/gcp/normalize-production-snapshot.py "$CHECK_DIR/production.after" > "$CHECK_DIR/production.after.normalized"
cmp "$CHECK_DIR/production.before.normalized" "$CHECK_DIR/production.after.normalized"
```

This compares metadata, not database contents. Unexpected/missing records fail
closed. No repeat image transfer or production audit is required for this fix.

After separately approving and merging this still-held PR, run only the manual
archive EOF preflight (no import or deployment):

```bash
gh workflow run gcp.yml --repo ttogzhann/freshfirst-market --ref main \
  -f preflight=true -f publish_test_image=false -f deploy=false
```

Run from an authenticated operator's repository checkout only after approval of
the exact commit and an existing small test-image digest in the configured app
repository. This fresh-host reference procedure creates only
two new host files plus their directory, imports one untagged test image, and
does not start a container. Existing target files cause an abort instead of an
overwrite. Import-only mode requires 512 MiB available RAM, limits the archive
and expanded layers to 64 MiB, checks both disks, and preserves release records.

```bash
set -euo pipefail
REVIEWED_SHA=REPLACE_WITH_APPROVED_COMMIT
IMAGE=us-central1-docker.pkg.dev/freshfirst-513520/freshfirst/app@sha256:REPLACE_WITH_APPROVED_SMALL_TEST_DIGEST
EXPECTED_CONFIG_ID=sha256:REPLACE_WITH_APPROVED_CONFIG_DIGEST
[[ "$REVIEWED_SHA" =~ ^[a-f0-9]{40}$ ]]
[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/freshfirst-513520/freshfirst/app@sha256:[a-f0-9]{64}$ ]]
[[ "$EXPECTED_CONFIG_ID" =~ ^sha256:[a-f0-9]{64}$ ]]
CHECK_DIR=$(mktemp -d)
FLAGS=(--project=freshfirst-513520 --zone=us-central1-a --tunnel-through-iap --quiet)
vm() { gcloud compute ssh freshfirst "${FLAGS[@]}" --ssh-flag=-T --command "$1"; }
for file in freshfirst-release.sh verify-image-archive.py normalize-production-snapshot.py; do
  git show "$REVIEWED_SHA:infra/gcp/$file" > "$CHECK_DIR/$file"
done
SNAPSHOT='set -eu; sudo -n sha256sum /usr/local/sbin/freshfirst-release /opt/freshfirst/compose.yaml /opt/freshfirst/infra/gcp/compose.image.yaml /opt/freshfirst/infra/gcp/compose.dev.yaml; ids=$(sudo -n docker ps -aq --filter label=com.docker.compose.project=freshfirst); test -n "$ids"; sudo -n docker inspect --format "{\"name\":{{json .Name}},\"id\":{{json .Id}},\"image\":{{json .Image}},\"started_at\":{{json .State.StartedAt}},\"restart_count\":{{json .RestartCount}},\"ports\":{{json .HostConfig.PortBindings}},\"mounts\":{{json .Mounts}}}" $ids'
RESOURCES='set -eu; free -m; root=$(sudo -n docker info --format "{{.DockerRootDir}}"); df -h /var/lib/freshfirst-releases/dev "$root"; ids=$(sudo -n docker ps -q --filter label=com.docker.compose.project=freshfirst); test -n "$ids"; sudo -n docker stats --no-stream --format "{{.Name}} {{.MemUsage}} {{.CPUPerc}}" $ids'
vm "$SNAPSHOT" | python3 "$CHECK_DIR/normalize-production-snapshot.py" > "$CHECK_DIR/production.before"
vm "$RESOURCES"
curl -fsS --max-time 15 -o /dev/null https://34.171.30.130.nip.io/healthz

vm 'sudo -n test ! -e /usr/local/sbin/freshfirst-release-dev-archive && sudo -n test ! -L /usr/local/sbin/freshfirst-release-dev-archive && sudo -n test ! -e /usr/local/lib/freshfirst-dev-archive && sudo -n test ! -L /usr/local/lib/freshfirst-dev-archive'
STAGE=$(vm 'mktemp -d /tmp/freshfirst-archive-check.XXXXXX')
[[ "$STAGE" =~ ^/tmp/freshfirst-archive-check\.[A-Za-z0-9]+$ ]]
gcloud compute scp "${FLAGS[@]}" "$CHECK_DIR/freshfirst-release.sh" "$CHECK_DIR/verify-image-archive.py" "freshfirst:$STAGE/"
vm "sudo -n install -d -o root -g root -m 0755 /usr/local/lib/freshfirst-dev-archive && sudo -n install -o root -g root -m 0750 '$STAGE/freshfirst-release.sh' /usr/local/sbin/freshfirst-release-dev-archive && sudo -n install -o root -g root -m 0644 '$STAGE/verify-image-archive.py' /usr/local/lib/freshfirst-dev-archive/verify-image-archive.py"
H=$(sha256sum "$CHECK_DIR/freshfirst-release.sh" | cut -d ' ' -f 1)
V=$(sha256sum "$CHECK_DIR/verify-image-archive.py" | cut -d ' ' -f 1)
vm "printf '%s  %s\n' '$H' /usr/local/sbin/freshfirst-release-dev-archive '$V' /usr/local/lib/freshfirst-dev-archive/verify-image-archive.py | sudo -n sha256sum -c -"

# Authentication is local to Cloud Shell; no credential is copied to the VM.
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
docker pull --platform linux/amd64 "$IMAGE"
docker image inspect --format '{{json .RepoDigests}}' "$IMAGE" | python3 -c 'import json,sys; assert sys.argv[1] in json.load(sys.stdin)' "$IMAGE"
docker manifest inspect "$IMAGE" > "$CHECK_DIR/manifest.json"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["config"]["digest"] == sys.argv[2]' "$CHECK_DIR/manifest.json" "$EXPECTED_CONFIG_ID"
LOCAL_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE")
[[ "$LOCAL_ID" == "$EXPECTED_CONFIG_ID" || "$LOCAL_ID" == "${IMAGE##*@}" ]]
docker image save --output "$CHECK_DIR/raw.tar" "$LOCAL_ID"
[[ $(stat -c %s "$CHECK_DIR/raw.tar") -lt 67108864 ]]
python3 "$CHECK_DIR/verify-image-archive.py" "$CHECK_DIR/raw.tar" "$EXPECTED_CONFIG_ID" "$CHECK_DIR" 67108864 > "$CHECK_DIR/test.tar"
HASH=$(sha256sum "$CHECK_DIR/test.tar" | cut -d ' ' -f 1)
SIZE=$(stat -c %s "$CHECK_DIR/test.tar")
[[ "$SIZE" -le 67108864 ]]
IMPORT_RC=0
cat "$CHECK_DIR/test.tar" | vm "sudo -n /usr/local/sbin/freshfirst-release-dev-archive dev '$IMAGE' --verify-image-archive-stdin '$HASH' '$SIZE' '$EXPECTED_CONFIG_ID'" || IMPORT_RC=$?

vm "$SNAPSHOT" | python3 "$CHECK_DIR/normalize-production-snapshot.py" > "$CHECK_DIR/production.after"
cmp "$CHECK_DIR/production.before" "$CHECK_DIR/production.after"
vm "$RESOURCES"
curl -fsS --max-time 15 -o /dev/null https://34.171.30.130.nip.io/healthz
[[ "$IMPORT_RC" -eq 0 ]] || { printf 'Import failed (exit %s); stop without repairs.\n' "$IMPORT_RC"; exit "$IMPORT_RC"; }
printf 'Import-only test passed; production metadata/helper/Compose hashes unchanged. Evidence: %s\n' "$CHECK_DIR"
```

On any failure, stop; do not change permissions, clean images globally or reset
databases. The imported untagged test image intentionally remains for inspection;
never prune shared images automatically. Staging contains source files only.
Production secrets and database contents are never read. After separately merging
the still-held PR and installing these files, approve the updated GitHub manual
archive EOF preflight to recheck the deployer's new entry point. No automatic
deployment is enabled by installation or an import-only test.
