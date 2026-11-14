"""Durable evidence for the original Issue #65 acceptance criteria."""

from datetime import date

from conftest import Source, meal, register_test_account
from fastapi.testclient import TestClient

from app.models import PantryInput
from app.services.fresh import FreshService
from app.store import SQLiteStore


def test_pending_resolution_states_are_excluded_from_all_inventory_calculations(client, service):
    unknown = client.post(
        "/api/pantry",
        json={"label": "dragonfruit", "quantity": 4, "unit": "g", "expiry_date": "2026-11-01"},
    ).json()
    suggested = client.post(
        "/api/pantry",
        json={"label": "molok", "quantity": 100, "unit": "ml", "expiry_date": "2026-11-01"},
    ).json()
    assert unknown["resolution_status"] == "unresolved"
    assert suggested["resolution_status"] == "suggested"

    account_service = service.for_owner(client.user_id)
    assert account_service.stock() == {}

    basket = client.post("/api/basket/items", json={"recipe_id": "rec_test1", "servings": 1}).json()
    assert basket["recipe_id"] == "rec_test1"
    shopping = client.post("/api/shopping-list/generate", json={}).json()
    assert {(item["ingredient_id"], item["quantity"]) for item in shopping} == {
        ("pasta", 100),
        ("milk", 100),
        ("butter", 10),
    }
    assert client.get("/api/recipes/rec_test1").json()["suggestions"] == []

    before = client.get("/api/pantry").json()
    cook = client.post(
        "/api/cooking/confirm",
        json={"recipe_id": "rec_test1", "servings": 1, "substitutions": []},
    )
    assert cook.status_code == 409
    assert cook.json()["code"] == "INSUFFICIENT_STOCK"
    assert client.get("/api/pantry").json() == before
    assert client.get("/api/cooking/history").json() == []


def test_pending_resolution_states_survive_file_backed_restart(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'issue65-restart.db'}"
    first = FreshService(
        store=SQLiteStore(database_url),
        source=Source([meal()]),
        today=lambda: date(2026, 10, 20),
        seed=False,
    )
    first.import_recipes()
    first.create_pantry(
        PantryInput(
            label="dragonfruit",
            quantity=4,
            unit="g",
            expiry_date="2026-11-01",
        )
    )
    first.store.close()

    restarted = FreshService(
        store=SQLiteStore(database_url),
        source=Source([meal()]),
        today=lambda: date(2026, 10, 20),
        seed=False,
    )
    restored = restarted.list_pantry()
    assert len(restored) == 1
    assert restored[0].original_label == "dragonfruit"
    assert restored[0].resolution_status == "unresolved"
    assert restored[0].ingredient_id is None
    assert restarted.stock() == {}
    assert restarted.get_recipe("rec_test1").match.covered == 0
    restarted.store.close()


def test_pantry_owner_scoping_covers_reload_and_crud(client):
    created = client.post(
        "/api/pantry",
        json={
            "ingredient_id": "egg",
            "quantity": 2,
            "unit": "pcs",
            "expiry_date": "2026-11-01",
        },
    ).json()
    other = client.__class__(client.app, raise_server_exceptions=False)
    with other:
        register_test_account(other, "issue65-owner@example.com")
        assert other.get("/api/pantry").json() == []
        assert (
            other.put(
                f"/api/pantry/{created['id']}",
                json={
                    "ingredient_id": "egg",
                    "quantity": 3,
                    "unit": "pcs",
                    "expiry_date": "2026-11-01",
                },
            ).status_code
            == 404
        )
        assert other.delete(f"/api/pantry/{created['id']}").status_code == 404
    assert client.get("/api/pantry").json()[0]["quantity"] == 2


def test_invalid_origin_and_strict_input_fail_without_mutation(client):
    before = client.get("/api/pantry").json()
    raw = TestClient(client.app, raise_server_exceptions=False)
    raw.cookies.update(client.cookies)
    raw.headers.update(
        {
            "Origin": "https://evil.example",
            "X-CSRF-Token": client.headers["X-CSRF-Token"],
        }
    )
    denied = raw.post(
        "/api/pantry",
        json={
            "ingredient_id": "egg",
            "quantity": 1,
            "unit": "pcs",
            "expiry_date": "2026-11-01",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "CSRF_FAILED"
    for body in (
        {"label": "new food", "quantity": 0, "unit": "g", "expiry_date": "2026-11-01"},
        {"label": "new food", "quantity": -1, "unit": "g", "expiry_date": "2026-11-01"},
        {"label": "new food", "quantity": 1, "unit": "cup", "expiry_date": "2026-11-01"},
        {"label": "new food", "quantity": 1, "unit": "g", "expiry_date": "2026-02-30"},
    ):
        response = client.post("/api/pantry", json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
    assert client.get("/api/pantry").json() == before
