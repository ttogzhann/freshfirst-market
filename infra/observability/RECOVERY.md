# Part 4 recovery evidence ? 2026-11-17

Scope: preserve the interrupted observability work; complete local dashboard,
paused demonstration alert, read-only responder and setup documentation. No
application deployment, infrastructure operation or live integration call.
Original session effort and aggregate ledger are unknown.

## Focused validation

Commands ran from `backend/` through the existing uv executable at
`C:/Users/User/AppData/Roaming/Python/Python312/Scripts/uv.exe`, with
`UV_OFFLINE=true`, `UV_CACHE_DIR` set to worktree-local `backend/.uv-cache` and
`--locked --no-sync`. No dependency or lockfile updates were made.
A separate Python parent used `Popen.communicate(timeout=30)` for pytest and
`subprocess.run(timeout=15)` for Ruff. On pytest timeout the wrapper would call
`taskkill /PID <pid> /T /F` to terminate its process tree. No timeout occurred.

```text
uv run --locked --no-sync pytest -q tests/test_oncall.py tests/test_telemetry.py::test_disabled_by_default_does_not_configure_exporters tests/test_telemetry.py::test_real_routes_counters_trace_log_privacy_and_cleanup
```

**BLOCKED, exit 4 before collection:** FastAPI/Pydantic import failed because the
existing virtual environment has no `METADATA` in
`email_validator-2.3.0.dist-info`; `importlib.metadata.version('email-validator')`
returns `None`, causing `AttributeError` in Pydantic. No test passed or failed at
execution; no exporter scheduler started. Do not interpret implemented mock tests
as executed evidence. Environment repair is required before repeating this same
focused command with a 30-second process-tree timeout.

```text
uv run --locked --no-sync ruff check app/telemetry.py tests/test_oncall.py ../infra/observability/oncall.py
uv run --locked --no-sync ruff format --check app/telemetry.py tests/test_oncall.py ../infra/observability/oncall.py
```

Both passed after correcting inherited long lines and formatting; three Python
files were checked. Standard-library JSON parsing passed for `dashboard.json`
and `alert-rule.json`; `git diff --check` passed (10-second subprocess timeout).
The 5xx panel/query now returns zero when no error series exists instead of an
empty numerator. Live metric names and Loki metadata remain unverified.

Intentionally not run: full backend/frontend suites, exporter collector test
`test_otlp_http_exports_all_signals_to_configured_collector`, exporter outage test
`test_exporter_outages_do_not_change_responses`, any service/background process,
Docker/Compose runtime, dashboard provisioning, alert delivery or paid AI call.
The reported prior scheduler stall was not reproduced or diagnosed by this work.

## Delivery and review

PM accepted local recovery scope in a separate context (AC-01 through AC-06).
Independent QA must review the committed candidate; engineering checks are not
QA PASS. Leave issues open and keep the PR draft while runtime checks remain
blocked. Existing root preservation/recovery directories and unrelated untracked
files are untouched. Production holds, deployment workflows and dev resource,
port and database isolation are unchanged. Existing dev Compose edits only
propagate explicit opt-in settings, defaulting instrumentation to disabled.

Publishing is currently blocked independently by GitHub CLI authentication
(HTTP 401) and Git HTTPS credential initialization. No PR link is claimed.
Next manual steps: restore GitHub authentication, repair the local locked uv
environment, repeat only the focused timeout-bounded checks, obtain independent
QA and review the draft PR. Credential-backed Grafana/AI setup and live activation
remain separate, operator-authorized work described in [README.md](README.md).
