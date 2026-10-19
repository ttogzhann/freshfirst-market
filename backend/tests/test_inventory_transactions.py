from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from conftest import pantry

from app.errors import ServiceError
from app.models import CookRequest, ShoppingInput, ShoppingPatch, TransferInput


def test_purchase_requires_confirmation_and_is_idempotent(client):
    item = client.post(
        "/api/shopping-list/items", json={"label": "Eggs", "quantity": 6, "unit": "pcs"}
    ).json()
    path = f"/api/shopping-list/items/{item['id']}/transfer-to-pantry"
    data = {"quantity": 4, "expiry_date": "2026-11-01"}
    assert client.post(path, json=data).json()["code"] == "NOT_PURCHASED"
    client.patch(f"/api/shopping-list/items/{item['id']}", json={"purchased": True})
    assert client.get("/api/pantry").json() == []
    assert client.post(path, json=data).json()["transferred_to_pantry"]
    assert client.post(path, json=data).status_code == 200
    assert client.get("/api/pantry").json()[0]["quantity"] == 4
    assert (
        client.patch(f"/api/shopping-list/items/{item['id']}", json={"purchased": False}).json()[
            "code"
        ]
        == "ALREADY_TRANSFERRED"
    )


def test_conflicting_expiry_transfer_rolls_back_even_for_expired_stock(client):
    pantry(client, "egg", 2, "pcs", "2026-10-19")
    item = client.post(
        "/api/shopping-list/items", json={"label": "Eggs", "quantity": 6, "unit": "pcs"}
    ).json()
    client.patch(f"/api/shopping-list/items/{item['id']}", json={"purchased": True})
    response = client.post(
        f"/api/shopping-list/items/{item['id']}/transfer-to-pantry",
        json={"quantity": 6, "expiry_date": "2026-11-01"},
    )
    assert response.status_code == 409
    assert client.get("/api/pantry").json()[0]["quantity"] == 2
    assert not client.get("/api/shopping-list").json()[0]["transferred_to_pantry"]


def test_manual_noncatalog_transfer_and_bad_dates(client):
    item = client.post(
        "/api/shopping-list/items", json={"label": "Soap", "quantity": 1, "unit": "pcs"}
    ).json()
    client.patch(f"/api/shopping-list/items/{item['id']}", json={"purchased": True})
    path = f"/api/shopping-list/items/{item['id']}/transfer-to-pantry"
    assert client.post(path, json={"quantity": 1, "expiry_date": "2026-11-01"}).status_code == 422
    for expiry in ["2026-02-30", "2026-11-01T00:00:00", 1793491200]:
        assert client.post(path, json={"quantity": 1, "expiry_date": expiry}).status_code == 422


def test_cook_preview_then_revalidate_without_partial_deductions(client, service):
    for i, q, u in [("pasta", 100, "g"), ("milk", 100, "ml"), ("butter", 10, "g")]:
        pantry(client, i, q, u)
    req = {"recipe_id": "rec_test1", "servings": 1, "substitutions": []}
    before = deepcopy(service.state)
    assert client.post("/api/cooking/preview", json=req).json()["can_cook"]
    assert service.state == before
    milk = next(p for p in service.state.pantry.values() if p.ingredient_id == "milk")
    milk.expiry_date = service.today().replace(day=19)
    before = deepcopy(service.state)
    assert not client.post("/api/cooking/preview", json=req).json()["can_cook"]
    assert client.post("/api/cooking/confirm", json=req).json()["code"] == "INSUFFICIENT_STOCK"
    assert service.state == before


def test_successful_cooking_with_substitution_and_scaled_history(client):
    for i, q, u in [
        ("egg", 7, "pcs"),
        ("mushroom", 100, "g"),
        ("cheese", 60, "g"),
        ("butter", 20, "g"),
    ]:
        pantry(client, i, q, u)
    req = {
        "recipe_id": "rec_eggs",
        "servings": 2,
        "substitutions": [
            {
                "rule_id": "r8",
                "original_ingredient_id": "spinach",
                "substitute_ingredient_id": "mushroom",
            }
        ],
    }
    response = client.post("/api/cooking/confirm", json=req)
    assert response.status_code == 201
    consumed = {c["ingredient_id"]: c["quantity"] for c in response.json()["consumed"]}
    assert consumed == {"egg": 6, "mushroom": 100, "cheese": 60, "butter": 20}
    assert client.get("/api/pantry").json()[0]["quantity"] == 1
    assert len(client.get("/api/pantry").json()) == 1
    assert client.get("/api/cooking/history").json() == [response.json()]


def test_exception_after_deduction_rolls_back_inventory_and_history(service, monkeypatch):
    from app.models import PantryInput

    for i, q, u in [("pasta", 100, "g"), ("milk", 100, "ml"), ("butter", 10, "g")]:
        service.create_pantry(
            PantryInput(ingredient_id=i, quantity=q, unit=u, expiry_date="2026-11-01")
        )
    before = deepcopy(service.state)

    def fail_id(prefix):
        raise RuntimeError("Simulated history write failure")

    monkeypatch.setattr(service.store, "next_id", fail_id)
    with pytest.raises(RuntimeError):
        service.confirm_cook(CookRequest(recipe_id="rec_test1", servings=1, substitutions=[]))
    assert service.state == before


def test_concurrent_transfers_cannot_double_count(service):
    item = service.add_shopping(ShoppingInput(label="Eggs", quantity=6, unit="pcs"))
    service.update_shopping(item.id, ShoppingPatch(purchased=True))
    data = TransferInput(quantity=6, expiry_date="2026-11-01")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: service.transfer(item.id, data), range(12)))
    assert all(r.transferred_to_pantry for r in results)
    assert service.list_pantry()[0].quantity == 6


def test_concurrent_cooks_never_create_negative_stock(service):
    from app.models import PantryInput

    for i, q, u in [("pasta", 100, "g"), ("milk", 100, "ml"), ("butter", 10, "g")]:
        service.create_pantry(
            PantryInput(ingredient_id=i, quantity=q, unit=u, expiry_date="2026-11-01")
        )
    req = CookRequest(recipe_id="rec_test1", servings=1, substitutions=[])

    def cook(_):
        try:
            service.confirm_cook(req)
            return "success"
        except ServiceError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(cook, range(4)))
    assert results.count("success") == 1
    assert results.count("INSUFFICIENT_STOCK") == 3
    assert service.list_pantry() == []
    assert len(service.list_history()) == 1
