"""Opt-in FF21 HTTP smoke. Live network occurs only with --live, never in pytest."""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("FRESHFIRST_AUTH_SECRET", "isolated startup smoke test secret 32 bytes")

from conftest import register_test_account  # noqa: E402
from test_startup_http import normal_server, saved_http_state  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "smoke.db"
    if database.exists():
        parser.error("Use a fresh directory; smoke.db already exists")
    result = {"date_utc": datetime.now(timezone.utc).isoformat(), "live": args.live}
    session_token = None
    with normal_server(f"sqlite:///{database}", directory, offline=not args.live) as (
        client,
        elapsed,
    ):
        result["startup_seconds"] = elapsed
        register_test_account(client, "smoke@example.com")
        session_token = client.cookies.get("freshfirst_session")
        for source, scale in (("53137", 2), ("52776", 3)):
            client.post(
                "/api/basket/items", json={"recipe_id": f"rec_{source}", "servings": scale}
            ).raise_for_status()
        before = saved_http_state(client)
        started = time.monotonic()
        response = client.post("/api/recipes/import", timeout=90)
        after = saved_http_state(client)
        result.update(
            status=response.status_code,
            report=response.json(),
            import_seconds=time.monotonic() - started,
            before=before,
            after=after,
        )
    with normal_server(f"sqlite:///{database}", directory) as (client, elapsed):
        result["restart_seconds"] = elapsed
        client.cookies.set("freshfirst_session", session_token, domain="127.0.0.1", path="/api")
        restored = client.get("/api/auth/session")
        assert restored.json()["authenticated"] is True
        client.headers.update(
            {
                "X-CSRF-Token": restored.json()["csrf_token"],
                "Origin": "http://localhost:5173",
            }
        )
        result["restart_state_equal"] = saved_http_state(client) == after
    (directory / "result.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("before", "after", "report")}))
    print(f"Full report/state: {directory / 'result.json'}")


if __name__ == "__main__":
    main()
