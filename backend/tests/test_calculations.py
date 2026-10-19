import json

from conftest import meal, pantry

from app.services.importer import normalize_meal


def test_matching_scaling_expiry_and_title_sort(client):
    pantry(client, "pasta", 0.1, "kg", "2026-10-22")
    pantry(client, "milk", 0.1, "l", "2026-10-19")
    recipes = client.get("/api/recipes").json()
    first = next(r for r in recipes if r["id"] == "rec_test1")
    assert first["match"] == {
        "score": 33,
        "covered": 1,
        "total": 3,
        "missing": ["Milk", "Butter"],
        "expiring_used": ["Pasta"],
    }
    detail = client.get("/api/recipes/rec_test1", params={"servings": 3}).json()
    assert detail["match"] == first["match"]  # Contract keeps base-serving match.
    lines = {line["ingredient_id"]: line for line in detail["lines"]}
    assert lines["pasta"]["required"] == 300
    assert lines["pasta"]["available"] == 100
    assert lines["milk"]["available"] == 0
    assert all(not line["sufficient"] for line in lines.values())
    titles = [r["title"] for r in client.get("/api/recipes?sort=title").json()]
    assert titles == sorted(titles)
    assert len(client.get("/api/recipes?query=%20milk%20&category=Pasta").json()) == 1
    assert client.get("/api/recipes?category=unknown").json() == []
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["total_items"] == 2
    assert dashboard["expiring_soon"] == 1
    assert dashboard["expired"] == 1
    assert all("Pasta" in r["match"]["expiring_used"] for r in dashboard["recommendations"])


def test_expiry_tie_breaker_inclusive_today_and_three_days(client, service):
    pantry(client, "pasta", 100, expiry="2026-10-23")
    pantry(client, "butter", 10, expiry="2026-10-20")
    pantry(client, "parmesan", 30, expiry="2026-10-24")
    result = client.get("/api/dashboard").json()
    assert result["expiring_soon"] == 2
    assert result["expired"] == 0
    recipes = client.get("/api/recipes").json()
    # test2 is fully covered and ranks ahead of test1's partial cover.
    assert recipes[0]["id"] == "rec_test2"


def test_shopping_aggregates_shared_stock_once_and_normalizes_units(client):
    pantry(client, "pasta", 0.15, "kg")
    pantry(client, "milk", 0.1, "l", "2026-10-19")
    for recipe_id in ["rec_test1", "rec_test2"]:
        client.post("/api/basket/items", json={"recipe_id": recipe_id, "servings": 1})
    list_before = client.get("/api/shopping-list").json()
    assert list_before == []
    shopping = client.post("/api/shopping-list/generate", json={}).json()
    quantities = {s["ingredient_id"]: s["quantity"] for s in shopping}
    assert quantities == {"pasta": 50, "milk": 100, "butter": 10, "parmesan": 30}
    totals = {line["ingredient_id"]: line for line in client.get("/api/basket").json()["totals"]}
    assert totals["pasta"]["required"] == 200
    assert totals["pasta"]["available"] == 150
    assert not totals["pasta"]["sufficient"]


def test_basket_upsert_and_substitution_choices(client):
    first = client.post("/api/basket/items", json={"recipe_id": "rec_eggs", "servings": 1}).json()
    assert (
        client.post("/api/basket/items", json={"recipe_id": "rec_eggs", "servings": 2}).json()["id"]
        == first["id"]
    )
    assert len(client.get("/api/basket").json()["items"]) == 1
    pantry(client, "mushroom", 200)
    detail = client.get("/api/recipes/rec_eggs", params={"servings": 2}).json()
    suggestion = next(s for s in detail["suggestions"] if s["rule"]["id"] == "r8")
    assert suggestion["required"] == 100
    assert detail["match"]["score"] == 0
    sub = {
        "rule_id": "r8",
        "original_ingredient_id": "spinach",
        "substitute_ingredient_id": "mushroom",
    }
    response = client.patch(f"/api/basket/items/{first['id']}", json={"substitutions": [sub]})
    assert response.status_code == 200
    totals = {
        line["ingredient_id"]: line["required"]
        for line in client.get("/api/basket").json()["totals"]
    }
    assert "spinach" not in totals
    assert totals["mushroom"] == 100
    shopping = client.post("/api/shopping-list/generate").json()
    assert all(s["ingredient_id"] not in ["spinach", "mushroom"] for s in shopping)
    detail = client.get(
        "/api/recipes/rec_eggs", params={"servings": 2, "substitutions": json.dumps([sub])}
    ).json()
    mushroom = next(line for line in detail["lines"] if line["ingredient_id"] == "mushroom")
    assert mushroom["substituted_from"] == "spinach"
    assert (
        client.patch(f"/api/basket/items/{first['id']}", json={"substitutions": []}).json()[
            "substitutions"
        ]
        == []
    )


def test_expired_and_insufficient_substitutes_not_suggested_or_saved(client):
    pantry(client, "mushroom", 500, expiry="2026-10-19")
    assert client.get("/api/recipes/rec_eggs").json()["suggestions"] == []
    b = client.post("/api/basket/items", json={"recipe_id": "rec_eggs", "servings": 1}).json()
    sub = {
        "rule_id": "r8",
        "original_ingredient_id": "spinach",
        "substitute_ingredient_id": "mushroom",
    }
    assert (
        client.patch(f"/api/basket/items/{b['id']}", json={"substitutions": [sub]}).status_code
        == 422
    )
    assert client.get("/api/basket").json()["items"][0]["substitutions"] == []


def test_invalid_duplicate_and_wrong_context_substitutions(client):
    sub = {
        "rule_id": "r8",
        "original_ingredient_id": "spinach",
        "substitute_ingredient_id": "mushroom",
    }
    for recipe_id, choices in [
        ("rec_eggs", [sub, sub]),
        ("rec_test1", [sub]),
        ("rec_eggs", [sub | {"substitute_ingredient_id": "egg"}]),
    ]:
        req = {"recipe_id": recipe_id, "servings": 1, "substitutions": choices}
        assert client.post("/api/cooking/preview", json=req).status_code == 422


def test_shopping_regeneration_protects_edits_purchases_deletions_and_manual_reset(client):
    client.post("/api/basket/items", json={"recipe_id": "rec_test1", "servings": 1})
    first = client.post("/api/shopping-list/generate").json()
    manual = client.post(
        "/api/shopping-list/items", json={"label": "Paper towels", "quantity": 2, "unit": "pcs"}
    ).json()
    client.patch(f"/api/shopping-list/items/{first[0]['id']}", json={"quantity": 999})
    before = client.get("/api/shopping-list").json()
    assert client.post("/api/shopping-list/generate").json()["code"] == "EDITS_WOULD_BE_LOST"
    assert client.get("/api/shopping-list").json() == before
    generated = client.post("/api/shopping-list/generate", json={"force": True}).json()
    assert manual in generated
    assert not any(item["quantity"] == 999 for item in generated)
    assert client.post("/api/shopping-list/generate", json={"resetAll": True}).status_code == 409
    item = next(i for i in generated if i["origin"] == "generated")
    client.patch(f"/api/shopping-list/items/{item['id']}", json={"purchased": True})
    assert client.post("/api/shopping-list/generate").status_code == 409
    client.patch(f"/api/shopping-list/items/{item['id']}", json={"purchased": False})
    assert client.delete(f"/api/shopping-list/items/{item['id']}").status_code == 204
    assert client.post("/api/shopping-list/generate").status_code == 409
    reset = client.post(
        "/api/shopping-list/generate", json={"resetAll": True, "force": True}
    ).json()
    assert all(item["origin"] == "generated" for item in reset)


def test_urgency_reorders_equal_match_scores(client, service):
    for raw in [
        meal(
            "a",
            "A fresh topping",
            ingredients=[("Pasta", "100g"), ("Butter", "10g"), ("Milk", "100ml")],
        ),
        meal(
            "z",
            "Z urgent topping",
            ingredients=[("Pasta", "100g"), ("Parmesan", "30g"), ("Milk", "100ml")],
        ),
    ]:
        recipe = normalize_meal(raw)
        service.state.recipes[recipe.id] = recipe
    pantry(client, "pasta", 100, expiry="2026-11-01")
    pantry(client, "butter", 10, expiry="2026-11-01")
    pantry(client, "parmesan", 30, expiry="2026-10-22")
    ranked = client.get("/api/recipes?query=topping").json()
    assert [r["match"]["score"] for r in ranked] == [67, 67]
    assert [r["id"] for r in ranked] == ["rec_z", "rec_a"]


def test_shared_substitute_demand_cannot_exceed_stock(client, service):
    recipe = normalize_meal(
        meal(
            "shared", "Shared substitute", "Pasta", [("Cheddar cheese", "40g"), ("Parmesan", "30g")]
        )
    )
    service.state.recipes[recipe.id] = recipe
    pantry(client, "parmesan", 40)
    # Cheese substitution needs 30g, but Parmesan already needs 30g itself.
    assert client.get("/api/recipes/rec_shared").json()["suggestions"] == []
    req = {
        "recipe_id": recipe.id,
        "servings": 1,
        "substitutions": [
            {
                "rule_id": "r2",
                "original_ingredient_id": "cheese",
                "substitute_ingredient_id": "parmesan",
            }
        ],
    }
    preview = client.post("/api/cooking/preview", json=req).json()
    assert not preview["can_cook"]
    assert all(not line["sufficient"] for line in preview["lines"])
    assert client.post("/api/cooking/confirm", json=req).status_code == 409
    assert client.get("/api/pantry").json()[0]["quantity"] == 40


def test_scaling_uses_recipe_base_servings(client, service):
    service.state.recipes["rec_test1"].base_servings = 2
    detail = client.get("/api/recipes/rec_test1?servings=3").json()
    assert detail["base_servings"] == 2
    assert {line["ingredient_id"]: line["required"] for line in detail["lines"]} == {
        "pasta": 150,
        "milk": 150,
        "butter": 15,
    }
