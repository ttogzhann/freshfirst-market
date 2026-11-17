# Explicit manual DEV release with focused validation

The `gcp.yml` manual `deploy_dev` mode is a separate, auditable DEV-only path.
The workflow must execute from `main`; `source_sha` must be a full lowercase
40-character commit reachable from `origin/main`. Control tools are pinned to
the workflow's exact main `github.sha`; the image source is the admitted SHA.
No application history is merged by this workflow or these documentation files.

Current preparation blocker: `origin/main` at `26e8d14` lacks the reviewed DEV
Compose overlay and telemetry tests. The application merge `15a71fe` belongs to
`feature/render-deployment`, not main. Under this strict main-source policy it
cannot be dispatched as source. Do not deliberately spend the authorized run on
a known failing source; obtain a separately approved source-policy decision or
reviewed main integration first. An eligible main commit must also contain the
reviewed source files and focused tests. Branch names and short SHAs are rejected.

## Admission before any cloud credential or build

Manual mode requires `deploy_dev=true` and all `preflight`,
`publish_test_image`, and `deploy` inputs false; leave `dev_run_id` and `digest`
empty. Conflicting modes fail in the credential-free admission job and cannot
start the OIDC preflight/test publisher. Source and control ancestry are checked
before source validation, dependencies, cloud authentication or Docker builds.

The manual admission job has only repository-read permission and no GCP
environment or OIDC permission. It runs these explicit focused checks:

```text
python3 -m unittest discover -s .deployment-tools/infra/gcp -p test_manual_dev_policy.py
python3 .deployment-tools/infra/gcp/manual-dev-policy.py source .source
uv run --locked --no-sync pytest -q tests/test_telemetry_headers.py tests/test_oncall.py tests/test_telemetry.py::test_disabled_by_default_does_not_configure_exporters tests/test_telemetry.py::test_real_routes_counters_trace_log_privacy_and_cleanup
```

Each check/test command uses `timeout --signal=KILL 30s` on the runner, killing
the process group at the deadline. Dependencies use pinned uv `0.13.3`, the
source's existing locked environment and finite installation timeouts. No full
backend/frontend suite or real exporter collector/outage test is selected. The
source Compose plan is rendered with synthetic credentials only and must leave
telemetry disabled, with no credential environment entries or secret mounts.

`manual-focused-gate` retains a JSON record and JUnit output with exact
source/control/run identifiers, allowlisted tests, executed count and pass status.
At least the 42 selected telemetry/responder cases must execute without skips,
errors or failures. The separate policy suite protects modes, ancestry, workflow
ordering and synthetic read-only host checks. This is **focused validation**, not
a full CI PASS; mocked provider responses do not prove managed integrations.

## Existing DEV archive path and holds

Only successful admission permits the existing `build-dev` job to obtain OIDC,
build/tag the immutable source image, validate its digest and config/layers, and
stream the verified image archive through the existing SSH/stdin helper. It
retains the existing development environment approval, shared DEV concurrency,
resource/headroom checks, isolated database/volume checks, loopback health check,
and before/after production health and metadata snapshots. It never installs
host Compose files or changes helper/sudo policy. Host files may differ from the
source only if their rendered ordinary DEV plan remains disabled and safe.

Additional manual-only read-only host gates verify the planned ordinary DEV
Compose configuration before transfer and after release. Private configuration
is piped directly to the policy parser and is never logged or retained. The
running DEV app is inspected only through booleans derived from selected
telemetry environment names and mount destinations. Telemetry must remain off,
without header environment values or OTLP secret mounts. No OTLP headers,
secret files, dashboard imports or alerts are configured by this path.

If existing host configuration can enable telemetry, a secret mount exists,
passwordless read-only checks are unavailable, or any check fails, stop. Do not
edit host files, broaden sudo, repair credentials, retry the workflow, reset a
database, remove images globally or bypass the snapshot comparison. Later repairs
require separate authorization. There is no automatic retry or rollback here.

Successful manual releases upload `manual-focused-dev-release`, not the automatic
`healthy-dev-release` artifact. Their metadata declares `manual-focused`,
`full_ci_passed=false`, null `ci_run_id`, and the exact focused/control/source/run
and image/archive identifiers. The existing production promotion verifier cannot
interpret it as a successful full-CI release. Production promotion and Render
deployment remain held. The automatic successful-push `workflow_run` path keeps
its prior CI prerequisite and ordinary artifact/CI-run identity.

## Later single authorized dispatch

After reviewing and merging only the workflow/control change into main, resolve
the source blocker above, independently verify the exact eligible SHA and obtain
the applicable DEV operation approval. Then dispatch `gcp.yml` on `main` with
only `deploy_dev=true`, the exact source SHA and all other modes false. Do not
dispatch `render.yml`: that starts broad suites. Watch the one approved run,
report its gate/build/deployment state and artifacts, and stop on its first
failure. No run has been dispatched by preparing this implementation.

Local engineering validation uses only the eight new policy/synthetic-host
cases, actionlint on the changed workflow, Python lint/format, Bash syntax and
diff checks. The main-source telemetry gate remains blocked by missing source
files; local policy success is not a claim that a live image was built or deployed.
