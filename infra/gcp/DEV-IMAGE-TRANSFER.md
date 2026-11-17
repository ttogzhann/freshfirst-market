# Held dev image transfer without VM registry credentials

Draft PR #98 remains blocked and must not be merged as-is. This replacement
prepares the alternative transport; **dev and both production jobs stay held**.
No live image build, transfer, import or deployment has been performed here.

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
- Install the updated `freshfirst-release.sh` as root:root mode 0750 and
  `verify-image-archive.py` at `/opt/freshfirst/infra/gcp/verify-image-archive.py`
  as root:root mode 0644. Install both together; retain existing Compose/env/
  allowlist files. Never read or replace production secrets.
- Verify the exact archive-mode arguments are allowed by noninteractive sudo.
  The updated manual preflight sends EOF with dummy nonsecret hashes/size and
  expects `Missing image archive on stdin` before any Docker call. Re-run only
  after separate approval; the older installed helper is not archive-compatible.
- With separate approval, validate an actual Docker-save/load on the VM's Docker
  version, free disk and memory headroom while keeping the release job held. The
  current tests use synthetic archives and mocked Docker/SSH, not a live import.
- Only after transport verification, approve removal of **dev's** hold in a
  separate PR and coordinate a fresh feature-push CI run. Preserve both production
  holds and manual preflight. Verify app health, ID/digest metadata, resource
  limits, dev database volume and unchanged production metadata/URL/records.

The previous audit limitations are not declared resolved. If stdin/session
recording exists, it may capture image contents (reviewed application code), but
not a registry bearer token. The image must remain free of baked credentials and
personal data; never add credentials to build args, layers or archive metadata.
The unchanged, held legacy production helper path is not part of this dev design
and is not activated by this PR.
