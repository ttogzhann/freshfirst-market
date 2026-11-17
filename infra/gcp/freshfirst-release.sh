#!/usr/bin/env bash
set +x # Tokens must never enter shell tracing, including bash -x invocations.
set -Eeuo pipefail
fail() { echo "$*" >&2; exit 1; }
[[ $# == 6 && $1 == dev && ( $3 == --image-archive-stdin || $3 == --verify-image-archive-stdin ) ]] || fail 'Usage: freshfirst-release-dev-archive dev IMAGE@sha256:DIGEST --image-archive-stdin|--verify-image-archive-stdin ARCHIVE_SHA256 SIZE IMAGE_ID'
environment=$1
image=$2
[[ $image =~ ^[a-z0-9-]+-docker\.pkg\.dev/[a-z0-9-]+/[a-z0-9_-]+/[a-z0-9/_-]+@sha256:[a-f0-9]{64}$ ]] || fail 'Invalid immutable image reference'
if [[ $environment == dev ]]; then
  archive_sha=$4
  archive_size=$5
  image_id=$6
  [[ $archive_sha =~ ^[a-f0-9]{64}$ && $image_id =~ ^sha256:[a-f0-9]{64}$ ]] || fail 'Invalid image archive hashes'
  [[ $archive_size =~ ^[1-9][0-9]{0,9}$ && $archive_size -le 1073741824 ]] || fail 'Invalid image archive size'
  LC_ALL=C IFS= read -r -t 10 -N 1 archive_prefix || fail 'Missing image archive on stdin'
fi
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
    # Dev secrets are independently generated at installation; never read production .env.
  done
fi
[[ -f $env_file && $(stat -c %u "$env_file") == 0 && $(stat -c %a "$env_file") == 600 ]] || fail 'Root-owned mode 0600 environment file required'
[[ -f $app_dir/compose.yaml && -f $app_dir/infra/gcp/compose.image.yaml ]] || fail 'Install reviewed Compose files first'
unset COMPOSE_FILE COMPOSE_PROJECT_NAME POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD FRESHFIRST_AUTH_SECRET FRESHFIRST_PORT FRESHFIRST_TRUSTED_ORIGINS
export FRESHFIRST_IMAGE=$image
compose=(docker compose --project-directory "$app_dir" --project-name "$project" --env-file "$env_file" -f "$app_dir/compose.yaml" -f "$app_dir/infra/gcp/compose.image.yaml")
if [[ $environment == dev ]]; then
  [[ -f $app_dir/infra/gcp/compose.dev.yaml ]] || fail 'Install reviewed dev resource overlay first'
  compose+=(-f "$app_dir/infra/gcp/compose.dev.yaml")
fi
state=/var/lib/freshfirst-releases/$environment
install -d -m 0700 "$state"
exec 9>"$state/lock"
flock -n 9 || fail 'Another deployment is running for this environment'
db_id=$("${compose[@]}" ps -q db)
[[ -n $db_id && $(docker inspect --format '{{.State.Health.Status}}' "$db_id") == healthy ]] || fail 'Existing healthy environment database required'
umask 077
transfer=
cleanup_transfer() {
  if [[ -n $transfer ]]; then
    rm -f -- "$transfer/image.tar"
    rmdir -- "$transfer"
    transfer=
  fi
}
trap cleanup_transfer EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ $environment == dev ]]; then
  verifier=/usr/local/lib/freshfirst-dev-archive/verify-image-archive.py
  expanded_limit=1073741824
  if [[ $3 == --verify-image-archive-stdin ]]; then
    [[ $archive_size -le 67108864 ]] || fail 'Import-only test archive exceeds 64 MiB'
    available_kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    [[ $available_kb =~ ^[0-9]+$ && $available_kb -ge 524288 ]] || fail 'Import-only test requires 512 MiB available RAM'
    expanded_limit=67108864
  fi
  [[ -f $verifier && $(stat -c %u "$verifier") == 0 && $(stat -c %a "$verifier") == 644 ]] || fail 'Install root-owned mode 0644 image verifier first'
  available=$(df -PB1 "$state" | awk 'NR==2 {print $4}')
  [[ $available =~ ^[0-9]+$ && $available -ge $((3 * archive_size + 536870912)) ]] || fail 'Insufficient disk headroom for image archive'
  transfer=$(mktemp -d "$state/transfer.XXXXXX")
  { printf '%s' "$archive_prefix"; head -c "$archive_size"; } >"$transfer/image.tar"
  [[ $(stat -c %s "$transfer/image.tar") == "$archive_size" ]] || fail 'Truncated or oversized image archive'
  printf '%s  %s\n' "$archive_sha" "$transfer/image.tar" | sha256sum -c - >/dev/null || fail 'Image archive checksum mismatch'
  docker_root=$(docker info --format '{{.DockerRootDir}}')
  [[ -d $docker_root ]] || fail 'Cannot verify Docker storage headroom'
  # Validate everything before emitting an untagged normalized archive to Docker.
  python3 "$verifier" "$transfer/image.tar" "$image_id" "$docker_root" "$expanded_limit" | docker image load >/dev/null
  [[ $(docker image inspect --format '{{.Id}}' "$image_id") == "$image_id" ]] || fail 'Loaded image ID mismatch'
  if [[ $3 == --verify-image-archive-stdin ]]; then
    cleanup_transfer
    echo "dev import verified: $image $image_id"
    exit 0
  fi
  export FRESHFIRST_IMAGE=$image_id
  printf '%s\n' "$image_id" >"$state/pending-image-id"
  printf '%s %s\n' "$archive_sha" "$archive_size" >"$state/pending-archive"
fi
cleanup_transfer
previous=$("${compose[@]}" ps -q app)
if [[ -n $previous ]]; then docker inspect --format '{{.Config.Image}}' "$previous" >"$state/previous-image"; fi
printf '%s\n' "$image" >"$state/pending-image"
"${compose[@]}" up -d --no-deps --no-build --pull never app
for attempt in {1..30}; do
  app_id=$("${compose[@]}" ps -q app)
  if [[ -n $app_id && $(docker inspect --format '{{.State.Health.Status}}' "$app_id") == healthy ]]; then
    if [[ $environment == dev ]]; then
      [[ $(docker inspect --format '{{.Image}}' "$app_id") == "$image_id" ]] || fail 'Running dev image ID mismatch'
    fi
    mv "$state/pending-image" "$state/current-image"
    if [[ $environment == dev ]]; then
      mv "$state/pending-image-id" "$state/current-image-id"
      mv "$state/pending-archive" "$state/current-archive"
    fi
    echo "$environment healthy: $image"
    exit 0
  fi
  sleep 5
done
fail 'Application not healthy; pending-image retained. Roll back explicitly after checking schema compatibility.'
