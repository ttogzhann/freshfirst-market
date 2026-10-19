import pytest
from conftest import pantry


@pytest.mark.parametrize(
    "patch",
    [
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": "2"},
        {"quantity": True},
        {"quantity": None},
        {"quantity": 0.0001},
        {"unit": "kg"},
        {"unit": "cup"},
        {"expiry_date": "2026-02-30"},
        {"expiry_date": "2026-11-01T00:00:00"},
        {"expiry_date": 1793491200},
        {"ingredient_id": "unknown"},
    ],
)
def test_invalid_pantry_requests(client, patch):
    body = {
        "ingredient_id": "egg",
        "quantity": 1,
        "unit": "pcs",
        "expiry_date": "2026-11-01",
    } | patch
    response = client.post("/api/pantry", json=body)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert client.get("/api/pantry").json() == []


@pytest.mark.parametrize("servings", [0, 9, 1.5, True, "2", None])
def test_invalid_servings(client, servings):
    response = client.post(
        "/api/basket/items", json={"recipe_id": "rec_test1", "servings": servings}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "url", ["/api/recipes/absent", "/api/recipes/rec_test1?servings=9", "/api/recipes?sort=unknown"]
)
def test_read_errors(client, url):
    assert client.get(url).status_code in [404, 422]


@pytest.mark.parametrize("choices", ["not-json", "{}", "null", '[{"rule_id":"r1"}]'])
def test_invalid_substitution_query(client, choices):
    assert (
        client.get("/api/recipes/rec_test1", params={"substitutions": choices}).status_code == 422
    )


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/basket/items/nope", {"servings": 2}),
        ("/api/shopping-list/items/nope", {"quantity": 2}),
    ],
)
def test_missing_patch_resources(client, path, body):
    response = client.patch(path, json=body)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_json_and_required_field_errors(client):
    assert client.post("/api/pantry", json={}).status_code == 422
    assert (
        client.post(
            "/api/pantry", content="{bad", headers={"content-type": "application/json"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/pantry",
            content='{"ingredient_id":"egg","quantity":NaN,"unit":"pcs","expiry_date":"2026-11-01"}',
            headers={"content-type": "application/json"},
        ).status_code
        == 422
    )


def test_pantry_merge_conflict_and_duplicate_edit(client):
    a = pantry(client, "flour", 1, "kg")
    assert pantry(client, "flour", 500)["quantity"] == 1500
    response = client.post(
        "/api/pantry",
        json={"ingredient_id": "flour", "quantity": 1, "unit": "g", "expiry_date": "2026-11-02"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "EXPIRY_CONFLICT"
    b = pantry(client, "egg", 3, "pcs")
    response = client.put(
        f"/api/pantry/{b['id']}",
        json={"ingredient_id": "flour", "quantity": 1, "unit": "g", "expiry_date": "2026-11-01"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_INGREDIENT"
    assert client.delete(f"/api/pantry/{a['id']}").status_code == 204
    assert client.delete(f"/api/pantry/{a['id']}").status_code == 404


def test_null_patch_rejected_and_empty_patch_kept(client):
    b = client.post("/api/basket/items", json={"recipe_id": "rec_test1", "servings": 1}).json()
    assert client.patch(f"/api/basket/items/{b['id']}", json={}).json() == b
    assert client.patch(f"/api/basket/items/{b['id']}", json={"servings": None}).status_code == 422
    s = client.post(
        "/api/shopping-list/items", json={"label": "Soap", "quantity": 1, "unit": "pcs"}
    ).json()
    assert (
        client.patch(f"/api/shopping-list/items/{s['id']}", json={"purchased": None}).status_code
        == 422
    )
    assert (
        client.patch(f"/api/shopping-list/items/{s['id']}", json={"purchased": "false"}).status_code
        == 422
    )


def test_unexpected_errors_use_contract_envelope(client, service, monkeypatch):
    def fail():
        raise RuntimeError("Private failure detail")

    monkeypatch.setattr(service, "dashboard", fail)
    response = client.get("/api/dashboard")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "Private failure" not in response.text
