from datetime import date
from decimal import Decimal

from conftest import TODAY, pantry

from app.models import PantryItem
from app.services.allocation import allocate


def lot(lot_id, expiry, quantity, *, dimension="g", status="resolved", ingredient="pasta"):
    return PantryItem(
        id=lot_id,
        ingredient_id=ingredient,
        quantity=quantity,
        expiry_date=date.fromisoformat(expiry),
        canonical_dimension=dimension,
        resolution_status=status,
    )


def test_allocator_is_fefo_stable_and_caps_partial_lots():
    lots = [
        lot("later", "2026-11-02", 2000),
        lot("earlier", "2026-10-21", 500),
    ]
    result = allocate(reversed(lots), "pasta", "g", Decimal("1250"), TODAY)
    assert result.available == Decimal("2500")
    assert result.allocated == Decimal("1250")
    assert result.missing == Decimal("0")
    assert [item.lot_id for item in result.lots] == ["earlier", "later"]
    assert [item.quantity for item in result.lots] == [Decimal("500"), Decimal("750")]


def test_allocator_excludes_boundaries_resolution_and_dimensions():
    lots = [
        lot("yesterday", "2026-10-19", 100),
        lot("today", "2026-10-20", 100),
        lot("threshold", "2026-10-23", 100),
        lot("after", "2026-10-24", 100),
        lot("unresolved", "2026-10-20", 500, status="unresolved"),
        lot("volume", "2026-10-20", 500, dimension="ml"),
    ]
    result = allocate(lots, "pasta", "g", Decimal("450"), TODAY)
    assert result.available == Decimal("300")
    assert result.allocated == Decimal("300")
    assert result.missing == Decimal("150")
    assert [item.lot_id for item in result.lots] == ["today", "threshold", "after"]


def test_api_exposes_same_fefo_result_to_detail_basket_shopping_and_cooking(client, service):
    pantry(client, "pasta", 100, "g", "2026-10-21")
    pantry(client, "pasta", 200, "g", "2026-11-01")
    detail = client.get("/api/recipes/rec_test1", params={"servings": 1}).json()
    pasta = next(line for line in detail["lines"] if line["ingredient_id"] == "pasta")
    assert (pasta["required"], pasta["available"], pasta["allocated"], pasta["missing"]) == (
        100,
        300,
        100,
        0,
    )
    assert pasta["allocations"][0]["quantity"] == 100
    client.post("/api/basket/items", json={"recipe_id": "rec_test1", "servings": 1})
    basket = client.get("/api/basket").json()
    basket_pasta = next(line for line in basket["totals"] if line["ingredient_id"] == "pasta")
    assert basket_pasta["allocations"] == pasta["allocations"]
    shopping = client.post("/api/shopping-list/generate", json={}).json()
    assert not any(item["ingredient_id"] == "pasta" for item in shopping)


def test_insufficient_cook_rolls_back_without_negative_stock(client):
    pantry(client, "pasta", 50, "g", "2026-10-21")
    request = {"recipe_id": "rec_test1", "servings": 1, "substitutions": []}
    before = client.get("/api/pantry").json()
    assert client.post("/api/cooking/confirm", json=request).status_code == 409
    assert client.get("/api/pantry").json() == before
    assert client.get("/api/cooking/history").json() == []


def test_adaptation_returns_maximum_count_and_same_exact_lines_across_journey(client):
    # rec_test1 is 100g pasta, 100ml milk and 10g butter per recipe quantity.
    pantry(client, "pasta", 250, "g", "2026-10-21")
    pantry(client, "milk", 250, "ml", "2026-10-21")
    pantry(client, "butter", 25, "g", "2026-10-21")

    detail = client.get("/api/recipes/rec_test1", params={"servings": 2}).json()
    assert (detail["original_servings"], detail["adapted_servings"]) == (1, 2)
    assert detail["feasible_servings"] == 2
    assert set(detail["limiting_lines"]) == {"pasta", "milk", "butter"}

    basket_item = client.post(
        "/api/basket/items", json={"recipe_id": "rec_test1", "servings": 2}
    ).json()
    basket = client.get("/api/basket").json()
    assert basket["items"][0]["adapted_servings"] == basket_item["servings"] == 2
    assert basket["items"][0]["feasible_servings"] == 2
    basket_pasta = next(line for line in basket["totals"] if line["ingredient_id"] == "pasta")
    detail_pasta = next(line for line in detail["lines"] if line["ingredient_id"] == "pasta")
    assert basket_pasta == detail_pasta

    preview = client.post(
        "/api/cooking/preview",
        json={"recipe_id": "rec_test1", "servings": 2, "substitutions": []},
    ).json()
    assert preview["feasible_servings"] == 2
    assert (
        next(line for line in preview["lines"] if line["ingredient_id"] == "pasta") == detail_pasta
    )

    record = client.post(
        "/api/cooking/confirm",
        json={"recipe_id": "rec_test1", "servings": 2, "substitutions": []},
    ).json()
    assert (record["original_servings"], record["adapted_servings"]) == (1, 2)
    assert {line["ingredient_id"]: line["quantity"] for line in record["consumed"]} == {
        "pasta": 200,
        "milk": 200,
        "butter": 20,
    }


def test_adaptation_exposes_limiting_lines_and_rejects_no_zero_fraction(client):
    pantry(client, "pasta", 100, "g", "2026-10-21")
    pantry(client, "milk", 100, "ml", "2026-10-21")
    pantry(client, "butter", 10, "g", "2026-10-21")
    detail = client.get("/api/recipes/rec_test1", params={"servings": 8}).json()
    assert detail["feasible_servings"] == 1
    assert set(detail["limiting_lines"]) == {"pasta", "milk", "butter"}
    assert all(line["required"] > 0 for line in detail["lines"])
