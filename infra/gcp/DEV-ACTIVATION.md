# Dev activation candidate: auditing remains unresolved

**Draft only. Do not merge or dispatch a deployment.** The GCP workflow is already
enabled for preflight; merging this candidate would enable its automatic dev job
for successful feature-branch push CI. Both production jobs retain explicit
`false &&` holds, and the manual preflight job is unchanged.

## Evidence and limitation

OIDC preflight run `43936970514` passed for OS Login identity
`sa_113856971648595959818`: SSH, passwordless noninteractive sudo, and the helper's
exact missing-token rejection were verified. It sent no registry credential.

The operator reports `use_pty`, no explicit sudo input/output logging directives,
`forcecommand none`, `usepam yes`, no obvious recorder in the inspected PAM chains,
and no tlog/SSSD recording configuration. `sudo -V` describes logging capabilities,
not proof they are enabled. `auditctl` is unavailable. External/session recording
and custom I/O hooks remain unverified. These findings do **not** establish that
forwarding a registry bearer token through SSH/sudo stdin is safe.

Before using the existing token-forwarding helper, obtain administrator evidence
covering the exact identity, command and non-TTY IAP connection: effective sudo
input logging (including command tags/non-TTY stdin), SSH/PAM/session hooks and
external recording. Do not send a real token as a recording test.

## Safer alternative if recording cannot be ruled out

Keep registry credentials on the ephemeral GitHub runner. Pull the approved
immutable image there and transfer only a credential-free image archive over IAP
SSH, then load it on the VM. Bind the archive checksum and image identity to the
original registry digest/source SHA in release metadata and verify them before
loading/deploying. Do not assume that loading an archive preserves `RepoDigests`.
Include no credentials, environment files or database contents in the archive.

Docker supports [saving](https://docs.docker.com/reference/cli/docker/image/save/)
and [loading](https://docs.docker.com/reference/cli/docker/image/load/) image
archives. This alternative needs a separately reviewed helper/workflow change,
verification and temporary disk headroom; it is **not implemented by this PR**.
The current helper's token-stdin interface must not be used for an image archive.

## Activation gates

Resolve the recording limitation or implement/verify the credential-free transport
first. Then obtain separate approval for builds and activation. Run approved CI,
ensure no older matching CI runs are pending, and coordinate the main merge and
fresh feature push; merging this PR is itself an activation change. Verify dev
health, limits, isolated volume, release artifact and unchanged production
metadata. Do not remove either production hold or dispatch production.

This preparation commit uses `[skip ci]` to honor the no-build instruction; no
workflow has been dispatched. Local validation is not a deployment/audit verdict.
