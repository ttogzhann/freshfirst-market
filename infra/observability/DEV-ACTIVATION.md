# DEV Grafana activation preparation

This is a manual runbook for a later, separately authorized DEV operation.
Preparation does not deploy an image, install a secret, contact GCP/Grafana,
change infrastructure or GitHub secrets, or enable an alert. Production holds,
the archive release helper, stdin image transfer, database volumes and dev
resource/loopback port limits remain unchanged. The image used later must contain
the reviewed header-file implementation. The earlier Part 4 image at `4a3a34a`
does not read this file option and must not be used for this activation. A new
approved archive-delivered image containing the loader commit is a prerequisite.

## Configuration boundary

Obtain the DEV stack's OTLP HTTPS base endpoint, instance identity and narrowly
scoped ingest token from its OpenTelemetry connection page. Grant only the
needed metrics/logs/traces write scopes. Do not reuse production credentials or
the responder's Grafana datasource read token. No VM service account is needed.

| Setting | Location | Value / treatment |
| --- | --- | --- |
| `FRESHFIRST_IMAGE` | Existing private `/etc/freshfirst/dev.env` | Approved immutable image digest containing this code; existing release prerequisites still apply |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Same DEV env file | DEV stack HTTPS base URL, including `/otlp` if supplied; no credentials or query string |
| `FRESHFIRST_TELEMETRY_SAMPLE_RATIO` | Same DEV env file | `1` temporarily for verification, then `0.1` |
| `FRESHFIRST_TELEMETRY_ENABLED` | Compose overlays only | Default dev overlay hardcodes `false`; optional telemetry overlay overrides `true` |
| `FRESHFIRST_TELEMETRY_ENVIRONMENT` | Telemetry overlay | Fixed `dev` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Telemetry overlay | Fixed `http/protobuf` |
| `FRESHFIRST_TELEMETRY_HEADERS_FILE` | Telemetry overlay | `/run/secrets/freshfirst_otlp_headers`; custom FreshFirst file extension, not a standard SDK variable |
| URL-encoded OTLP headers | Host `/etc/freshfirst/dev-secrets/otlp-headers` only | Secret content, never environment/argv/log output; mounted read-only at the path above |

Never set `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_TRACES_HEADERS`,
`OTEL_EXPORTER_OTLP_METRICS_HEADERS` or `OTEL_EXPORTER_OTLP_LOGS_HEADERS` in the
container, even to empty strings. All are rejected to prevent SDK ambient-header
merging. Do not source a credential-bearing portal shell snippet. Copy only its
URL-encoded header value, for example the *shape*
`Authorization=Basic%20ENCODED_VALUE`, without surrounding quotes, `export`, a
variable name or a trailing shell command. Percent-encoded characters are decoded
once; `+` remains `+`. Header pairs are comma-separated; duplicate names, malformed
escapes, control characters, non-ASCII bytes and files over 8192 bytes are rejected.
One terminal LF is accepted. Missing/unreadable/invalid files fail before exporter
providers or scheduler threads start. Error messages never include file content.

## Later manual secret installation

First obtain separate authorization and an approved privileged DEV host session.
Use a trusted terminal with input/session recording disabled. The following
Linux commands are supplied for operator review only; they have not run here.
They prompt through `/dev/tty` with echo disabled and never put secret material
in shell variables, exported environment, SSH arguments or command history.
An existing file is deliberately not overwritten. Do not reuse the release
helper's stdin: that stream contains the image archive.

```bash
sudo install -d -o root -g 10001 -m 0710 /etc/freshfirst/dev-secrets
sudo python3 - <<'PY'
import os
import termios

tty = os.open('/dev/tty', os.O_RDWR)
saved = termios.tcgetattr(tty)
hidden = termios.tcgetattr(tty)
hidden[3] &= ~termios.ECHO
try:
    termios.tcsetattr(tty, termios.TCSAFLUSH, hidden)
    os.write(tty, b'Paste DEV URL-encoded OTLP header value, then Enter: ')
    value = os.read(tty, 8193).removesuffix(b'\n')
finally:
    termios.tcsetattr(tty, termios.TCSAFLUSH, saved)
    os.write(tty, b'\n')
    os.close(tty)
if not value or len(value) > 8192 or any(c < 33 or c > 126 for c in value):
    raise SystemExit('Invalid header format; nothing installed')
path = '/etc/freshfirst/dev-secrets/otlp-headers'
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o440)
try:
    os.fchown(fd, 0, 10001)
    os.fchmod(fd, 0o440)
    with os.fdopen(fd, 'wb', closefd=False) as output:
        output.write(value + b'\n')
        output.flush()
        os.fsync(fd)
finally:
    os.close(fd)
PY
sudo stat -c '%U:%g %a %n' /etc/freshfirst/dev-secrets /etc/freshfirst/dev-secrets/otlp-headers
```

Expected metadata: directory `root:10001 710`, file `root:10001 440`. Never `cat`
the file, print a rendered Compose configuration, capture it in screenshots, or
copy it into the checkout. App UID/GID is `10001:10001`; `0600 root:root` would
prevent it from reading the secret. Local Compose file-backed secrets use
read-only bind mounts and ignore requested `uid`/`gid`/`mode`, so **host** ownership
and permissions are required. They are not encrypted secrets storage. Docker
inspect shows a source/target path and env file path, not the header value;
privileged host/Docker administrators and the running app can read the file.
Restrict host access and rotate the token if exposure is suspected.

For later approved rotation, mint a replacement with the same limited DEV write
scopes. Run the hidden-input installer above with its static `path` changed to
`/etc/freshfirst/dev-secrets/otlp-headers.next`; inspect only its ownership/mode.
Then replace the host file using
`sudo mv -T -- /etc/freshfirst/dev-secrets/otlp-headers.next /etc/freshfirst/dev-secrets/otlp-headers`.
Recreate only the DEV app with the explicit overlay command below, adding
`--force-recreate`, so it mounts the new file and reloads the credentials. An
atomic rename alone leaves an existing bind mount on the old inode. Verify all
three signals before revoking the old token; do not leave the old token active
after successful verification. No rotation or revocation has been performed.

GitHub Actions environment secrets are not used by this design. No workflow
uploads or env-to-file secret conversion is added. If Actions-based delivery is
requested later, review a dedicated protected DEV environment and separate
encrypted stdin transfer that cannot mix with the archive stream; never pass a
secret in SSH argv or an exported container environment variable.

## Later explicit DEV activation and verification

After separate deployment approval, install the reviewed Compose files and image
using the existing approved archive process. The digest must already be imported
locally: `--pull never` will not fetch it. Use
`sudoedit /etc/freshfirst/dev.env` to set only the nonsecret DEV endpoint,
temporary sample ratio `1` and approved image digest from the table above.
Preserve existing database/authentication values and add no header variables.
Then, in a privileged Bash DEV session:

```bash
compose=(sudo docker compose --project-directory /opt/freshfirst
  --project-name freshfirst-dev --env-file /etc/freshfirst/dev.env
  -f /opt/freshfirst/compose.yaml
  -f /opt/freshfirst/infra/gcp/compose.image.yaml
  -f /opt/freshfirst/infra/gcp/compose.dev.yaml
  -f /opt/freshfirst/infra/observability/compose.telemetry.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" up -d --no-deps --no-build --pull never app
```

Keep the existing private dev.env database/auth settings unchanged. Missing secret
files must block configuration/startup; do not substitute an environment token.
The commands target only `freshfirst-dev` app; no database recreation, production
container or infrastructure change is authorized by this runbook. An ordinary
archive release does not include the telemetry overlay and turns telemetry off.
Do not modify that helper to persist telemetry implicitly.

With sample ratio `1`, send a few harmless requests from the DEV host:

```bash
curl --fail --silent --show-error http://127.0.0.1:8081/api/ingredients >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8081/api/ingredients >/dev/null
```

In the DEV Grafana stack, allow at least one 60-second metric export interval
plus ingestion delay, then check all three signals in Explore:

1. Metrics: `freshfirst_http_requests_total{freshfirst_environment="dev"}`
   increases for `/api/ingredients`; check the duration histogram and actual
   normalized label names. An absent series is not a successful check.
2. Logs: find service `freshfirst-api`, filter `freshfirst_environment="dev"`,
   and inspect a safe `http.request.completed` event for that route. Record its
   `trace_id`/`span_id` (not a token or user payload). Confirm no query/body/header
   content is present. This verifies logs, not only container stderr output.
3. Traces: search Tempo for the recorded `trace_id`; verify the matching
   `GET /api/ingredients` server span and database child span. Existing parent
   trace context can affect parent-based sampling; the curl examples send none.

If ingestion fails, inspect generic exporter status without dumping request
headers or credentials; verify the private token/endpoint/scopes with the operator.
Do not retry by exposing the token or weakening TLS. After a successful check,
restore sample ratio `0.1` and recreate only the DEV app with the same reviewed
overlay command. Returning to the ordinary dev Compose stack disables telemetry.
Leave the traffic demonstration alert paused; no webhook or AI service activation
is part of this operation. Dashboard import and live alerts require separate review.

## Prepared-code validation versus live evidence

The focused header-file tests stub all exporter/provider/processor constructors:
they validate fail-closed parsing and explicit headers without network, real
exporters, scheduler threads or credentials. Existing responder tests mock
Grafana/AI; in-memory telemetry tests use an isolated database. These checks do
not prove live ingestion or authorize any command above.

Run only the selected tests below from `backend/`, with a separate supervisor
enforcing a 30-second timeout and killing the entire process tree on expiry:

```text
uv run --locked --no-sync pytest -q tests/test_telemetry_headers.py tests/test_oncall.py tests/test_telemetry.py::test_disabled_by_default_does_not_configure_exporters tests/test_telemetry.py::test_real_routes_counters_trace_log_privacy_and_cleanup
```

Do not run the full suite, the real collector test
`test_otlp_http_exports_all_signals_to_configured_collector` or the real exporter
outage test `test_exporter_outages_do_not_change_responses` during this preparation.
No live ingestion, credential installation or deployment result is claimed here.
