"""Read-only activation gates with synthetic Docker/HTTP responses."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "failure", ["", "ram", "volume", "port", "production", "dev", "limits"]
)
def test_host_gate_fails_closed_without_mutating_containers(tmp_path, failure):
    bash = (
        r"C:\Program Files\Git\bin\bash.exe"
        if os.name == "nt"
        else shutil.which("bash")
    )
    if not bash or not Path(bash).exists():
        pytest.skip("Bash required")
    scripts = {
        "sudo": '#!/bin/sh\n[ "$1" = -n ] || exit 1\nshift\nexec "$@"\n',
        "awk": '#!/bin/sh\nif [ "$FAILURE" = ram ]; then echo 1; else echo 9999999; fi\n',
        "sha256sum": "#!/bin/sh\nprintf '%064d  /compose.yaml\\n' 0\n",
        "curl": '#!/bin/sh\n[ "$FAILURE" != production ]\n',
        "docker": """#!/bin/sh
echo "$*" >> "$CALL_LOG"
case "$1" in
 ps)
  case "$*" in
   *project=freshfirst-dev*service=db*) echo dev-db;;
   *project=freshfirst-dev*service=app*) echo dev-app;;
   *service=app*) echo prod-app;;
   *service=db*) echo prod-db;;
   *service=caddy*) echo prod-caddy;;
   *) printf 'prod-app\\nprod-db\\nprod-caddy\\n';;
  esac;;
 inspect)
  case "$3" in
   *State.Running*) echo true;;
   *State.Health.Status*)
    if [ "$FAILURE" = dev ] && [ "$4" = dev-app ]; then echo unhealthy; else echo healthy; fi;;
   *HostConfig.Memory*)
    if [ "$4" = dev-db ]; then echo '134217728 134217728 150000000 no';
    elif [ "$FAILURE" = limits ]; then echo '0 0 0 always';
    else echo '402653184 402653184 250000000 no'; fi;;
   *HostConfig.PortBindings*)
    if [ "$FAILURE" = port ]; then echo '{}';
    else echo '{"8000/tcp":[{"HostIp":"127.0.0.1","HostPort":"8081"}]}'; fi;;
   *range*)
    if [ "$FAILURE" = volume ]; then echo production-volume;
    else echo freshfirst-dev_freshfirst-postgres-data; fi;;
   *) echo '{"name":"prod-app","id":"same","image":"same","started_at":"same","restart_count":0,"ports":{},"mounts":[]}';;
  esac;;
 *) exit 91;;
esac
""",
    }
    for name, content in scripts.items():
        path = tmp_path / name
        path.write_text(content, newline="\n")
        path.chmod(0o755)
    bin_path = tmp_path.as_posix()
    if os.name == "nt":
        bin_path = "/" + bin_path[0].lower() + bin_path[2:]
    env = {
        **os.environ,
        "FAILURE": failure,
        "CALL_LOG": (tmp_path / "calls").as_posix(),
    }
    phase = "before" if failure == "ram" else "after"
    result = subprocess.run(
        [
            bash,
            "-c",
            f'export PATH="{bin_path}:$PATH"; bash infra/gcp/dev-host-check.sh {phase}',
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == (not failure), result.stderr
    calls = Path(env["CALL_LOG"])
    if calls.exists():
        assert all(
            line.startswith(("ps ", "inspect "))
            for line in calls.read_text().splitlines()
        )
