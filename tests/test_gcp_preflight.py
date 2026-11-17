"""Offline workflow checks: no Google credentials, SSH, Docker or deployment."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.load(
        (ROOT / f".github/workflows/{name}.yml").read_text(encoding="utf-8-sig"),
        Loader=yaml.BaseLoader,
    )


def test_preflight_is_manual_and_all_deployments_remain_held():
    gcp, render = workflow("gcp"), workflow("render")
    for job in (
        gcp["jobs"]["build-dev"],
        gcp["jobs"]["promote-production"],
        render["jobs"]["deploy-render"],
    ):
        assert job["if"].strip().startswith("false &&")
    inputs = gcp["on"]["workflow_dispatch"]["inputs"]
    assert inputs["preflight"]["type"] == "boolean"
    assert inputs["preflight"]["default"] == "false"
    for name in ("dev_run_id", "digest", "source_sha"):
        assert inputs[name]["required"] == "false"
    job = gcp["jobs"]["oidc-preflight"]
    assert job["if"] == (
        "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && "
        "inputs.preflight == true && inputs.deploy != true"
    )
    assert job["environment"] == "gcp-development"
    auth = next(
        s
        for s in job["steps"]
        if s.get("uses", "").startswith("google-github-actions/auth")
    )
    assert auth["with"]["service_account"] == "${{ vars.GCP_DEPLOY_SERVICE_ACCOUNT }}"
    assert "token_format" not in auth["with"]
    assert auth["with"]["cleanup_credentials"] == "true"
    assert all("docker/" not in s.get("uses", "") for s in job["steps"])
    command = job["steps"][-1]["run"]
    for forbidden in (
        "REGISTRY_ACCESS_TOKEN",
        "print-access-token",
        "docker pull",
        "metadata.google",
    ):
        assert forbidden not in command
    assert "AUDITING: UNVERIFIED" in command


@pytest.mark.parametrize("failure", ["", "ssh", "sudo", "message", "success", "owner"])
def test_preflight_checks_real_identity_and_fails_closed(tmp_path, failure):
    bash = (
        r"C:\Program Files\Git\bin\bash.exe"
        if os.name == "nt"
        else shutil.which("bash")
    )
    if not bash or not Path(bash).exists():
        pytest.skip("Bash required for offline command tests")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    helper = tmp_path / "helper"
    helper.write_text("never executed by these mocks")
    summary = tmp_path / "summary"
    scripts = {
        "gcloud": """#!/bin/sh
[ "$FAILURE" != ssh ] || exit 255
case "$*" in *"--tunnel-through-iap"*"--ssh-flag=-T"*) ;; *) exit 99;; esac
while [ "$#" -gt 0 ]; do
  if [ "$1" = --command ]; then exec bash -c "$2"; fi
  shift
done
exit 99
""",
        "id": '#!/bin/sh\ncase "$1" in -un) echo sa_actual_oslogin;; -u) echo 1009;; esac\n',
        "stat": '#!/bin/sh\nif [ "$FAILURE" = owner ]; then echo 1000:0:750; else echo 0:0:750; fi\n',
        "sudo": """#!/bin/sh
[ "$1" = -n ] || exit 98
[ "$FAILURE" != sudo ] || exit 1
shift
if [ "$1" = -ll ]; then echo 'NOPASSWD command policy'; exit 0; fi
IFS= read -r unexpected && exit 97
case "$FAILURE" in
  message) echo 'different error'; exit 1;;
  success) exit 0;;
  *) echo 'Missing image archive on stdin' >&2; exit 1;;
esac
""",
    }
    for name, contents in scripts.items():
        path = binaries / name
        path.write_text(contents, newline="\n")
        path.chmod(0o755)
    binary_path = binaries.as_posix()
    if os.name == "nt":
        binary_path = "/" + binary_path[0].lower() + binary_path[2:]
    command = workflow("gcp")["jobs"]["oidc-preflight"]["steps"][-1]["run"]
    command = command.replace("/usr/local/sbin/freshfirst-release", helper.as_posix())
    result = subprocess.run(
        [bash, "-c", f'export PATH="{binary_path}:$PATH"\n' + command],
        input=b"",
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "GCP_VM_NAME": "test-vm",
            "GCP_PROJECT_ID": "test-project",
            "GCP_ZONE": "test-zone",
            "GITHUB_STEP_SUMMARY": summary.as_posix(),
            "FAILURE": failure,
        },
    )
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    assert (result.returncode == 0) == (failure == ""), output
    if not failure:
        assert "sa_actual_oslogin" in output
        assert "AUDITING: UNVERIFIED" in output
        assert "deployments remain held" in summary.read_text()
    else:
        assert not summary.exists()
