from conftest import CONTRACT, pantry
from fastapi.openapi.utils import get_openapi
from openapi_spec_validator import validate

from app.main import create_app
from app.models import (
    Account,
    AuthCredentials,
    AuthResponse,
    AuthSessionResponse,
    BasketInput,
    BasketItem,
    BasketItemWithRecipe,
    BasketPatch,
    BasketView,
    ConfirmedSubstitution,
    Consumption,
    CookingRecord,
    CookPreview,
    CookRequest,
    Dashboard,
    DemandLine,
    Error,
    ImportReport,
    ImportSkip,
    Ingredient,
    MatchInfo,
    PantryInput,
    PantryItem,
    Recipe,
    RecipeDetail,
    RecipeIngredient,
    RecipeSummary,
    ShoppingGenerationInput,
    ShoppingInput,
    ShoppingItem,
    ShoppingPatch,
    SubstitutionRule,
    SubstitutionSuggestion,
    TransferInput,
)


def test_authored_contract_valid_and_all_operations_registered(service):
    validate(CONTRACT)
    app = create_app(service, startup_import=False)
    generated = get_openapi(title=app.title, version=app.version, routes=app.routes)
    expected = {
        (method, "/api" + path, op["operationId"])
        for path, methods in CONTRACT["paths"].items()
        for method, op in methods.items()
    }
    actual = {
        (method, path, op["operationId"])
        for path, methods in generated["paths"].items()
        for method, op in methods.items()
    }
    assert actual == expected
    assert len(actual) == 27
    expected_domain_ids = {
        op["operationId"]
        for path, methods in CONTRACT["paths"].items()
        if not path.startswith("/auth/")
        for op in methods.values()
    }
    assert len(expected_domain_ids) == 23
    assert CONTRACT["security"] == [{"SessionCookie": [], "CsrfToken": []}]
    assert set(CONTRACT["components"]["securitySchemes"]) == {"SessionCookie", "CsrfToken"}
    assert CONTRACT["paths"]["/ingredients"]["get"]["security"] == []
    assert CONTRACT["paths"]["/substitution-rules"]["get"]["security"] == []
    assert CONTRACT["paths"]["/recipes"]["get"]["security"] == [{"SessionCookie": []}]
    assert (
        CONTRACT["paths"]["/pantry"]["post"].get("security", CONTRACT["security"])
        == CONTRACT["security"]
    )


def test_every_object_schema_has_a_transport_model():
    models = [
        BasketInput,
        BasketItem,
        BasketItemWithRecipe,
        BasketPatch,
        BasketView,
        Consumption,
        ConfirmedSubstitution,
        CookingRecord,
        CookPreview,
        CookRequest,
        Dashboard,
        DemandLine,
        Error,
        ImportReport,
        ImportSkip,
        Ingredient,
        MatchInfo,
        PantryInput,
        PantryItem,
        Recipe,
        RecipeDetail,
        RecipeIngredient,
        RecipeSummary,
        ShoppingGenerationInput,
        ShoppingInput,
        ShoppingItem,
        ShoppingPatch,
        SubstitutionRule,
        SubstitutionSuggestion,
        TransferInput,
        Account,
        AuthCredentials,
        AuthResponse,
        AuthSessionResponse,
    ]
    assert set(CONTRACT["components"]["schemas"]) - {
        "InputUnit",
        "CanonicalUnit",
        "Servings",
    } <= {m.__name__ for m in models}


def test_all_23_endpoints_with_real_response_schema_validation(client):
    assert client.get("/openapi.json").json() == CONTRACT
    assert client.get("/api/ingredients").status_code == 200
    assert client.get("/api/substitution-rules").status_code == 200
    assert client.get("/api/pantry").json() == []
    p = pantry(client, "egg", 6, "pcs")
    assert (
        client.put(
            f"/api/pantry/{p['id']}",
            json={
                "ingredient_id": "egg",
                "quantity": 7,
                "unit": "pcs",
                "expiry_date": "2026-11-01",
            },
        ).status_code
        == 200
    )
    assert client.delete(f"/api/pantry/{p['id']}").status_code == 204
    assert client.get("/api/recipes").status_code == 200
    assert client.get("/api/recipes/rec_test1").status_code == 200
    assert client.post("/api/recipes/import").json()["updated"] == 3
    b = client.post("/api/basket/items", json={"recipe_id": "rec_test1", "servings": 1}).json()
    assert client.get("/api/basket").status_code == 200
    assert client.patch(f"/api/basket/items/{b['id']}", json={"servings": 2}).status_code == 200
    assert client.post("/api/shopping-list/generate").status_code == 200
    assert client.get("/api/shopping-list").status_code == 200
    s = client.post(
        "/api/shopping-list/items", json={"label": "Eggs", "quantity": 6, "unit": "pcs"}
    ).json()
    assert (
        client.patch(f"/api/shopping-list/items/{s['id']}", json={"purchased": True}).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/shopping-list/items/{s['id']}/transfer-to-pantry",
            json={"quantity": 6, "expiry_date": "2026-11-01"},
        ).status_code
        == 200
    )
    assert client.delete(f"/api/shopping-list/items/{s['id']}").status_code == 204
    assert client.delete(f"/api/basket/items/{b['id']}").status_code == 204
    for i, q, u in [("pasta", 100, "g"), ("milk", 100, "ml"), ("butter", 10, "g")]:
        pantry(client, i, q, u)
    req = {"recipe_id": "rec_test1", "servings": 1, "substitutions": []}
    assert client.post("/api/cooking/preview", json=req).json()["can_cook"]
    assert client.post("/api/cooking/confirm", json=req).status_code == 201
    assert len(client.get("/api/cooking/history").json()) == 1
    assert client.get("/api/dashboard").status_code == 200
    domain_ids = {
        operation["operationId"]
        for path, methods in CONTRACT["paths"].items()
        if not path.startswith("/auth/")
        for operation in methods.values()
    }
    assert len(domain_ids) == 23
    assert domain_ids <= client.operations
