#!/usr/bin/env bash
# Read-only host gate. Output contains selected metadata, never container env.
set -euo pipefail
[[ $# == 1 && ( $1 == before || $1 == after ) ]]
if [[ $1 == before ]]; then
  available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  [[ $available =~ ^[0-9]+$ && $available -ge 524288 ]] || { echo 'Requires 512 MiB available RAM' >&2; exit 1; }
fi
for service in app db caddy; do
  id=$(sudo -n docker ps -q --filter label=com.docker.compose.project=freshfirst --filter "label=com.docker.compose.service=$service")
  [[ -n $id && $id != *$'\n'* ]]
  [[ $(sudo -n docker inspect --format '{{.State.Running}}' "$id") == true ]]
  if [[ $service != caddy ]]; then
    [[ $(sudo -n docker inspect --format '{{.State.Health.Status}}' "$id") == healthy ]]
  fi
done
db=$(sudo -n docker ps -q --filter label=com.docker.compose.project=freshfirst-dev --filter label=com.docker.compose.service=db)
[[ -n $db && $db != *$'\n'* ]]
[[ $(sudo -n docker inspect --format '{{.State.Health.Status}}' "$db") == healthy ]]
[[ $(sudo -n docker inspect --format '{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}} {{.HostConfig.NanoCpus}} {{.HostConfig.RestartPolicy.Name}}' "$db") == '134217728 134217728 150000000 no' ]]
[[ $(sudo -n docker inspect --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$db") == freshfirst-dev_freshfirst-postgres-data ]]
if [[ $1 == after ]]; then
  app=$(sudo -n docker ps -q --filter label=com.docker.compose.project=freshfirst-dev --filter label=com.docker.compose.service=app)
  [[ -n $app && $app != *$'\n'* ]]
  [[ $(sudo -n docker inspect --format '{{.State.Health.Status}}' "$app") == healthy ]]
  [[ $(sudo -n docker inspect --format '{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}} {{.HostConfig.NanoCpus}} {{.HostConfig.RestartPolicy.Name}}' "$app") == '402653184 402653184 250000000 no' ]]
  [[ $(sudo -n docker inspect --format '{{json .HostConfig.PortBindings}}' "$app") == '{"8000/tcp":[{"HostIp":"127.0.0.1","HostPort":"8081"}]}' ]]
  curl -fsS --max-time 15 -o /dev/null http://127.0.0.1:8081/healthz
fi
curl -fsS --max-time 15 -o /dev/null https://34.171.30.130.nip.io/healthz
sudo -n sha256sum /usr/local/sbin/freshfirst-release /opt/freshfirst/compose.yaml /opt/freshfirst/infra/gcp/compose.image.yaml /opt/freshfirst/infra/gcp/compose.dev.yaml
ids=$(sudo -n docker ps -aq --filter label=com.docker.compose.project=freshfirst)
sudo -n docker inspect --format '{"name":{{json .Name}},"id":{{json .Id}},"image":{{json .Image}},"started_at":{{json .State.StartedAt}},"restart_count":{{json .RestartCount}},"ports":{{json .HostConfig.PortBindings}},"mounts":{{json .Mounts}}}' $ids "$db"
