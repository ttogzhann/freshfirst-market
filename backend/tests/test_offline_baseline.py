"""FF19-PM-r1: packaged provenance, offline startup and missing-only persistence."""

import hashlib
import json
import subprocess
import sys
from copy import deepcopy

import pytest
from conftest import ContractClient, Source, meal
from sqlalchemy import func, select
from test_real_recipe_baseline import EXPECTED_LINES, FIXTURES

from app.errors import ServiceError
from app.main import create_app
from app.models import BasketInput, CookRequest, PantryInput, ShoppingInput
from app.services.fresh import FreshService
from app.services.importer import PackagedMealSource, TheMealDBSource, normalize_meal
from app.store import recipe_ingredients, recipes


def blocked_source(self):
    raise ServiceError(502, "SOURCE_UNAVAILABLE", "Source blocked for offline verification")


def test_packaged_bytes_and_exact_recipe_metadata():
    for filename in ("53137.json", "52776.json", "provenance.json"):
        assert (PackagedMealSource.DIRECTORY / filename).read_bytes() == (
            FIXTURES / filename
        ).read_bytes()
    for raw in PackagedMealSource().meals():
        recipe = normalize_meal(raw)
        assert {i.ingredient_id: i.quantity for i in recipe.ingredients} == {
            identity: quantity for _, _, identity, _, quantity in EXPECTED_LINES[raw["idMeal"]]
        }
        assert recipe.base_servings == 1
        for field, key in (
            ("title", "strMeal"),
            ("category", "strCategory"),
            ("instructions", "strInstructions"),
            ("image_url", "strMealThumb"),
        ):
            assert getattr(recipe, field) == raw[key].strip()


def test_default_offline_startup_and_separate_process_restart(monkeypatch):
    monkeypatch.setattr(TheMealDBSource, "meals", blocked_source)
    with ContractClient(create_app()) as client:
        details = [client.get(f"/api/recipes/rec_{i}").json() for i in EXPECTED_LINES]
        assert all(d["ingredients"] and d["instructions"] for d in details)
        service = client.app.state.service
        before = service.state
        service.seed_recipes()
        assert service.state == before
        # Once-only pantry remains once-only even if the user deletes the sample stock.
        for item in service.list_pantry():
            service.delete_pantry(item.id)
        before = service.state
    script = """
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services.importer import TheMealDBSource
def blocked(self):
    raise AssertionError('Startup attempted live source')
TheMealDBSource.meals = blocked
with TestClient(app) as client:
    s = app.state.service
    print(json.dumps(s.store._rows(s.state), sort_keys=True, default=str))
"""
    output = subprocess.check_output([sys.executable, "-c", script], text=True)
    assert json.loads(output) == json.loads(
        json.dumps(service.store._rows(before), sort_keys=True, default=str)
    )


def populated_service():
    service = FreshService(seed=False)
    raw = list(PackagedMealSource().meals())[0]
    raw["strMeal"] = "Newer live title"
    raw["strMeasure1"] = "2 Litre"
    service.source = Source([raw, meal()])
    service.import_recipes()
    for identity, quantity, unit in [("pasta", 300, "g"), ("milk", 300, "ml"), ("butter", 30, "g")]:
        service.create_pantry(
            PantryInput(
                ingredient_id=identity, quantity=quantity, unit=unit, expiry_date="2099-01-01"
            )
        )
    service.confirm_cook(CookRequest(recipe_id="rec_test1", servings=1, substitutions=[]))
    service.add_basket(BasketInput(recipe_id="rec_53137", servings=2))
    service.add_shopping(ShoppingInput(label="Saved edit", quantity=7, unit="g"))
    return service


def test_partial_baseline_retains_newer_live_and_every_saved_entity():
    service = populated_service()
    before = deepcopy(service.state)
    service.seed_recipes()
    after = service.state
    assert set(after.recipes) == {*before.recipes, "rec_52776"}
    del after.recipes["rec_52776"]
    assert after == before
    service.seed_recipes()
    with service.store.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(recipes)) == 3
        assert connection.scalar(select(func.count()).select_from(recipe_ingredients)) == 13
    expected = json.loads(json.dumps(service.store._rows(service.state), default=str))
    service.store.close()
    script = """
import json
from app.services.fresh import FreshService
s = FreshService(seed=False)
s.seed_recipes()
print(json.dumps(s.store._rows(s.state), default=str))
s.store.close()
"""
    assert (
        json.loads(subprocess.check_output([sys.executable, "-c", script], text=True)) == expected
    )


@pytest.mark.parametrize(
    "corruption", ["quantity", "identity", "metadata", "payload", "hash", "provenance"]
)
def test_malformed_second_record_is_visible_and_atomic(monkeypatch, tmp_path, corruption):
    directory = tmp_path / "package"
    directory.mkdir()
    for path in PackagedMealSource.DIRECTORY.glob("*.json"):
        (directory / path.name).write_bytes(path.read_bytes())
    manifest = json.loads((directory / "provenance.json").read_bytes())
    record = manifest["records"][1]
    path = directory / record["raw_file"]
    payload = json.loads(path.read_bytes())
    raw = payload["meals"][0]
    if corruption == "quantity":
        raw["strMeasure1"] = "1 cup"
    elif corruption == "identity":
        raw["strIngredient1"] = "Unknown chocolate"
    elif corruption == "metadata":
        raw["strMeal"] = ""
    elif corruption == "payload":
        payload["meals"] = None
    elif corruption == "provenance":
        record["lookup_url"] = "https://example.invalid"
    path.write_text(json.dumps(payload), encoding="utf8")
    if corruption != "hash":
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / "provenance.json").write_text(json.dumps(manifest), encoding="utf8")
    # Existing nonbaseline state survives; valid first baseline is not partially saved.
    service = populated_service()
    with service.store.transaction():
        del service.state.basket[next(iter(service.state.basket))]
        del service.state.recipes["rec_53137"]
    before = service.state
    monkeypatch.setattr(PackagedMealSource, "DIRECTORY", directory)
    with pytest.raises((RuntimeError, ServiceError)):
        with ContractClient(create_app(service)):
            pass
    assert service.state == before


def test_explicit_live_import_upsert_and_source_failure(monkeypatch):
    service = FreshService(seed=False)
    with ContractClient(create_app(service)) as client:
        before = service.state
        service.source = Source(list(PackagedMealSource().meals()))
        for _ in range(2):
            report = client.post("/api/recipes/import").json()
            assert (report["imported"], report["updated"], report["total_recipes"]) == (0, 2, 2)
        assert service.state == before
        service.source = TheMealDBSource()
        monkeypatch.setattr(TheMealDBSource, "meals", blocked_source)
        response = client.post("/api/recipes/import")
        assert response.status_code == 502
        assert response.json()["code"] == "SOURCE_UNAVAILABLE"
        assert service.state == before
