# Opt-in backend OpenTelemetry

Disabled by default: no SDK providers, exporter threads, database hooks or new
logging handlers are installed unless `FRESHFIRST_TELEMETRY_ENABLED=true`.
No existing deployment workflow or release helper enables it. API contracts,
authentication, inventory transactions and the frontend are unchanged.

## Signals and course terminology

FreshFirst is a pantry/recipe application, with no marketplace listing or
reservation endpoints. Course counters map to existing operations:

| Instrument | Actual meaning |
| --- | --- |
| `freshfirst.listings.created` | Successful `POST /api/pantry` (`createPantryItem`), including existing-item merges; counts requests, not unique rows |
| `freshfirst.reservations.completed` | Successful `POST /api/cooking/confirm` (`confirmCook`), after the transaction returns |
| `freshfirst.reservations.failures` | Non-2xx cooking confirmations, including authentication, validation, stock conflicts and server failures |
| `freshfirst.recipes.requests` | All recipe list/detail GET attempts, including failures; excludes import |
| `freshfirst.http.requests` | All FastAPI HTTP requests by method, route template and status |
| `http.server.request.duration` | Request duration histogram in seconds |

Cooking preview does not complete a reservation. Counters describe observed HTTP
results, not an exactly-once business ledger: a lost response or retry can differ
from durable inventory/history. They never control a transaction.

Manual ASGI instrumentation creates server spans and engine-scoped SQLAlchemy
events create child database spans, including failed queries. Only operation
names (`SELECT`, `INSERT`, etc.) are captured, never SQL text/parameters or database
URLs. JSON request-completion logs on stderr and OTLP logs share trace/span IDs.
Existing arbitrary application/uvicorn logs are **not** forwarded by this exporter.
No raw URLs, query strings, IDs, headers, cookies, bodies, user data, exception
messages/stacks, baggage or host/environment resource detection are exported.
Only W3C `traceparent` is accepted for correlation. Sampling defaults to 10%
(parent-based); metrics and safe request logs cover every request. Providers are
app-local, with bounded 256-entry span/log queues, 60-second metric intervals,
3-second exporter timeouts and lifecycle shutdown. Export may drop data during
outages; request-completion telemetry failures cannot change API responses.

## Minimal local check

Use the SDK's [OTLP HTTP/protobuf exporters](https://opentelemetry.io/docs/languages/python/exporters/).
From the repository root, optionally run the provided debug collector on your
workstation, not the 2 GB VM:

```bash
docker run --rm --memory=128m --cpus=0.25 \
  -p 127.0.0.1:4318:4318 \
  -v "$PWD/infra/observability/collector.yaml:/etc/otelcol/config.yaml:ro" \
  otel/opentelemetry-collector:0.151.0
```

In another terminal, using an isolated development database and the existing
local authentication setup:

```bash
cd backend
FRESHFIRST_TELEMETRY_ENABLED=true \
FRESHFIRST_TELEMETRY_ENVIRONMENT=local \
FRESHFIRST_TELEMETRY_SAMPLE_RATIO=1 \
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318 \
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8001
# Another terminal: curl -fsS http://127.0.0.1:8001/api/ingredients
```

The debug collector acknowledges all three signals; metrics export within 60
seconds or on graceful shutdown. This config prints summaries, not dashboards.
Endpoint is a **base** URL: `/v1/traces`, `/v1/metrics`, `/v1/logs` are appended.
Only `http/protobuf` is supported. Invalid explicit opt-in configuration fails
startup; disabled mode ignores telemetry settings. Signal-specific endpoint,
resource and sampler environment overrides are intentionally not used.
Remote collector endpoints require HTTPS; plain HTTP is limited to loopback.

## Managed dashboards and alerts

For this dev VM, prefer [direct Grafana Cloud OTLP ingestion](https://grafana.com/docs/grafana-cloud/send-data/otlp/send-data-otlp/)
over running Grafana/Prometheus/Loki/Tempo locally. It supports metrics, traces
and logs without a VM service account. Use the stack's OpenTelemetry connection
page to obtain its HTTPS base endpoint and a narrowly scoped write token. Store
the portal's URL-encoded OTLP header value only in the private DEV file described
in [the DEV activation runbook](DEV-ACTIVATION.md). Do not put the token in an
`OTEL_EXPORTER_OTLP_HEADERS` environment variable or in `dev.env`: Docker inspect
exposes container environment values. The application reads
`FRESHFIRST_TELEMETRY_HEADERS_FILE` and passes parsed headers directly to all
three exporters without copying credentials into its environment. Generic and
signal-specific SDK header environment variables are rejected before providers
start; remote dev export requires the file. The file option is rejected for
production/test/local telemetry environments. Local loopback collectors may run
without headers.

The optional `compose.telemetry.yaml` mounts only
`/etc/freshfirst/dev-secrets/otlp-headers` as a read-only file-backed Compose secret
and explicitly enables dev instrumentation. It is not loaded by ordinary archive
releases. The default dev overlay forces telemetry off, so a subsequent ordinary
release disables it. Never load the telemetry overlay for production. Production
holds, release helpers, database configuration and resource limits are unchanged.

The activation runbook contains the complete nonsecret environment table,
root/group file permissions for app UID/GID 10001, later operator-only commands
and live verification procedure. No secret file, deployment, infrastructure or
GitHub Actions secret operation was performed while preparing these files.

With no attached VM service account, telemetry can still use the managed token.
Dev image pulls are now prepared to use the deployer's short-lived OIDC token
over SSH stdin; complete the separate [release prerequisites](../gcp/MILESTONE1.md#short-lived-dev-registry-authentication)
before enabling GCP. Production's existing metadata-token prerequisite is unchanged.

In hosted Grafana, use Explore's managed Prometheus, Tempo and Loki sources.
Find `service.name=freshfirst-api`, inspect a trace with database child spans,
and open its request log by trace ID. Backend normalization commonly exposes
these PromQL names; verify the actual names/`job` label in Explore first:

```promql
sum(rate(freshfirst_http_requests_total{job="freshfirst-api"}[5m]))
sum(increase(freshfirst_listings_created_total{job="freshfirst-api"}[1h]))
sum(increase(freshfirst_reservations_completed_total{job="freshfirst-api"}[1h]))
sum(increase(freshfirst_reservations_failures_total{job="freshfirst-api"}[10m]))
sum(rate(freshfirst_recipes_requests_total{job="freshfirst-api"}[5m]))
histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{job="freshfirst-api"}[5m])))
```

Import [dashboard.json](dashboard.json) through Grafana dashboard import and select
the dev Metrics and Logs datasources for `DS_METRICS` and `DS_LOGS`. Its eight
panels include request rate, 5xx fraction (zero when no 5xx series exists), p95,
four business counters and safe request logs; all queries filter dev. Verify
metric normalization and Loki structured metadata in Explore before relying on
the panels. Trace links require operator-configured Loki derived fields targeting
the Tempo datasource using the emitted `trace_id`.

Operational alerts are manual follow-up configuration, not provisioned by the
demo rule. Through Grafana Alerting, configure:
reservation failures >=3 in 10 minutes (warning; may be expected stock/validation
failures), HTTP 5xx rate >5% for 5 minutes with at least 20 requests in the window,
p95 latency >1 second for 5 minutes, and no request metric for 5 minutes (telemetry
silence, not proof the app is down). Match the actual status-code label in Explore,
usually `http_response_status_code`. Add a contact point and send a test
notification only with approval. Provisioning hosted dashboards, tokens, alerts
and notification recipients is an operator action, not performed by these files.


## Paused traffic demonstration alert

[alert-rule.json](alert-rule.json) is a single Grafana alert provisioning API
object, not a full provisioning-file document. Replace `REPLACE_DEV_FOLDER_UID`
and `REPLACE_METRICS_UID` with identifiers from the dev stack. It is **paused**,
labelled `freshfirst_environment=dev`, and fires on more than 20 harmless
`GET /api/ingredients` requests in five minutes. No-data is OK; this demonstrates
notification plumbing, not application failure detection. Keep it paused until
an operator separately approves importing/enabling it and configuring a contact
point. No alert, contact point or test notification has been created by this work.

## Read-only AI on-call responder

[oncall.py](oncall.py) is a separate FastAPI app for a workstation or separately
approved responder host. It never runs on the constrained application VM and has
no shell, deployment, database or remediation tools. It accepts only authenticated
`FreshFirstDevTrafficDemo` or `FreshFirstDevErrors` dev alerts at `POST /alerts`.
It performs three fixed dev Prometheus queries and one dev Loki query through the
configured Grafana datasource proxy, strips logs to method/status/duration/trace
ID, and asks the configured AI provider for a diagnostic summary. Alert URLs,
annotations, raw logs and arbitrary instructions are not forwarded. AI output
is untrusted advice requiring human review.

Configure these values privately on the responder host, never in Git or terminal
transcripts:

```dotenv
ONCALL_WEBHOOK_TOKEN=REPLACE_WITH_RANDOM_DEDICATED_TOKEN_AT_LEAST_32_CHARACTERS
GRAFANA_URL=https://YOUR-STACK.grafana.net
GRAFANA_READ_TOKEN=REPLACE_WITH_READ_ONLY_DATASOURCE_QUERY_TOKEN
GRAFANA_METRICS_UID=REPLACE_DEV_METRICS_UID
GRAFANA_LOGS_UID=REPLACE_DEV_LOGS_UID
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_API_KEY=REPLACE_PRIVATELY
AI_MODEL=REPLACE_WITH_AVAILABLE_PROVIDER_MODEL
```

The other supported AI base is `https://api.openai.com/v1`. Choose a model
available to that account; no model availability or paid quota is assumed.
The Grafana token needs query permission on only the selected dev datasources
and the stack's datasource proxy, not editor/admin or telemetry-write permissions.
Use a dedicated AI key with a provider spending limit. The OTLP ingestion token
is separate and must not be reused as a Grafana read token.

For a later operator-run foreground session, after loading those private values:

```bash
cd backend
uv run --locked uvicorn oncall:create_app --factory --app-dir ../infra/observability --host 127.0.0.1 --port 8010
```

The webhook uses `Authorization: Bearer <ONCALL_WEBHOOK_TOKEN>`; authenticated
`GET /incidents/{incident_id}` retrieves the returned summary and bounded context.
`GET /healthz` exposes only mode/status. A hosted Grafana webhook cannot reach
loopback: a separately approved HTTPS ingress with access controls is required
for real delivery. None is installed here. Do not expose the workstation port
publicly or put tokens in URL parameters. A contact-point test must use an
allowlisted alert name and dev label; generic `TestAlert` notifications are rejected.

The process deduplicates each alert-name set for ten minutes and permits five
AI attempts per rolling hour. Limits and at most 20 retained reports are in
memory, reset on restart, and require a single worker; they are not a durable
incident system. Reports for the same alert-name set replace prior reports.
Each upstream request has an eight-second HTTP timeout and bounded response
reads. Missing Grafana context is marked; AI failure produces a safe manual
fallback without exposing provider errors. Failed attempts consume budget and
are deduplicated. No automatic notification or remediation follows a summary.

## Recovery validation and integration status

Dashboard, paused alert, responder and dev opt-in wiring are implemented as local
code/configuration. `backend/tests/test_oncall.py` uses `httpx.MockTransport`:
Grafana queries, alert delivery and AI summaries are **simulated**, with no live
provider calls. Selected telemetry checks use in-memory SDK exporters and an
isolated test database; they do not prove managed ingestion or dashboards work.

Do not run the full suite during this recovery. In particular, exclude
`test_otlp_http_exports_all_signals_to_configured_collector` and
`test_exporter_outages_do_not_change_responses` in `test_telemetry.py`; they create
real exporter/scheduler activity and are intentionally unverified after the
reported Windows/VS Code stall. Run only explicitly selected responder and
in-memory telemetry tests, with an external process-tree timeout of 30 seconds.
The ordinary unbounded `uv run pytest` command is unsuitable for this recovery.

Live OTLP ingestion, dashboard import, alert evaluation, notification delivery,
AI provider access and trace links require credentials and manual verification.
No deployment, infrastructure operation, notification or live AI request was
performed. Production holds and dev isolation remain unchanged. The next manual
step is reviewing the PR; after approval and separate activation authorization,
configure the private dev credentials and verify datasource names in Explore
before importing the dashboard or enabling the paused demonstration.
