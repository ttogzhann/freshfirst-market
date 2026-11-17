"""Offline manual publisher checks: no real image pull/push, credentials or VM."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name="gcp"):
    return yaml.load(
        (ROOT / f".github/workflows/{name}.yml").read_text(encoding="utf-8-sig"),
        Loader=yaml.BaseLoader,
    )


def test_publisher_is_manual_mutually_exclusive_and_all_deployments_stay_held():
    w = workflow()
    job = w["jobs"]["publish-import-test-image"]
    assert job["if"] == (
        "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && "
        "inputs.publish_test_image == true && inputs.preflight != true && inputs.deploy != true"
    )
    assert "inputs.publish_test_image != true" in w["jobs"]["oidc-preflight"]["if"]
    assert (
        w["on"]["workflow_dispatch"]["inputs"]["publish_test_image"]["default"]
        == "false"
    )
    for j in [
        w["jobs"]["build-dev"],
        w["jobs"]["promote-production"],
        workflow("render")["jobs"]["deploy-render"],
    ]:
        assert j["if"].strip().startswith("false &&")
    assert job["environment"] == "gcp-development"
    steps = job["steps"]
    check = next(i for i, s in enumerate(steps) if s.get("id") == "archive")
    auth = next(
        i
        for i, s in enumerate(steps)
        if s.get("uses", "").startswith("google-github-actions/auth")
    )
    assert check < auth
    assert (
        steps[auth]["with"]["service_account"]
        == "${{ vars.GCP_DEPLOY_SERVICE_ACCOUNT }}"
    )
    assert "credentials_json" not in steps[auth]["with"]
    assert "@sha256:" in job["env"]["TEST_BASE_IMAGE"]
    for forbidden in [
        "compute ssh",
        "compute scp",
        "docker build",
        "freshfirst-release",
    ]:
        assert forbidden not in json.dumps(job)
    assert steps[-1]["with"]["path"] == "import-test-image.json"
    assert steps[-1]["with"]["name"] != "healthy-dev-release"


@pytest.mark.parametrize(
    "size,platform,mismatch",
    [
        (96, "linux/amd64", False),
        (67108864, "linux/amd64", False),
        (96, "linux/arm64", False),
        (96, "linux/amd64", True),
    ],
)
def test_publisher_enforces_size_platform_and_immutable_identity(
    tmp_path, size, platform, mismatch
):
    bash = (
        r"C:\Program Files\Git\bin\bash.exe"
        if os.name == "nt"
        else shutil.which("bash")
    )
    if not bash or not Path(bash).exists():
        pytest.skip("Bash required")
    binary = tmp_path / "bin"
    binary.mkdir()
    calls = tmp_path / "calls"
    output = tmp_path / "outputs"
    repo = "us-central1-docker.pkg.dev/test-project/freshfirst/app"
    scripts = {
        "docker": """#!/bin/sh
echo "$*" >> "$CALL_LOG"
case "$*" in
 "image inspect --format {{.Os}}/{{.Architecture}}"*) echo "$TEST_PLATFORM";;
 "image inspect --format {{.Id}}"*)
   case "$*" in *"$IMAGE_REPOSITORY@"*) echo "$TARGET_ID";; *) echo "$SOURCE_ID";; esac;;
 "image save"*) printf '%096d' 0 > "$4";;
 "image inspect --format {{json .RepoDigests}}"*) printf '["%s@sha256:%s"]\\n' "$IMAGE_REPOSITORY" "$TARGET_DIGEST";;
esac
""",
        "stat": '#!/bin/sh\necho "$TEST_ARCHIVE_SIZE"\n',
        "gcloud": '#!/bin/sh\ncase "$*" in "auth configure-docker "*) echo "$*" >> "$CALL_LOG";; *) exit 99;; esac\n',
    }
    for name, script in scripts.items():
        path = binary / name
        path.write_text(script, newline="\n")
        path.chmod(0o755)
    # Use the already-selected Python environment, not a host python3 alias.
    import sys

    (binary / "python3").write_text(
        '#!/bin/sh\nexec "$TEST_PYTHON" "$@"\n', newline="\n"
    )
    (binary / "python3").chmod(0o755)
    posix_bin = binary.as_posix()
    if os.name == "nt":
        posix_bin = "/" + posix_bin[0].lower() + posix_bin[2:]
    job = workflow()["jobs"]["publish-import-test-image"]
    env = {
        **os.environ,
        **job["env"],
        "TEST_PYTHON": sys.executable,
        "CALL_LOG": calls.as_posix(),
        "RUNNER_TEMP": tmp_path.as_posix(),
        "GITHUB_OUTPUT": output.as_posix(),
        "GITHUB_STEP_SUMMARY": (tmp_path / "summary").as_posix(),
        "GITHUB_RUN_ID": "12",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_REPOSITORY": "owner/repo",
        "IMAGE_REPOSITORY": repo,
        "REGISTRY": repo.split("/")[0],
        "SOURCE_ID": "sha256:" + "b" * 64,
        "TARGET_ID": "sha256:" + ("d" if mismatch else "b") * 64,
        "TARGET_DIGEST": "c" * 64,
        "TEST_ARCHIVE_SIZE": str(size),
        "TEST_PLATFORM": platform,
    }
    result = None
    for step in (s for s in job["steps"] if "run" in s):
        result = subprocess.run(
            [bash, "-c", f'export PATH="{posix_bin}:$PATH"\n' + step["run"]],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            break
        for line in output.read_text().splitlines():
            key, value = line.split("=", 1)
            env[key.upper()] = value
    success = size < 67108864 and platform == "linux/amd64" and not mismatch
    assert (result.returncode == 0) == success, result.stderr.decode(errors="replace")
    log = calls.read_text()
    assert "compute ssh" not in log
    assert not list(tmp_path.glob("freshfirst-import-test.*.tar"))
    if size >= 67108864 or platform != "linux/amd64":
        assert "push " not in log and "configure-docker" not in log
    if success:
        record = json.loads((tmp_path / "import-test-image.json").read_text())
        assert record["image"] == repo + "@sha256:" + "c" * 64
        assert record["image_id"] == "sha256:" + "b" * 64
        assert record["archive_size"] == 96
        assert record["archive_sha256"] == hashlib.sha256(b"0" * 96).hexdigest()
        assert record["platform"] == "linux/amd64" and record["run_id"] == 12
        assert "healthy" not in record
