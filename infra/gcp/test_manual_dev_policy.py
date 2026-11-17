"""Offline focused admission cases; no application, cloud, Docker or scheduler."""

import base64
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "policy", Path(__file__).with_name("manual-dev-policy.py")
)
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)
SHA = "a" * 40


class ManualDevPolicyTests(unittest.TestCase):
    def event(self, **inputs):
        return {"inputs": {"deploy_dev": True, "source_sha": SHA, **inputs}}

    def test_only_explicit_main_dispatch_with_exact_source(self):
        self.assertEqual(POLICY.dispatch_source(self.event(), "refs/heads/main", SHA), SHA)
        for source in ("main", SHA[:7], "a" * 39, "a" * 41, "$(touch unsafe)", "A" * 40):
            with self.subTest(source=source), self.assertRaises(ValueError):
                POLICY.dispatch_source(self.event(source_sha=source), "refs/heads/main", SHA)
        for ref in ("refs/heads/feature/render-deployment", "refs/tags/main"):
            with self.assertRaises(ValueError):
                POLICY.dispatch_source(self.event(), ref, SHA)

    def test_modes_are_mutually_exclusive(self):
        for key in ("preflight", "publish_test_image", "deploy", "dev_run_id", "digest"):
            with self.subTest(mode=key), self.assertRaises(ValueError):
                POLICY.dispatch_source(self.event(**{key: "true"}), "refs/heads/main", SHA)
        with self.assertRaises(ValueError):
            POLICY.dispatch_source(self.event(deploy_dev=False), "refs/heads/main", SHA)

    def test_feature_commit_cannot_bypass_main_ancestry(self):
        with patch.dict("os.environ", GITHUB_SHA=SHA):
            with patch.object(POLICY.subprocess, "run") as run:
                run.return_value.returncode = 1
                with self.assertRaises(ValueError):
                    POLICY.require_main_ancestor(Path("control"), SHA)
                self.assertEqual(run.call_args.args[0][-2:], [SHA, "origin/main"])
                self.assertEqual(run.call_args.kwargs["timeout"], 10)

    def test_only_disabled_dev_plan_without_credentials_is_accepted(self):
        for enabled in ("false", False):
            POLICY.telemetry_disabled(
                {"services": {"app": {"environment": {"FRESHFIRST_TELEMETRY_ENABLED": enabled}}}}
            )
        for enabled in ("true", True, "1", "", None):
            with self.subTest(enabled=enabled), self.assertRaises(ValueError):
                POLICY.telemetry_disabled(
                    {
                        "services": {
                            "app": {"environment": {"FRESHFIRST_TELEMETRY_ENABLED": enabled}}
                        }
                    }
                )
        for name in POLICY.HEADER_NAMES:
            with self.subTest(name=name), self.assertRaises(ValueError):
                POLICY.telemetry_disabled({"services": {"app": {"environment": {name: "dummy"}}}})

    def test_credential_mounts_rejected(self):
        for target in ("/run/secrets/freshfirst_otlp_headers", "/private/otlp-headers"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                POLICY.telemetry_disabled({"services": {"app": {"volumes": [{"target": target}]}}})
        with self.assertRaises(ValueError):
            POLICY.telemetry_disabled({"services": {"app": {"secrets": ["headers"]}}})

    def test_focused_allowlist_excludes_real_exporters_and_full_suite(self):
        self.assertEqual(len(POLICY.FOCUSED_TESTS), 4)
        self.assertTrue(all(item.startswith("tests/test_") for item in POLICY.FOCUSED_TESTS))
        self.assertFalse(
            any("outages" in item or "collector" in item for item in POLICY.FOCUSED_TESTS)
        )

    def test_workflow_gate_precedes_cloud_and_production_stays_held(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/gcp.yml").read_text()
        gate = workflow.split("  manual-dev-gate:\n", 1)[1].split("  build-dev:\n", 1)[0]
        self.assertNotIn("id-token: write", gate)
        self.assertNotIn("google-github-actions/auth", gate)
        self.assertIn("ref: ${{ github.sha }}", gate)
        self.assertIn("30s uv run --locked --no-sync pytest", gate)
        self.assertIn("needs.manual-dev-gate.result == 'success'", workflow)
        self.assertIn("needs.manual-dev-gate.result == 'skipped'", workflow)
        self.assertIn("if: false && github.event_name", workflow.split("  promote-production:")[1])
        for selection in POLICY.FOCUSED_TESTS:
            self.assertIn(selection, gate)

    def test_host_gate_fails_closed_using_only_synthetic_read_only_commands(self):
        bash = r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else shutil.which("bash")
        if not bash or not Path(bash).exists():
            self.skipTest("Bash is required for the focused synthetic host test")
        root = Path(__file__).resolve().parents[2]
        policy = base64.b64encode((root / "infra/gcp/manual-dev-policy.py").read_bytes()).decode()
        for failure in ("", "plan", "env", "mount", "config"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                (folder / "sudo").write_text(
                    '#!/bin/sh\n[ "$1" = -n ] || exit 1\nshift\nexec "$@"\n'
                )
                (folder / "python3").write_text('#!/bin/sh\nexec "$TEST_PYTHON" "$@"\n')
                (folder / "docker").write_text("""#!/bin/sh
echo "$1" >> "$CALL_LOG"
case "$1" in
 compose)
   [ "$FAILURE" != config ] || exit 1
   cat >/dev/null
   if [ "$FAILURE" = plan ]; then
     echo '{"services":{"app":{"environment":{"FRESHFIRST_TELEMETRY_ENABLED":"true"}}}}'
   else echo '{"services":{"app":{"environment":{"FRESHFIRST_TELEMETRY_ENABLED":"false"}}}}'; fi;;
 ps) echo dev-app;;
 inspect)
   case "$3" in
     *Config.Env*) [ "$FAILURE" != env ] || printf unsafe;;
     *Mounts*) [ "$FAILURE" != mount ] || printf /run/secrets/freshfirst_otlp_headers;;
     *) exit 1;;
   esac;;
 *) exit 1;;
esac
""")
                for script in folder.iterdir():
                    script.chmod(0o755)
                prefix = folder.as_posix()
                if os.name == "nt":
                    prefix = "/" + prefix[0].lower() + prefix[2:]
                result = subprocess.run(
                    [
                        bash,
                        "-c",
                        f'export PATH="{prefix}:$PATH"; '
                        'bash infra/gcp/manual-dev-host-check.sh after "$POLICY"',
                    ],
                    cwd=root,
                    env={
                        **os.environ,
                        "POLICY": policy,
                        "FAILURE": failure,
                        "TEST_PYTHON": str(Path(__import__("sys").executable)),
                        "CALL_LOG": str(folder / "calls"),
                    },
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(result.returncode == 0, not failure, result.stderr)
                self.assertTrue(
                    set((folder / "calls").read_text().splitlines()) <= {"compose", "ps", "inspect"}
                )


if __name__ == "__main__":
    unittest.main()
