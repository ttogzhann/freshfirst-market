"""Reproduce gcloud cold-start ssh-keygen stdout without any VM or cloud access."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_cold_ssh_setup_cannot_enter_strict_snapshot_data(tmp_path):
    bash = (
        r"C:\Program Files\Git\bin\bash.exe"
        if os.name == "nt"
        else shutil.which("bash")
    )
    if not bash or not Path(bash).exists():
        pytest.skip("Bash and ssh-keygen required")
    tools = tmp_path / ".deployment-tools/infra/gcp"
    tools.mkdir(parents=True)
    for name in ("normalize-production-snapshot.py", "dev-host-check.sh"):
        shutil.copyfile(ROOT / "infra/gcp" / name, tools / name)
    bins = tmp_path / "bin"
    bins.mkdir()
    (bins / "python3").write_text('#!/bin/sh\nexec "$TEST_PYTHON" "$@"\n', newline="\n")
    (bins / "gcloud").write_text(
        """#!/bin/bash
set -euo pipefail
key=$GCP_SSH_KEY
command=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --ssh-key-file) shift; key=$1;;
    --command) shift; command=$1;;
  esac
  shift
done
echo "WARNING: SSH diagnostic" >&2
if [ ! -s "$key" ]; then
  # SDK 593.0.0 KeygenCommand: no -q, stdout inherited, no cloud needed.
  ssh-keygen -N '' -t rsa -f "$key"
  echo "Warning: Permanently added test host" >&2
fi
if [ "$command" = true ]; then
  echo "setup diagnostic on stdout"
  [ "${FAIL_SETUP:-}" != yes ] || exit 73
else
  cat >/dev/null
  [ "${CONTAMINATE:-}" != yes ] || echo "unexpected snapshot output"
  cat "$SNAPSHOT"
fi
""",
        newline="\n",
    )
    for path in bins.iterdir():
        path.chmod(0o755)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "name": "caddy",
                "id": "unchanged",
                "image": "unchanged",
                "started_at": "unchanged",
                "restart_count": 0,
                "ports": {},
                "mounts": [],
            }
        )
        + "\n"
    )
    bin_path = bins.as_posix()
    if os.name == "nt":
        bin_path = "/" + bin_path[0].lower() + bin_path[2:]
    env = {
        **os.environ,
        "TEST_PYTHON": sys.executable,
        "GCP_SSH_KEY": (tmp_path / "runner-ssh").as_posix(),
        "RUNNER_TEMP": tmp_path.as_posix(),
        "GITHUB_STEP_SUMMARY": (tmp_path / "summary").as_posix(),
        "SNAPSHOT": snapshot.as_posix(),
        "GCP_PROJECT_ID": "test",
        "GCP_VM_NAME": "test",
        "GCP_ZONE": "test",
    }
    prefix = f'export PATH="{bin_path}:$PATH"\n'

    def run(code, **extra):
        return subprocess.run(
            [bash, "-c", prefix + code],
            cwd=tmp_path,
            env={**env, **extra},
            capture_output=True,
            text=True,
            check=False,
        )

    # The actual ssh-keygen progress is rejected by the unchanged strict parser.
    cold = run(
        'set -eo pipefail; gcloud --command "bash -s -- before" </dev/null | '
        "python3 .deployment-tools/infra/gcp/normalize-production-snapshot.py"
    )
    assert cold.returncode != 0
    assert "Invalid production snapshot" in cold.stderr
    Path(env["GCP_SSH_KEY"]).unlink(missing_ok=True)
    Path(env["GCP_SSH_KEY"] + ".pub").unlink(missing_ok=True)

    workflow = yaml.load(
        (ROOT / ".github/workflows/gcp.yml").read_text(encoding="utf-8-sig"),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["build-dev"]["steps"]
    setup = next(
        s["run"]
        for s in steps
        if s.get("name") == "Prepare noninteractive IAP SSH outside snapshot data"
    )
    before = next(
        s["run"]
        for s in steps
        if s.get("name")
        == "Check production health, dev database isolation and host headroom"
    )
    after = next(
        s["run"]
        for s in steps
        if s.get("name") == "Verify dev health and unchanged production metadata"
    )
    ready = run(setup)
    assert ready.returncode == 0, ready.stderr
    assert ready.stdout == ""
    assert "Generating public/private rsa key pair" in ready.stderr
    assert "setup diagnostic on stdout" in ready.stderr
    assert (
        "Permanently added" in ready.stderr
        and "WARNING: SSH diagnostic" in ready.stderr
    )
    assert run(before).returncode == 0
    assert run(after).returncode == 0
    assert (tmp_path / "production.before").read_bytes() == (
        tmp_path / "production.after"
    ).read_bytes()
    assert run(before, CONTAMINATE="yes").returncode != 0
    assert run(setup, FAIL_SETUP="yes").returncode == 73
