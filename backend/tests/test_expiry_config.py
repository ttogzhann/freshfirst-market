import os
import subprocess
import sys
from datetime import date

import pytest
from conftest import ContractClient, Source, meal, pantry

from app.config import expiry_days
from app.main import create_app
from app.services.fresh import FreshService


@pytest.mark.parametrize("raw,expected", [(None, 3), ("0", 0), ("3", 3), ("5", 5), (5, 5)])
def test_threshold_configuration(raw, expected):
    assert expiry_days(raw) == expected


@pytest.mark.parametrize("raw,expected", [(None, 3), ("0", 0), ("5", 5)])
def test_normal_app_reads_environment(tmp_path, raw, expected):
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'valid.db'}"}
    environment.pop("FRESHFIRST_EXPIRY_DAYS", None)
    if raw is not None:
        environment["FRESHFIRST_EXPIRY_DAYS"] = raw
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from app.main import app; "
                "print(app.state.service.expiry_days); "
                "app.state.service.store.close()"
            ),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(expected)


@pytest.mark.parametrize(
    "raw",
    [
        "-1",
        "1.5",
        "abc",
        "NaN",
        "Infinity",
        "",
        " ",
        -1,
        1.5,
        float("nan"),
        float("inf"),
        True,
        9007199254740992,
    ],
)
def test_invalid_direct_service_configuration_is_named_and_precedes_database(raw):
    with pytest.raises(ValueError, match="FRESHFIRST_EXPIRY_DAYS"):
        FreshService(expiry_days=raw)


@pytest.mark.parametrize("raw", ["-1", "1.5", "abc", "NaN", "Infinity", ""])
def test_invalid_normal_app_startup_fails_clearly_without_database(tmp_path, raw):
    path = tmp_path / "must-not-exist.db"
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        env={**os.environ, "DATABASE_URL": f"sqlite:///{path}", "FRESHFIRST_EXPIRY_DAYS": raw},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "FRESHFIRST_EXPIRY_DAYS must be a nonnegative whole-day integer" in result.stderr
    assert not path.exists()


@pytest.mark.parametrize(
    "threshold,count,urgent",
    [(0, 1, ["Milk"]), (3, 2, ["Milk", "Butter"]), (5, 4, ["Milk", "Butter", "Sugar", "Flour"])],
)
def test_configured_http_boundaries_and_expired_stock(threshold, count, urgent):
    service = FreshService(seed=False, today=lambda: date(2026, 10, 20), expiry_days=threshold)
    service.source = Source(
        [
            meal(
                "boundary",
                ingredients=[
                    ("Pasta", "100g"),
                    ("Milk", "100ml"),
                    ("Butter", "10g"),
                    ("Sugar", "10g"),
                    ("Flour", "10g"),
                    ("Rice", "10g"),
                ],
            )
        ]
    )
    service.import_recipes()
    with ContractClient(create_app(service, startup_import=False)) as client:
        for identity, quantity, unit, expiry in [
            ("pasta", 100, "g", "2026-10-19"),
            ("milk", 100, "ml", "2026-10-20"),
            ("butter", 10, "g", "2026-10-23"),
            ("sugar", 10, "g", "2026-10-24"),
            ("flour", 10, "g", "2026-10-25"),
            ("rice", 10, "g", "2026-10-26"),
        ]:
            pantry(client, identity, quantity, unit, expiry)
        dashboard = client.get("/api/dashboard").json()
        assert (dashboard["expired"], dashboard["expiring_soon"]) == (1, count)
        detail = client.get("/api/recipes/rec_boundary").json()
        assert detail["match"]["expiring_used"] == urgent
        assert detail["match"]["covered"] == 5
        lines = {line["ingredient_id"]: line for line in detail["lines"]}
        assert lines["pasta"]["available"] == 0
        assert lines["milk"]["available"] == 100
        client.post("/api/basket/items", json={"recipe_id": "rec_boundary", "servings": 1})
        shopping = client.post("/api/shopping-list/generate", json={}).json()
        assert [(row["ingredient_id"], row["quantity"]) for row in shopping] == [("pasta", 100)]
        request = {"recipe_id": "rec_boundary", "servings": 1, "substitutions": []}
        assert not client.post("/api/cooking/preview", json=request).json()["can_cook"]
        before = service.state
        assert client.post("/api/cooking/confirm", json=request).status_code == 409
        assert service.state == before
        # Still editable; insufficient near-expiry stock must not claim a usable ingredient.
        item = next(
            row for row in client.get("/api/pantry").json() if row["ingredient_id"] == "milk"
        )
        assert (
            client.put(
                f"/api/pantry/{item['id']}",
                json={
                    "ingredient_id": "milk",
                    "quantity": 1,
                    "unit": "ml",
                    "expiry_date": "2026-10-20",
                },
            ).status_code
            == 200
        )
        assert (
            "Milk" not in client.get("/api/recipes/rec_boundary").json()["match"]["expiring_used"]
        )
