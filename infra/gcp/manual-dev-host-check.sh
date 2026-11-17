#!/usr/bin/env bash
# Read-only manual DEV gate. Policy text is public pinned-control source, not a credential.
set +x
set -euo pipefail
[[ $# == 2 && ( $1 == before || $1 == after ) && $2 =~ ^[A-Za-z0-9+/=]+$ ]]
policy=$(printf '%s' "$2" | base64 --decode)
# Render private configuration only into the policy parser, never logs/artifacts.
# The second env file overrides only a nonsecret image placeholder for validation.
printf 'FRESHFIRST_IMAGE=local/validation@sha256:%064d\n' 0 \
  | sudo -n docker compose --project-directory /opt/freshfirst \
      --project-name freshfirst-dev --env-file /etc/freshfirst/dev.env --env-file /dev/stdin \
      -f /opt/freshfirst/compose.yaml -f /opt/freshfirst/infra/gcp/compose.image.yaml \
      -f /opt/freshfirst/infra/gcp/compose.dev.yaml config --format json \
  | python3 -c "$policy" plan
if [[ $1 == after ]]; then
  app=$(sudo -n docker ps -q --filter label=com.docker.compose.project=freshfirst-dev --filter label=com.docker.compose.service=app)
  [[ -n $app && $app != *$'\n'* ]]
  # Emit only booleans for selected settings, never credential values or full env.
  safety=$(sudo -n docker inspect --format '{{range .Config.Env}}{{$key := index (split . "=") 0}}{{if eq $key "FRESHFIRST_TELEMETRY_ENABLED"}}{{if ne . "FRESHFIRST_TELEMETRY_ENABLED=false"}}unsafe{{end}}{{else if or (eq $key "FRESHFIRST_TELEMETRY_HEADERS_FILE") (eq $key "OTEL_EXPORTER_OTLP_HEADERS") (eq $key "OTEL_EXPORTER_OTLP_TRACES_HEADERS") (eq $key "OTEL_EXPORTER_OTLP_METRICS_HEADERS") (eq $key "OTEL_EXPORTER_OTLP_LOGS_HEADERS")}}unsafe{{end}}{{end}}' "$app")
  [[ -z $safety ]]
  mounts=$(sudo -n docker inspect --format '{{range .Mounts}}{{println .Destination}}{{end}}' "$app")
  [[ $mounts != *'/run/secrets'* && $mounts != *otlp* ]]
fi
printf 'Manual DEV telemetry-disabled plan/runtime check passed.\n' >&2
