"""Fail-closed manual DEV admission; no cloud credentials or application imports."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

FOCUSED_TESTS = [
    "tests/test_telemetry_headers.py",
    "tests/test_oncall.py",
    "tests/test_telemetry.py::test_disabled_by_default_does_not_configure_exporters",
    "tests/test_telemetry.py::test_real_routes_counters_trace_log_privacy_and_cleanup",
]
HEADER_NAMES = {
    "OTEL_EXPORTER_OTLP_HEADERS",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
    "OTEL_EXPORTER_OTLP_METRICS_HEADERS",
    "OTEL_EXPORTER_OTLP_LOGS_HEADERS",
    "FRESHFIRST_TELEMETRY_HEADERS_FILE",
}


def dispatch_source(event, ref, control_sha):
    inputs = event.get("inputs", {})
    if ref != "refs/heads/main" or inputs.get("deploy_dev") not in {True, "true"}:
        raise ValueError("Manual DEV requires an explicit main dispatch")
    for mode in ("preflight", "publish_test_image", "deploy"):
        if inputs.get(mode) not in {False, "false", None, ""}:
            raise ValueError("Manual DEV cannot be combined with another mode")
    if inputs.get("dev_run_id") or inputs.get("digest"):
        raise ValueError("Manual DEV cannot consume promotion inputs")
    source = inputs.get("source_sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", source) or not re.fullmatch(r"[a-f0-9]{40}", control_sha):
        raise ValueError("Exact 40-character source and control commits required")
    return source


def require_main_ancestor(repo, source):
    for commit in (source, os.environ["GITHUB_SHA"]):
        result = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, "origin/main"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if result.returncode:
            raise ValueError("Source and control commits must belong to origin/main")


def telemetry_disabled(plan):
    app = plan["services"]["app"]
    env = app.get("environment", {})
    if str(env.get("FRESHFIRST_TELEMETRY_ENABLED", "false")).lower() != "false":
        raise ValueError("DEV telemetry must remain disabled")
    if HEADER_NAMES.intersection(env) or app.get("secrets"):
        raise ValueError("DEV credential environment and secret mounts are forbidden")
    for mount in app.get("volumes", []):
        if not isinstance(mount, dict):
            raise ValueError("Expected normalized Compose mount metadata")
        paths = [str(mount.get(key, "")).lower() for key in ("source", "target")]
        if any("/run/secrets" in path or "otlp" in path for path in paths):
            raise ValueError("DEV telemetry credential mounts are forbidden")


def validate_source(source_dir):
    required = ["compose.yaml", "infra/gcp/compose.image.yaml", "infra/gcp/compose.dev.yaml"]
    required += ["backend/" + item.split("::")[0] for item in FOCUSED_TESTS]
    if any(not (source_dir / item).is_file() for item in required):
        raise ValueError("Approved source lacks required focused tests or DEV Compose files")
    env = {
        "PATH": os.environ["PATH"],
        "POSTGRES_PASSWORD": "isolated-validation-placeholder",
        "FRESHFIRST_AUTH_SECRET": "isolated-validation-placeholder-at-least-32-characters",
        "FRESHFIRST_IMAGE": "local/validation@sha256:" + "0" * 64,
    }
    command = ["docker", "compose", "--project-directory", str(source_dir)]
    for path in required[:3]:
        command += ["-f", str(source_dir / path)]
    result = subprocess.run(
        command + ["config", "--format", "json"],
        env=env,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if result.returncode:
        raise ValueError("Approved source DEV Compose validation failed")
    telemetry_disabled(json.loads(result.stdout))


def main():
    try:
        mode = sys.argv[1]
        if mode == "inputs":
            source = dispatch_source(
                json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()),
                os.environ["GITHUB_REF"],
                os.environ["GITHUB_SHA"],
            )
            require_main_ancestor(Path(sys.argv[2]), source)
            with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
                stream.write(f"source_sha={source}\n")
        elif mode == "source":
            validate_source(Path(sys.argv[2]).resolve())
        elif mode == "plan":
            telemetry_disabled(json.load(sys.stdin))
        else:
            raise ValueError("Unknown admission mode")
    except (KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired):
        raise SystemExit("Manual DEV admission failed; stop without repairs") from None


if __name__ == "__main__":
    main()
