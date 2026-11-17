# Manual import-test image publication (not executed)

The existing `gcp.yml` gains a manual-only `publish-import-test-image` job on
`main`, using `gcp-development` and the existing keyless OIDC deployer. No new
workflow identity, IAM grant, VM action or deployment is introduced. Dev and both
production jobs remain explicitly held. Publication and SSH preflight flags are
mutually exclusive; setting both runs neither job.

Source: Docker Official BusyBox 1.37.0's linux/amd64 manifest, pinned to
`sha256:66a6306db78bf2dbf3487f293aa8d6990d8e506fdffab9cc43fe422becf886e4`.
The [Docker Hub tag metadata](https://hub.docker.com/v2/repositories/library/busybox/tags/1.37.0)
reports 2,211,514 compressed bytes; this is not
proof of Docker archive size. The job pulls, checks platform, saves by content
image ID and requires the actual untagged archive to be **under 64 MiB before
publishing**. It never builds FreshFirst or executes the image.

Only after that check, OIDC authenticates to the configured existing Artifact
Registry. The image is retagged as
`GCP_IMAGE_REPOSITORY:import-test-RUN_ID-RUN_ATTEMPT`, without replacing release
tags. After push, the exact registry digest is resolved from Docker RepoDigests,
pulled again by digest and required to match the source image ID.

`gcp-import-test-image` contains only `import-test-image.json`: immutable target
and source references, image ID, platform, actual archive size/SHA-256 and run/
source provenance. Archive bytes and credential files are not uploaded. The
temporary archive is deleted and OIDC credentials are cleaned up on the runner.
No credentials or image bytes are sent to the VM. Future exports must recheck
their own size/checksum; Docker archive bytes can vary by exporter version.

## Activation requires separate approval

1. Review and merge this PR; retain all deployment holds and blocked draft PR #98.
2. Separately approve publishing one test image, then dispatch only this job:

   ```bash
   gh workflow run gcp.yml --repo ttogzhann/freshfirst-market --ref main \
     -f publish_test_image=true -f preflight=false -f deploy=false
   ```

3. Require success and download `gcp-import-test-image`. Review/approve its exact
   `image` digest for the separate PR #99 import-only host procedure. That host
   test still needs separate installation/test approval and expanded-size/RAM/
   disk checks. No VM test, dev activation or production promotion follows
   automatically from publication.

Failure after push can leave the small test tag without a completed artifact;
do not treat it as approved evidence or automatically retry/delete registry data.
No long-lived service-account key is used. No image has been published by this PR.
