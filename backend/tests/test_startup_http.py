"""FF21: normal app startup and restart over real HTTP, without external access."""

import os
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
from conftest import ContractClient, register_test_account

from app.main import create_app
from app.services.fresh import FreshService
from app.services.importer import PackagedMealSource, TheMealDBSource


@contextmanager
def normal_server(database_url, directory, offline=True):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    script = """
import socket, sys, uvicorn
original = socket.socket.connect
def blocked(self, address):
    if address[0] not in ('127.0.0.1', '::1'):
        raise OSError('FF21 external network deliberately blocked')
    return original(self, address)
if sys.argv[2] == 'offline':
    socket.socket.connect = blocked
uvicorn.run('app.main:app', host='127.0.0.1', port=int(sys.argv[1]))
"""
    started = time.monotonic()
    with (directory / f"server-{port}.log").open("w+", encoding="utf8") as log:
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(port), "offline" if offline else "live"],
            cwd=Path(__file__).resolve().parents[1],
            env={
                **os.environ,
                "DATABASE_URL": database_url,
                "FRESHFIRST_AUTH_SECRET": "isolated backend restart test secret 32 bytes",
            },
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client:
                while True:
                    try:
                        response = client.get("/api/ingredients")
                        response.raise_for_status()
                        break
                    except httpx.HTTPError:
                        assert process.poll() is None, "Backend stopped before readiness"
                        assert time.monotonic() - started < 15, "Startup exceeded 15 seconds"
                        time.sleep(0.05)
                yield client, time.monotonic() - started
        finally:
            process.terminate()
            process.wait(timeout=10)
            log.seek(0)
            assert "15 recipes" not in log.read()


def saved_http_state(client):
    recipes = client.get("/api/recipes").json()
    return {
        "recipes": sorted(
            [client.get(f"/api/recipes/{r['id']}").json() for r in recipes],
            key=lambda r: r["id"],
        ),
        "basket": client.get("/api/basket").json(),
        "pantry": client.get("/api/pantry").json(),
    }


def test_normal_http_offline_startup_restart_and_failure(tmp_path):
    database = tmp_path / "normal.db"
    url = f"sqlite:///{database}"
    session_token = None
    with normal_server(url, tmp_path) as (client, elapsed):
        assert elapsed < 15
        register_test_account(client, "startup@example.com")
        session_token = client.cookies.get("freshfirst_session")
        details = saved_http_state(client)["recipes"]
        expected = {
            "53137": {"milk": 1000, "sugar": 300, "baking_powder": 1.25, "vanilla": 5},
            "52776": {
                "plain_chocolate": 250,
                "butter": 175,
                "milk": 30,
                "egg": 5,
                "sugar": 175,
                "flour": 125,
            },
        }
        assert len(details) == 15
        for recipe in details:
            assert recipe["id"] == f"rec_{recipe['external_id']}"
            assert recipe["base_servings"] == 1
            assert all(recipe[f] for f in ("title", "category", "instructions", "image_url"))
            if recipe["external_id"] in expected:
                assert {
                    i["ingredient_id"]: i["quantity"] for i in recipe["ingredients"]
                } == expected[recipe["external_id"]]
        for external_id, scale in (("53137", 2), ("52776", 3)):
            response = client.post(
                "/api/basket/items", json={"recipe_id": f"rec_{external_id}", "servings": scale}
            )
            assert response.status_code == 200
        before = saved_http_state(client)
        response = client.post("/api/recipes/import")
        assert response.status_code == 502
        assert response.json() == {
            "status": 502,
            "code": "SOURCE_UNAVAILABLE",
            "message": "TheMealDB is unavailable or returned invalid data. "
            "Previously imported recipes are unchanged.",
        }
        assert saved_http_state(client) == before
    with normal_server(url, tmp_path) as (client, elapsed):
        assert elapsed < 15
        client.cookies.set(
            "freshfirst_session",
            session_token,
            domain="127.0.0.1",
            path="/api",
        )
        restored = client.get("/api/auth/session")
        assert restored.json()["authenticated"] is True
        client.headers.update(
            {
                "X-CSRF-Token": restored.json()["csrf_token"],
                "Origin": "http://localhost:5173",
            }
        )
        assert saved_http_state(client) == before
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 15
        assert connection.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[0] == 102
        assert (
            connection.execute("SELECT COUNT(*) FROM ingredients WHERE id='milk'").fetchone()[0]
            == 1
        )


def test_actual_adapter_captured_import_preserves_basket_and_ids():
    captures = list(PackagedMealSource().meals())

    def respond(request):
        return httpx.Response(
            200, json={"meals": captures if request.url.params["f"] == "a" else None}
        )

    service = FreshService(seed=False)
    with httpx.Client(transport=httpx.MockTransport(respond)) as upstream:
        service.source = TheMealDBSource(upstream)
        with ContractClient(create_app(service)) as client:
            register_test_account(client, "import@example.com")
            assert (
                client.post(
                    "/api/basket/items", json={"recipe_id": "rec_53137", "servings": 4}
                ).status_code
                == 200
            )
            before = saved_http_state(client)
            for _ in range(2):
                response = client.post("/api/recipes/import")
                assert response.status_code == 200
                assert response.json() == {
                    "imported": 0,
                    "updated": 15,
                    "skipped": [],
                    "total_recipes": 15,
                }
                assert saved_http_state(client) == before
