#!/usr/bin/env bash
set -Eeuo pipefail
fail() { echo "$*" >&2; exit 1; }
[[ $# == 2 && ( $1 == dev || $1 == prod ) ]] || fail 'Usage: freshfirst-release dev|prod REGISTRY_IMAGE@sha256:DIGEST'
environment=$1
image=$2
[[ $image =~ ^[a-z0-9-]+-docker\.pkg\.dev/[a-z0-9-]+/[a-z0-9_-]+/[a-z0-9/_-]+@sha256:[a-f0-9]{64}$ ]] || fail 'Invalid immutable image reference'
config=/etc/freshfirst/deploy.conf
[[ -f $config && $(stat -c %u "$config") == 0 && $(stat -c %a "$config") == 600 ]] || fail 'Root-owned mode 0600 deploy.conf required'
source "$config"
[[ ${IMAGE_REPOSITORY:-} =~ ^[a-z0-9-]+-docker\.pkg\.dev/[a-z0-9-]+/[a-z0-9_-]+/[a-z0-9/_-]+$ ]] || fail 'Invalid configured image repository'
[[ $image == "$IMAGE_REPOSITORY"@sha256:* ]] || fail 'Image outside configured repository'
app_dir=/opt/freshfirst
project=freshfirst
env_file=$app_dir/.env
if [[ $environment == dev ]]; then
  project=freshfirst-dev
  env_file=/etc/freshfirst/dev.env
  [[ -f $env_file ]] || fail 'Missing independent dev configuration'
  for key in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD FRESHFIRST_AUTH_SECRET FRESHFIRST_PORT FRESHFIRST_TRUSTED_ORIGINS; do
    [[ $(grep -c "^$key=" "$env_file") == 1 ]] || fail "Dev configuration requires exactly one $key"
  done
  for entry in 'POSTGRES_DB=freshfirst_dev' 'POSTGRES_USER=freshfirst_dev' 'FRESHFIRST_PORT=127.0.0.1:8081' 'FRESHFIRST_TRUSTED_ORIGINS=http://127.0.0.1:8081'; do
    grep -Fxq "$entry" "$env_file" || fail "Dev configuration must contain $entry"
  done
  for key in POSTGRES_PASSWORD FRESHFIRST_AUTH_SECRET; do
    dev_value=$(grep -m1 "^$key=" "$env_file")
    [[ -n ${dev_value#*=} && $dev_value != *REPLACE* ]] || fail 'Replace dev secret placeholders'
    [[ $dev_value != "$(grep -m1 "^$key=" "$app_dir/.env")" ]] || fail 'Dev and production secrets must differ'
  done
fi
[[ -f $env_file && $(stat -c %u "$env_file") == 0 && $(stat -c %a "$env_file") == 600 ]] || fail 'Root-owned mode 0600 environment file required'
[[ -f $app_dir/compose.yaml && -f $app_dir/infra/gcp/compose.image.yaml ]] || fail 'Install reviewed Compose files first'
unset COMPOSE_FILE COMPOSE_PROJECT_NAME POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD FRESHFIRST_AUTH_SECRET FRESHFIRST_PORT FRESHFIRST_TRUSTED_ORIGINS
export FRESHFIRST_IMAGE=$image
compose=(docker compose --project-directory "$app_dir" --project-name "$project" --env-file "$env_file" -f "$app_dir/compose.yaml" -f "$app_dir/infra/gcp/compose.image.yaml")
state=/var/lib/freshfirst-releases/$environment
install -d -m 0700 "$state"
exec 9>"$state/lock"
flock -n 9 || fail 'Another deployment is running for this environment'
db_id=$("${compose[@]}" ps -q db)
[[ -n $db_id && $(docker inspect --format '{{.State.Health.Status}}' "$db_id") == healthy ]] || fail 'Existing healthy environment database required'
previous=$("${compose[@]}" ps -q app)
if [[ -n $previous ]]; then docker inspect --format '{{.Config.Image}}' "$previous" >"$state/previous-image"; fi
credentials=$(mktemp -d)
trap 'rm -f -- "$credentials/config.json"; rmdir -- "$credentials"' EXIT
export DOCKER_CONFIG=$credentials
curl --fail --silent --show-error -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' \
  | docker login --username oauth2accesstoken --password-stdin "https://${IMAGE_REPOSITORY%%/*}" >/dev/null
"${compose[@]}" pull app
printf '%s\n' "$image" >"$state/pending-image"
"${compose[@]}" up -d --no-deps --no-build --pull never app
for attempt in {1..30}; do
  app_id=$("${compose[@]}" ps -q app)
  if [[ -n $app_id && $(docker inspect --format '{{.State.Health.Status}}' "$app_id") == healthy ]]; then
    mv "$state/pending-image" "$state/current-image"
    echo "$environment healthy: $image"
    exit 0
  fi
  sleep 5
done
fail 'Application not healthy; pending-image retained. Roll back explicitly after checking schema compatibility.'
