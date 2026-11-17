"""Offline archive/SSH/helper checks; no real registry, Docker, VM or credentials."""

import gzip
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "archive", ROOT / "infra/gcp/verify-image-archive.py"
)
ARCHIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARCHIVE)
IMAGE = "us-central1-docker.pkg.dev/test-project/freshfirst/app@sha256:" + "a" * 64


def image_archive(
    *,
    tags=None,
    bad_layer=False,
    unsafe=False,
    config_id=None,
    architecture="amd64",
    compressed=False,
):
    layer = b"isolated layer contents"
    config = json.dumps(
        {
            "os": "linux",
            "architecture": architecture,
            "rootfs": {
                "type": "layers",
                "diff_ids": ["sha256:" + hashlib.sha256(layer).hexdigest()],
            },
        }
    ).encode()
    image_id = "sha256:" + hashlib.sha256(config).hexdigest()
    manifest = [{"Config": "config.json", "RepoTags": tags, "Layers": ["layer.tar"]}]
    content = {
        "manifest.json": json.dumps(manifest).encode(),
        "config.json": config,
        "layer.tar": b"tampered"
        if bad_layer
        else (gzip.compress(layer) if compressed else layer),
        "index.json": b'{"annotations":{"io.containerd.image.name":"production:latest"}}',
    }
    if unsafe:
        content["../outside"] = b"not extracted"
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, data in content.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return stream.getvalue(), config_id or image_id


def test_archive_is_verified_then_normalized_without_tags_or_extra_metadata(tmp_path):
    data, image_id = image_archive()
    source = tmp_path / "image.tar"
    source.write_bytes(data)
    out = io.BytesIO()
    ARCHIVE.normalize(source, image_id, out)
    with tarfile.open(fileobj=io.BytesIO(out.getvalue())) as archive:
        manifest = json.load(archive.extractfile("manifest.json"))
        assert manifest[0]["RepoTags"] is None
        assert archive.getnames() == [
            "manifest.json",
            image_id[7:] + ".json",
            "layers/0/layer.tar",
        ]
        assert (
            "sha256:"
            + hashlib.sha256(
                archive.extractfile(manifest[0]["Config"]).read()
            ).hexdigest()
            == image_id
        )


@pytest.mark.parametrize(
    "options",
    [
        {"tags": ["production:latest"]},
        {"bad_layer": True},
        {"unsafe": True},
        {"config_id": "sha256:" + "b" * 64},
        {"architecture": "arm64"},
    ],
)
def test_invalid_archive_emits_no_docker_input(tmp_path, options):
    data, image_id = image_archive(**options)
    source = tmp_path / "image.tar"
    source.write_bytes(data)
    out = io.BytesIO()
    with pytest.raises(ValueError):
        ARCHIVE.normalize(source, image_id, out)
    assert out.getvalue() == b""


def test_compressed_layers_are_checked_uncompressed_and_bounded(tmp_path, monkeypatch):
    data, image_id = image_archive(compressed=True)
    source = tmp_path / "image.tar"
    source.write_bytes(data)
    output = io.BytesIO()
    ARCHIVE.normalize(source, image_id, output)
    with tarfile.open(fileobj=io.BytesIO(output.getvalue())) as archive:
        assert (
            archive.extractfile("layers/0/layer.tar").read()
            == b"isolated layer contents"
        )
    monkeypatch.setattr(ARCHIVE, "MAX_EXPANDED_BYTES", 1)
    output = io.BytesIO()
    with pytest.raises(ValueError, match="Expanded layer size"):
        ARCHIVE.normalize(source, image_id, output)
    assert not output.getvalue()


@pytest.fixture
def runtime(tmp_path):
    bash = (
        r"C:\Program Files\Git\bin\bash.exe"
        if os.name == "nt"
        else shutil.which("bash")
    )
    if not bash or not Path(bash).exists():
        pytest.skip("Bash required")
    app, config, state, binaries = [
        tmp_path / x for x in ("app", "config", "state", "bin")
    ]
    for path in (app / "infra/gcp", config, state / "dev", binaries):
        path.mkdir(parents=True)
    for name in (
        "compose.yaml",
        "infra/gcp/compose.image.yaml",
        "infra/gcp/compose.dev.yaml",
    ):
        (app / name).write_text("services: {}")
    shutil.copyfile(
        ROOT / "infra/gcp/verify-image-archive.py",
        app / "infra/gcp/verify-image-archive.py",
    )
    (config / "deploy.conf").write_text("IMAGE_REPOSITORY=" + IMAGE.split("@")[0])
    (config / "dev.env").write_text(
        "POSTGRES_DB=freshfirst_dev\nPOSTGRES_USER=freshfirst_dev\nPOSTGRES_PASSWORD=independent-dev-password\n"
        "FRESHFIRST_AUTH_SECRET=independent-dev-secret\nFRESHFIRST_PORT=127.0.0.1:8081\n"
        "FRESHFIRST_TRUSTED_ORIGINS=http://127.0.0.1:8081\n"
    )
    helper = tmp_path / "release.sh"
    helper.write_text(
        (ROOT / "infra/gcp/freshfirst-release.sh")
        .read_text()
        .replace("/etc/freshfirst", config.as_posix())
        .replace("/opt/freshfirst", app.as_posix())
        .replace("/var/lib/freshfirst-releases", state.as_posix()),
        newline="\n",
    )
    scripts = {
        "install": "#!/bin/sh\nexit 0\n",
        "flock": "#!/bin/sh\nexit 0\n",
        "stat": '#!/bin/sh\ncase "$2" in %u) echo 0;; %a) case "$3" in *verify-image-archive.py) echo 644;; *) echo 600;; esac;; %s) wc -c < "$3" | tr -d " ";; esac\n',
        "df": '#!/bin/sh\necho "Filesystem size used available percent mount"\necho "test 9999999999 0 ${FREE_BYTES:-9999999999} 0% /"\n',
        "python3": '#!/bin/sh\nexec "$TEST_PYTHON" "$@"\n',
        "docker": """#!/bin/sh
echo "${ON_VM:-runner} $*" >> "$CALL_LOG"
if [ "${ON_VM:-}" = 1 ]; then
  case "$*" in login*|pull*|"image pull"*|*" pull app") exit 91;; esac
fi
case "$*" in
 "info --format {{.DockerRootDir}}") echo "$DOCKER_ROOT_PATH";;
 *"ps -q db") echo db;;
 *"ps -q app") echo app;;
 *".State.Health.Status"*) echo healthy;;
 *".Config.Image"*) echo old-image;;
 *"{{.Image}}"*) echo "${RUNNING_IMAGE_ID:-$TEST_IMAGE_ID}";;
 "image inspect --format {{json .RepoDigests}}"*) printf '["%s"]\\n' "${REPORTED_IMAGE:-$TEST_IMAGE}";;
 "image inspect --format {{.Id}}"*) echo "$TEST_IMAGE_ID";;
 "image save"*) cp "$SOURCE_ARCHIVE" "$4";;
 "image load") cat > "$IMPORTED_ARCHIVE";;
 *"up -d"*) [ "$FRESHFIRST_IMAGE" = "$TEST_IMAGE_ID" ] || exit 92;;
esac
""",
        "gcloud": """#!/bin/sh
while [ "$#" -gt 0 ]; do
 if [ "$1" = --command ]; then export ON_VM=1; exec bash -c "$2"; fi
 shift
done
exit 93
""",
        "sudo": '#!/bin/sh\n[ "$1" = -n ] || exit 95\nshift\nexec bash "$@"\n',
        "curl": "#!/bin/sh\nexit 94\n",
    }
    for name, text in scripts.items():
        path = binaries / name
        path.write_text(text, newline="\n")
        path.chmod(0o755)
    binary_path = binaries.as_posix()
    if os.name == "nt":
        binary_path = "/" + binary_path[0].lower() + binary_path[2:]
    log = tmp_path / "calls"

    def run(
        *,
        data=None,
        checksum=None,
        size=None,
        free=None,
        running=None,
        workflow=False,
        reported=None,
    ):
        archive, image_id = image_archive()
        data = archive if data is None else data
        source = tmp_path / "source.tar"
        source.write_bytes(data)
        env = {
            **os.environ,
            "TEST_PYTHON": sys.executable,
            "TEST_IMAGE_ID": image_id,
            "TEST_IMAGE": IMAGE,
            "DOCKER_ROOT_PATH": tmp_path.as_posix(),
            "CALL_LOG": log.as_posix(),
            "IMPORTED_ARCHIVE": (tmp_path / "imported.tar").as_posix(),
            "SOURCE_ARCHIVE": source.as_posix(),
            "RUNNER_TEMP": tmp_path.as_posix(),
            "GITHUB_OUTPUT": (tmp_path / "outputs").as_posix(),
            "IMAGE": IMAGE,
            "GCP_PROJECT_ID": "test",
            "GCP_VM_NAME": "test",
            "GCP_ZONE": "test",
            "ON_VM": "1",
        }
        if free is not None:
            env["FREE_BYTES"] = str(free)
        if running:
            env["RUNNING_IMAGE_ID"] = running
        if reported:
            env["REPORTED_IMAGE"] = reported
        prefix = f'export PATH="{binary_path}:$PATH"\n'
        if workflow:
            env.pop("ON_VM")
            w = yaml.load(
                (ROOT / ".github/workflows/gcp.yml").read_text(encoding="utf-8-sig"),
                Loader=yaml.BaseLoader,
            )
            step = next(
                s
                for s in w["jobs"]["build-dev"]["steps"]
                if s.get("id") == "dev-transfer"
            )
            script = step["run"].replace(
                "/usr/local/sbin/freshfirst-release", helper.as_posix()
            )
            command = [bash, "-c", prefix + script]
            stdin = b""
        else:
            runner = tmp_path / "runner.sh"
            runner.write_text(
                prefix + f'exec bash "{helper.as_posix()}" "$@"\n', newline="\n"
            )
            command = [
                bash,
                str(runner),
                "dev",
                IMAGE,
                "--image-archive-stdin",
                checksum or hashlib.sha256(data).hexdigest(),
                str(size or len(data) or 1),
                image_id,
            ]
            stdin = data
        result = subprocess.run(
            command, input=stdin, capture_output=True, env=env, check=False
        )
        return result, state, log, tmp_path, image_id

    return run


def test_helper_imports_only_verified_image_and_preserves_digest_metadata(runtime):
    result, state, log, temp, image_id = runtime()
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    calls = log.read_text()
    assert "1 image load" in calls
    assert "--project-name freshfirst-dev" in calls
    assert "up -d --no-deps --no-build --pull never app" in calls
    assert (state / "dev/current-image").read_text().strip() == IMAGE
    assert (state / "dev/current-image-id").read_text().strip() == image_id
    assert not list((state / "dev").glob("transfer.*"))
    with tarfile.open(temp / "imported.tar") as archive:
        assert "index.json" not in archive.getnames()


@pytest.mark.parametrize(
    "options",
    [
        {"data": b""},
        {"checksum": "0" * 64},
        {"size": 999999},
        {"free": 0},
        {"running": "sha256:" + "0" * 64},
        {"data": image_archive(bad_layer=True)[0]},
    ],
)
def test_helper_fails_without_publishing_a_healthy_release(runtime, options):
    result, state, _, _, _ = runtime(**options)
    assert result.returncode != 0
    assert not (state / "dev/current-image").exists()
    assert not list((state / "dev").glob("transfer.*"))
    if options == {"data": b""}:
        assert b"Missing image archive on stdin" in result.stderr


@pytest.mark.parametrize("reported", [None, IMAGE.replace("a" * 64, "b" * 64)])
def test_workflow_exports_exact_registry_digest_and_transfers_only_image_bytes(
    runtime, reported
):
    result, state, log, temp, image_id = runtime(workflow=True, reported=reported)
    calls = log.read_text()
    if reported:
        assert result.returncode != 0
        assert "1 image load" not in calls
        assert not (state / "dev/current-image").exists()
    else:
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        assert (state / "dev/current-image-id").read_text().strip() == image_id
        assert "runner pull --platform linux/amd64 " + IMAGE in calls
        assert "1 pull" not in calls and "login" not in calls
        assert "archive_sha256=" in (temp / "outputs").read_text()
    assert not list(temp.glob("freshfirst-dev.*.tar"))


def test_workflow_keeps_holds_preflight_and_one_build_with_no_vm_credentials():
    def load(name):
        return yaml.load(
            (ROOT / f".github/workflows/{name}.yml").read_text(encoding="utf-8-sig"),
            Loader=yaml.BaseLoader,
        )

    gcp, render = load("gcp"), load("render")
    for job in (
        gcp["jobs"]["build-dev"],
        gcp["jobs"]["promote-production"],
        render["jobs"]["deploy-render"],
    ):
        assert job["if"].strip().startswith("false &&")
    dev = gcp["jobs"]["build-dev"]
    assert (
        sum("docker/build-push-action@" in s.get("uses", "") for s in dev["steps"]) == 1
    )
    assert "REGISTRY_ACCESS_TOKEN" not in json.dumps(dev)
    assert "--registry-token-stdin" not in json.dumps(dev)
    assert all("token_format" not in s.get("with", {}) for s in dev["steps"])
    assert gcp["jobs"]["oidc-preflight"]["environment"] == "gcp-development"


def test_release_metadata_retains_registry_digest_and_transfer_binding(tmp_path):
    workflow = yaml.load(
        (ROOT / ".github/workflows/gcp.yml").read_text(encoding="utf-8-sig"),
        Loader=yaml.BaseLoader,
    )
    step = next(
        s
        for s in workflow["jobs"]["build-dev"]["steps"]
        if s.get("name") == "Record healthy dev release"
    )
    code = step["run"].split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    _, image_id = image_archive()
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        check=True,
        env={
            **os.environ,
            "IMAGE": IMAGE,
            "DIGEST": IMAGE.split("@")[1],
            "SOURCE_SHA": "b" * 40,
            "CI_RUN_ID": "10",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12",
            "IMAGE_ID": image_id,
            "ARCHIVE_SHA256": "c" * 64,
            "ARCHIVE_SIZE": "10240",
        },
    )
    record = json.loads((tmp_path / "release.json").read_text())
    assert record["image"] == IMAGE
    assert record["digest"] == IMAGE.split("@")[1]
    assert record["source_sha"] == "b" * 40
    assert record["ci_run_id"] == 10 and record["dev_run_id"] == 12
    assert record["dev_healthy"] is True
    assert (
        record["image_id"] == image_id
        and record["transport"] == "verified-image-archive"
    )
    assert record["archive_sha256"] == "c" * 64 and record["archive_size"] == 10240
