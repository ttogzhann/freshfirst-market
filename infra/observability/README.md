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
`OTEL_EXPORTER_OTLP_HEADERS` (the portal's URL-encoded authorization value) only
in a private root-owned `0600` env file; never source/print it in CI, commit it or
place credentials in the endpoint URL. Direct ingestion is a dev/quickstart
tradeoff; a remote collector can add buffering without consuming this VM's RAM.

Set these additional values in the private **dev** environment file:

```dotenv
FRESHFIRST_TELEMETRY_ENVIRONMENT=dev
FRESHFIRST_TELEMETRY_SAMPLE_RATIO=0.1
OTEL_EXPORTER_OTLP_ENDPOINT=https://YOUR-STACK-OTLP-GATEWAY/otlp
OTEL_EXPORTER_OTLP_HEADERS=REPLACE_PRIVATELY_WITH_PORTAL_VALUE
```

The separate `compose.telemetry.yaml` explicitly enables instrumentation and
passes these values into the app container. For a later approved dev-only
operation, append it to the existing reviewed image/dev Compose configuration:

```bash
sudo docker compose --project-directory /opt/freshfirst \
  --project-name freshfirst-dev --env-file /etc/freshfirst/dev.env \
  -f /opt/freshfirst/compose.yaml \
  -f /opt/freshfirst/infra/gcp/compose.image.yaml \
  -f /opt/freshfirst/infra/gcp/compose.dev.yaml \
  -f /opt/freshfirst/infra/observability/compose.telemetry.yaml config --quiet
```

Supply the approved `FRESHFIRST_IMAGE` digest through the env file for this manual
Compose command. Do not print the rendered config because it contains secrets.
After separate deployment approval, the same command with `up -d --no-deps
--no-build --pull never app` instead of `config --quiet` recreates only dev app.
The existing release helper does not load the telemetry overlay: a subsequent
normal release disables telemetry again. Before persistent activation, separately
review adding this overlay to **dev only** in that helper. Production stays off;
no GCP deployment hold or GitHub environment setting is changed here.

With no attached VM service account, telemetry can still use the managed token,
but the current GCP release helper's metadata-token Artifact Registry login cannot
work. Resolve that separate runtime image-pull identity prerequisite with explicit
approval before enabling the GCP pipeline; telemetry does not resolve it.

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

Create a dashboard with these six panels. Through Grafana Alerting, configure:
reservation failures >=3 in 10 minutes (warning; may be expected stock/validation
failures), HTTP 5xx rate >5% for 5 minutes with at least 20 requests in the window,
p95 latency >1 second for 5 minutes, and no request metric for 5 minutes (telemetry
silence, not proof the app is down). Match the actual status-code label in Explore,
usually `http_response_status_code`. Add a contact point and send a test
notification only with approval. Provisioning hosted dashboards, tokens, alerts
and notification recipients is an operator action, not performed by these files.
