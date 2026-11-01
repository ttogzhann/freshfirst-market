"""HTTP integration coverage for the production Docker Compose stack.

Run from the repository root with:

    uv run --project backend --locked pytest -q tests/test_compose_integration.py

The test owns a unique Compose project, environment file, database and named
volume. It never uses the developer's Compose project or a checked-in secret.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "compose.yaml"
COMPOSE = shutil.which("docker.exe") or shutil.which("docker")


def _redact(value: str, *secrets: str) -> str:
    result = value
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[redacted]")
    return result[-2000:]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ComposeRuntime:
    def __init__(self):
        if COMPOSE is None:
            pytest.fail("Docker CLI is required for Compose integration tests")
        self.project = f"freshfirst-integration-{uuid.uuid4().hex[:12]}"
        self.port = _free_port()
        self.password = f"pw-{uuid.uuid4().hex}-compose"
        self.auth_secret = f"auth-{uuid.uuid4().hex}-compose-secret"
        self.db_name = f"freshfirst_{uuid.uuid4().hex[:12]}"
        self.db_user = f"freshfirst_{uuid.uuid4().hex[:12]}"
        self.env_directory = Path(tempfile.mkdtemp(prefix="freshfirst-compose-"))
        self.env_file = self.env_directory / "compose.env"
        self.env_file.write_text(
            "\n".join(
                (
                    f"POSTGRES_DB={self.db_name}",
                    f"POSTGRES_USER={self.db_user}",
                    f"POSTGRES_PASSWORD={self.password}",
                    f"FRESHFIRST_AUTH_SECRET={self.auth_secret}",
                    f"FRESHFIRST_TRUSTED_ORIGINS=http://127.0.0.1:{self.port}",
                    f"FRESHFIRST_PORT={self.port}",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        self.base_url = f"http://127.0.0.1:{self.port}"

    def command(self, *args: str) -> list[str]:
        return [
            COMPOSE,
            "compose",
            "--env-file",
            str(self.env_file),
            "-p",
            self.project,
            "-f",
            str(COMPOSE_FILE),
            *args,
        ]

    def run(self, *args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            self.command(*args),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if completed.returncode:
            command = " ".join(self.command(*args)[:3] + ["..."])
            output = _redact(
                completed.stderr or completed.stdout,
                self.password,
                self.auth_secret,
                self.db_name,
                self.db_user,
            )
            raise RuntimeError(
                f"{command} failed with exit {completed.returncode}: {output}"
            )
        return completed

    def start(self):
        self.run("up", "--build", "-d", timeout=600)
        self.run(
            "exec", "-T", "db", "pg_isready", "-U", self.db_user, "-d", self.db_name
        )
        self.wait_for_health()
        postgres_url_check = (
            'case "$DATABASE_URL" in '
            "postgresql+psycopg://*db:5432/*) printf postgres;; *) exit 1;; esac"
        )
        self.run(
            "exec",
            "-T",
            "app",
            "sh",
            "-c",
            postgres_url_check,
        )

    def wait_for_health(self):
        deadline = time.monotonic() + 120
        last_error = ""
        while time.monotonic() < deadline:
            try:
                with urlopen(f"{self.base_url}/healthz", timeout=5) as response:
                    if response.status == 200:
                        return
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                last_error = str(error)
            time.sleep(2)
        raise RuntimeError(f"Compose app did not become healthy: {_redact(last_error)}")

    def recreate_app(self):
        self.run("up", "-d", "--force-recreate", "app", timeout=180)
        self.wait_for_health()

    def cleanup(self):
        try:
            self.run("down", "-v", "--remove-orphans", timeout=120)
        finally:
            shutil.rmtree(self.env_directory, ignore_errors=True)


class HttpClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.cookie = ""
        self.csrf = ""

    def request(self, method: str, path: str, payload=None, expected=None):
        headers = {"Origin": self.base_url, "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.csrf and method not in {"GET", "HEAD"}:
            headers["X-CSRF-Token"] = self.csrf
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path, data=body, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=20) as response:
                status = response.status
                raw = response.read()
                set_cookie = response.headers.get("Set-Cookie", "")
        except HTTPError as error:
            status = error.code
            raw = error.read()
            set_cookie = error.headers.get("Set-Cookie", "")
        except (URLError, TimeoutError) as error:
            raise AssertionError(
                f"HTTP {method} {path} failed: {_redact(str(error))}"
            ) from error
        match = re.search(r"(?:^|;)\s*(freshfirst_session=[^;]+)", set_cookie)
        if match:
            self.cookie = match.group(1)
        text = raw.decode("utf-8")
        try:
            value = json.loads(text) if text else None
        except json.JSONDecodeError:
            value = text
        if expected is not None and status not in expected:
            raise AssertionError(
                f"HTTP {method} {path} returned {status}, expected {expected}"
            )
        if isinstance(value, dict) and value.get("csrf_token"):
            self.csrf = value["csrf_token"]
        return status, value

    def restore(self):
        status, value = self.request("GET", "/api/auth/session", expected={200})
        assert status == 200 and value["csrf_token"]
        return value

    def register(self, email: str, password: str):
        status, value = self.request(
            "POST",
            "/api/auth/register",
            {"email": email, "password": password},
            expected={201},
        )
        assert status == 201 and value["user"]["email"] == email
        return value


def _add_pantry(
    client: HttpClient, ingredient_id: str, quantity: int, unit: str, expiry: str
):
    return client.request(
        "POST",
        "/api/pantry",
        {
            "ingredient_id": ingredient_id,
            "quantity": quantity,
            "unit": unit,
            "expiry_date": expiry,
        },
        expected={200},
    )[1]


def test_real_compose_postgres_workflow():
    runtime = ComposeRuntime()
    expiry = (date.today() + timedelta(days=7)).isoformat()
    password = f"Integration-{uuid.uuid4().hex}!"
    email = f"owner-{uuid.uuid4().hex[:12]}@example.com"
    isolated_email = f"other-{uuid.uuid4().hex[:12]}@example.com"
    owner = HttpClient(runtime.base_url)
    other = HttpClient(runtime.base_url)
    try:
        runtime.start()
        if os.getenv("FRESHFIRST_COMPOSE_TEST_FORCE_FAILURE") == "1":
            raise AssertionError("forced cleanup probe")

        owner.restore()
        owner.register(email, password)
        recipes = owner.request("GET", "/api/recipes", expected={200})[1]
        assert any(recipe["id"] == "rec_53177" for recipe in recipes)

        _add_pantry(owner, "pasta", 500, "g", expiry)
        basket_status, basket_item = owner.request(
            "POST",
            "/api/basket/items",
            {"recipe_id": "rec_53177", "servings": 1},
            expected={200},
        )
        assert basket_status == 200 and basket_item["recipe_id"] == "rec_53177"
        shopping = owner.request(
            "POST", "/api/shopping-list/generate", {}, expected={200}
        )[1]
        assert {item["ingredient_id"] for item in shopping} >= {
            "chorizo",
            "parsley",
            "pepper",
            "olive_oil",
            "parmesan",
        }

        before_failed_cook = owner.request("GET", "/api/pantry", expected={200})[1]
        failed_status, _ = owner.request(
            "POST",
            "/api/cooking/confirm",
            {"recipe_id": "rec_53177", "servings": 1, "substitutions": []},
            expected={409},
        )
        assert failed_status == 409
        assert (
            owner.request("GET", "/api/pantry", expected={200})[1] == before_failed_cook
        )
        assert owner.request("GET", "/api/cooking/history", expected={200})[1] == []

        for ingredient_id, quantity, unit in (
            ("chorizo", 80, "g"),
            ("parsley", 20, "g"),
            ("pepper", 2, "pcs"),
            ("olive_oil", 30, "ml"),
            ("parmesan", 50, "g"),
        ):
            _add_pantry(owner, ingredient_id, quantity, unit, expiry)
        preview = owner.request(
            "POST",
            "/api/cooking/preview",
            {"recipe_id": "rec_53177", "servings": 1, "substitutions": []},
            expected={200},
        )[1]
        assert preview["can_cook"] is True
        assert (
            owner.request(
                "POST",
                "/api/cooking/confirm",
                {"recipe_id": "rec_53177", "servings": 1, "substitutions": []},
                expected={201},
            )[0]
            == 201
        )
        assert len(owner.request("GET", "/api/cooking/history", expected={200})[1]) == 1

        other.restore()
        other.register(isolated_email, password)
        assert other.request("GET", "/api/pantry", expected={200})[1] == []
        assert other.request("GET", "/api/cooking/history", expected={200})[1] == []

        runtime.recreate_app()
        restored = owner.restore()
        assert restored["authenticated"] is True
        assert restored["user"]["email"] == email
        assert len(owner.request("GET", "/api/cooking/history", expected={200})[1]) == 1
        assert len(owner.request("GET", "/api/basket", expected={200})[1]["items"]) == 1
        assert owner.request("GET", "/api/pantry", expected={200})[1]
    finally:
        runtime.cleanup()
