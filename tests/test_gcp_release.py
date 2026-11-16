"""Offline release checks: no Docker daemon, network, VM or real credentials."""

import copy
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "promotion", ROOT / "infra/gcp/verify-promotion.py"
)
PROMOTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROMOTION)
DIGEST = "sha256:" + "a" * 64
SHA = "b" * 40
IMAGE = "us-central1-docker.pkg.dev/test-project/freshfirst/app@" + DIGEST


def metadata():
    repo = {"full_name": "owner/repo"}
    release = {
        "image": IMAGE,
        "digest": DIGEST,
        "source_sha": SHA,
        "repository": "owner/repo",
        "dev_run_id": 12,
        "ci_run_id": 10,
        "dev_healthy": True,
    }
    run = {
        "id": 12,
        "repository": repo,
        "event": "workflow_run",
        "conclusion": "success",
        "path": ".github/workflows/gcp.yml",
        "head_branch": "main",
    }
    ci = {
        "id": 10,
        "repository": repo,
        "head_repository": repo,
        "event": "push",
        "head_branch": "feature/render-deployment",
        "head_sha": SHA,
        "path": ".github/workflows/render.yml",
        "conclusion": "success",
    }
    return release, run, ci


def test_exact_digest_and_old_successful_release_can_be_promoted():
    # workflow_run itself runs from default main, while its CI source is the feature branch.
    assert PROMOTION.verify(*metadata(), "owner/repo", DIGEST, SHA, "12") == IMAGE


@pytest.mark.parametrize(
    "section,key,value",
    [
        (0, "digest", "sha256:" + "c" * 64),
        (0, "source_sha", "c" * 40),
        (0, "dev_healthy", False),
        (0, "dev_run_id", 13),
        (0, "image", IMAGE + "'; false"),
        (1, "conclusion", "failure"),
        (1, "event", "workflow_dispatch"),
        (1, "path", ".github/workflows/other.yml"),
        (2, "event", "pull_request"),
        (2, "head_branch", "other"),
        (2, "head_sha", "c" * 40),
        (2, "conclusion", "failure"),
        (2, "head_repository", {"full_name": "attacker/fork"}),
    ],
)
def test_mismatched_or_untrusted_release_is_rejected(section, key, value):
    values = copy.deepcopy(metadata())
    values[section][key] = value
    with pytest.raises(ValueError):
        PROMOTION.verify(*values, "owner/repo", DIGEST, SHA, "12")


def test_workflow_preserves_ci_sha_and_manual_production_gate():
    workflow = yaml.load(
        (ROOT / ".github/workflows/gcp.yml").read_text(encoding="utf-8-sig"),
        Loader=yaml.BaseLoader,
    )
    dev, prod = workflow["jobs"]["build-dev"], workflow["jobs"]["promote-production"]
    assert dev["if"].strip().startswith("false &&")
    assert workflow["on"]["workflow_dispatch"]["inputs"]["deploy"] == {
        "description": "Explicitly approve promoting the verified dev digest to production",
        "required": "true",
        "default": "false",
        "type": "boolean",
    }
    for guard in (
        "conclusion == 'success'",
        "event == 'push'",
        "head_branch == 'feature/render-deployment'",
        "head_repository.full_name == github.repository",
    ):
        assert guard in dev["if"]
    assert dev["steps"][0]["with"]["ref"] == "${{ github.event.workflow_run.head_sha }}"
    assert "github.event_name == 'workflow_dispatch'" in prod["if"]
    assert "inputs.deploy == true" in prod["if"]
    assert "github.ref == 'refs/heads/feature/render-deployment'" in prod["if"]
    assert "||" not in prod["if"]
    assert prod["environment"] == "gcp-production"
    assert (
        sum(
            "docker/build-push-action@" in step.get("uses", "") for step in dev["steps"]
        )
        == 1
    )
    assert not any("build-push" in step.get("uses", "") for step in prod["steps"])
    verify_index = next(
        i for i, step in enumerate(prod["steps"]) if step.get("id") == "release"
    )
    auth_index = next(
        i
        for i, step in enumerate(prod["steps"])
        if step.get("uses", "").startswith("google-github-actions/auth")
    )
    assert verify_index < auth_index


def test_check_only_ci_does_not_trigger_legacy_production_listener():
    def workflow(name):
        return yaml.load(
            (ROOT / f".github/workflows/{name}.yml").read_text(encoding="utf-8-sig"),
            Loader=yaml.BaseLoader,
        )

    ci, gcp = workflow("render"), workflow("gcp")
    assert ci["name"] == "FreshFirst checks"
    assert ci["name"] != "FreshFirst Render CI/CD"  # Legacy workflow_run listener.
    assert gcp["on"]["workflow_run"]["workflows"] == [ci["name"]]
    assert ci["on"]["push"]["branches"] == ["feature/render-deployment"]
    assert "pull_request" in ci["on"]
    assert ci["on"]["workflow_dispatch"]["inputs"]["deploy"]["default"] == "false"
    deploy = ci["jobs"]["deploy-render"]
    assert deploy["if"].strip() == (
        "github.event_name == 'workflow_dispatch' && inputs.deploy == true && "
        "github.ref == 'refs/heads/feature/render-deployment'"
    )
    assert deploy["environment"] == "render-production"
    assert set(deploy["needs"]) == {
        "backend",
        "frontend",
        "production-image",
        "compose-integration",
        "playwright-e2e",
    }
    assert set(ci["jobs"]) == set(deploy["needs"]) | {"deploy-render"}
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    assert blueprint["services"][0]["autoDeploy"] is False


@pytest.fixture
def shell_runtime(tmp_path):
    bash = shutil.which("bash")
    if os.name == "nt":
        bash = r"C:\Program Files\Git\bin\bash.exe"
    if not bash or not Path(bash).exists():
        pytest.skip("Bash required for isolated helper tests")
    app, config, state, binaries = [
        tmp_path / name for name in ("app", "config", "state", "bin")
    ]
    for path in (app / "infra/gcp", config, binaries):
        path.mkdir(parents=True)
    for environment in ("dev", "prod"):
        (state / environment).mkdir(parents=True)
    (app / "compose.yaml").write_text("services: {}")
    (app / "infra/gcp/compose.image.yaml").write_text("services: {}")
    (app / "infra/gcp/compose.dev.yaml").write_text("services: {}")
    (config / "deploy.conf").write_text("IMAGE_REPOSITORY=" + IMAGE.split("@")[0])
    (app / ".env").write_text(
        "POSTGRES_PASSWORD=prod-password\nFRESHFIRST_AUTH_SECRET=prod-secret\n"
    )
    (config / "dev.env").write_text(
        "POSTGRES_DB=freshfirst_dev\nPOSTGRES_USER=freshfirst_dev\nPOSTGRES_PASSWORD=dev-password\nFRESHFIRST_AUTH_SECRET=dev-secret\nFRESHFIRST_PORT=127.0.0.1:8081\nFRESHFIRST_TRUSTED_ORIGINS=http://127.0.0.1:8081\n"
    )
    script = (ROOT / "infra/gcp/freshfirst-release.sh").read_text()
    script = (
        script.replace("/etc/freshfirst", config.as_posix())
        .replace("/opt/freshfirst", app.as_posix())
        .replace("/var/lib/freshfirst-releases", state.as_posix())
    )
    helper = tmp_path / "release.sh"
    helper.write_text(script, newline="\n")
    mocks = {
        "install": "#!/bin/sh\nexit 0\n",  # State directories prepared above.
        "stat": '#!/bin/sh\ncase "$2" in %u) echo 0;; %a) echo 600;; esac\n',
        "flock": "#!/bin/sh\nexit 0\n",
        "curl": '#!/bin/sh\necho metadata >> "$CALL_LOG"\nprintf \'{"access_token":"dummy"}\'\n',
        "python3": "#!/bin/sh\ncat >/dev/null\necho dummy\n",
        "docker": '#!/bin/sh\necho "$*" >> "$CALL_LOG"\ncase "$*" in *"ps -q db") echo db;; *"ps -q app") echo app;; *".State.Health.Status"*) echo healthy;; *".Config.Image"*) echo "us-central1-docker.pkg.dev/test-project/freshfirst/app@sha256:'
        + "c" * 64
        + '";; *login*) cat >/dev/null;; esac\n',
    }
    for name, content in mocks.items():
        path = binaries / name
        path.write_text(content, newline="\n")
        path.chmod(0o755)
    log = tmp_path / "calls.log"
    env = {
        **os.environ,
        "PATH": binaries.as_posix()
        + (":" if os.name != "nt" else ";")
        + os.environ["PATH"],
        "CALL_LOG": log.as_posix(),
    }
    # Git Bash converts the Windows inherited PATH to POSIX; prepend inside bash instead.
    runner = tmp_path / "runner.sh"
    binary_path = binaries.as_posix()
    if os.name == "nt":
        binary_path = "/" + binary_path[0].lower() + binary_path[2:]
    runner.write_text(
        f'#!/bin/bash\nexport PATH="{binary_path}:$PATH"\nexec bash "{helper.as_posix()}" "$@"\n',
        newline="\n",
    )

    def run(environment, image=IMAGE):
        return subprocess.run(
            [bash, str(runner), environment, image],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    return run, log, state, config


@pytest.mark.parametrize(
    "environment,project", [("dev", "freshfirst-dev"), ("prod", "freshfirst")]
)
def test_helper_updates_only_selected_app_and_records_digest(
    shell_runtime, environment, project
):
    run, log, state, _ = shell_runtime
    result = run(environment)
    assert result.returncode == 0, result.stderr
    calls = log.read_text()
    assert f"--project-name {project} " in calls
    assert ("/infra/gcp/compose.dev.yaml" in calls) == (environment == "dev")
    assert "up -d --no-deps --no-build --pull never app" in calls
    assert "up -d db" not in calls and " down " not in calls
    assert (state / environment / "current-image").read_text().strip() == IMAGE
    assert (
        (state / environment / "previous-image").read_text().strip().endswith("c" * 64)
    )


@pytest.mark.parametrize(
    "environment,image",
    [
        ("stage", IMAGE),
        ("prod", "app:latest"),
        ("dev", IMAGE.replace("test-project", "other-project")),
    ],
)
def test_helper_rejects_invalid_input_without_docker_or_network(
    shell_runtime, environment, image
):
    run, log, _, _ = shell_runtime
    assert run(environment, image).returncode != 0
    assert not log.exists()


def test_dev_cannot_reuse_production_secrets(shell_runtime):
    run, log, _, config = shell_runtime
    path = config / "dev.env"
    path.write_text(path.read_text().replace("dev-password", "prod-password"))
    assert run("dev").returncode != 0
    assert not log.exists()


def test_dev_cannot_override_isolation_with_duplicate_keys(shell_runtime):
    run, log, _, config = shell_runtime
    with (config / "dev.env").open("a") as f:
        f.write("FRESHFIRST_PORT=80\n")
    assert run("dev").returncode != 0
    assert not log.exists()


def test_dev_requires_overlay_but_production_does_not(shell_runtime):
    run, log, _, config = shell_runtime
    (config.parent / "app/infra/gcp/compose.dev.yaml").unlink()
    assert run("dev").returncode != 0
    assert not log.exists()
    assert run("prod").returncode == 0
    assert "compose.dev.yaml" not in log.read_text()


@pytest.mark.skipif(not shutil.which("docker"), reason="Docker Compose CLI required")
def test_merged_dev_resources_and_production_isolation(tmp_path):
    import json

    configs = {}
    for name, project in (("prod", "freshfirst"), ("dev", "freshfirst-dev")):
        env_file = tmp_path / f"{name}.env"
        env_file.write_text(
            f"POSTGRES_DB={project.replace('-', '_')}\n"
            f"POSTGRES_USER={project.replace('-', '_')}\n"
            f"POSTGRES_PASSWORD={name}-password\n"
            f"FRESHFIRST_AUTH_SECRET={name}-secret\n"
            f"FRESHFIRST_IMAGE={IMAGE}\n"
        )
        # Ignore host Compose/interpolation settings; use only disposable values.
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("COMPOSE_", "POSTGRES_", "FRESHFIRST_"))
        }
        command = [
            "docker",
            "compose",
            "--project-name",
            project,
            "--env-file",
            str(env_file),
            "--profile",
            "https",
            "-f",
            "compose.yaml",
            "-f",
            "infra/gcp/compose.image.yaml",
        ]
        if name == "dev":
            command += ["-f", "infra/gcp/compose.dev.yaml"]
        result = subprocess.run(
            command + ["config", "--format", "json"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        configs[name] = json.loads(result.stdout)
    dev, prod = configs["dev"], configs["prod"]
    assert set(dev["services"]) == {"app", "db"}
    assert "caddy" in prod["services"]
    for service, memory, cpus in (("app", 384, 0.25), ("db", 128, 0.15)):
        settings = dev["services"][service]
        assert int(settings["mem_limit"]) == memory * 1024 * 1024
        assert settings["memswap_limit"] == settings["mem_limit"]
        assert float(settings["cpus"]) == cpus
        assert settings["restart"] == "no"
        assert "mem_limit" not in prod["services"][service]
    ports = dev["services"]["app"]["ports"]
    assert len(ports) == 1
    assert (ports[0]["host_ip"], str(ports[0]["published"]), ports[0]["target"]) == (
        "127.0.0.1",
        "8081",
        8000,
    )
    assert not dev["services"]["db"].get("ports")
    for kind, key in (
        ("volumes", "freshfirst-postgres-data"),
        ("networks", "freshfirst"),
    ):
        assert dev[kind][key]["name"] == f"freshfirst-dev_{key}"
        assert prod[kind][key]["name"] == f"freshfirst_{key}"
    for service, key in (
        ("app", "FRESHFIRST_AUTH_SECRET"),
        ("db", "POSTGRES_PASSWORD"),
    ):
        assert (
            dev["services"][service]["environment"][key]
            != prod["services"][service]["environment"][key]
        )
    command = dev["services"]["db"]["command"]
    assert {
        "shared_buffers=16MB",
        "work_mem=1MB",
        "maintenance_work_mem=16MB",
        "max_connections=20",
    } <= set(command)
