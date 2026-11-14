import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from conftest import ContractClient, Source, meal, register_test_account
from sqlalchemy import event, func, select

from app.errors import ServiceError
from app.main import create_app
from app.services.fresh import FreshService
from app.services.importer import TheMealDBSource, normalize_meal
from app.services.quantities import normalize, parse_measure
from app.store import SQLiteStore, import_source_lines, import_sources, ingredients, recipes


@pytest.mark.parametrize(
    "text,unit,expected",
    [
        ("1kg", "g", 1000),
        ("1.5 l", "ml", 1500),
        ("2 tbsp", "ml", 30),
        ("1/4 tsp", "ml", 1.25),
        ("1 1/2 tablespoons", "ml", 22.5),
        ("2", "pcs", 2),
        ("3 cloves", "pcs", 3),
        ("125 grams", "g", 125),
    ],
)
def test_exact_quantity_normalization(text, unit, expected):
    assert parse_measure(text, unit) == expected


@pytest.mark.parametrize(
    "text",
    [
        "pinch",
        "1 handful",
        "1 cup",
        "to taste",
        "1-2 g",
        "about 2g",
        "",
        "0g",
        "1/0g",
        "NaN g",
        "1 tin",
        "some",
        "1 g plus extra",
    ],
)
def test_unsupported_or_ambiguous_measures_are_never_guessed(text):
    with pytest.raises(ServiceError) as error:
        parse_measure(text, "g")
    assert error.value.status == 422


def test_incompatible_units_cannot_cross_mass_volume_or_count():
    for quantity, unit, canonical in [(1, "kg", "ml"), (1, "pcs", "g"), (1, "tsp", "g")]:
        with pytest.raises(ServiceError):
            normalize(quantity, unit, canonical)


def test_import_is_idempotent_updates_source_ids_and_reports_skips(client, service):
    original = meal()
    updated = meal(title="Updated milk pasta")
    bad = meal("unsupported", ingredients=[("Flour", "1 cup")])
    service.source = Source([updated, bad])
    response = client.post("/api/recipes/import")
    report = response.json()
    assert report["imported"] == 0
    assert report["updated"] == 1
    assert report["total_recipes"] == 3
    assert report["skipped"][0]["external_id"] == "unsupported"
    assert "quantity" in report["skipped"][0]["reason"].lower()
    assert client.get("/api/recipes/rec_test1").json()["title"] == "Updated milk pasta"
    assert normalize_meal(original).external_id == normalize_meal(updated).external_id


def test_import_accepts_all_valid_reviewed_records_and_duplicates_do_not_count_twice():
    payload = [meal(str(n)) for n in range(25)]
    service = FreshService(source=Source([payload[0], payload[0]] + payload), seed=False)
    first = service.import_recipes()
    assert first.imported == first.total_recipes == 25
    second = service.import_recipes()
    assert second.imported == 0
    assert second.updated == 25
    assert len({r.external_id for r in service.state.recipes.values()}) == 25


def test_duplicate_ingredient_lines_aggregate_after_normalization():
    recipe = normalize_meal(meal(ingredients=[("Milk", "1 l"), ("Milk", "100ml")]))
    assert len(recipe.ingredients) == 1
    assert recipe.ingredients[0].quantity == 1100


def test_import_creates_reviewed_new_ingredient_alias_and_audit_rows(tmp_path):
    raw = meal("new-profile", ingredients=[("Kelp flakes", "1kg")]) | {
        "source_name": "reviewed-fixture",
        "lookup_url": "https://source.example/recipes/new-profile",
        "captured_at_utc": "2026-11-14T00:00:00+00:00",
        "reviewed_ingredient_profiles": {
            "Kelp flakes": {
                "canonical_id": "kelp_flakes",
                "display_name": "Kelp flakes",
                "category": "Pantry staples",
                "canonical_unit": "g",
            }
        },
    }
    service = FreshService(
        store=SQLiteStore(f"sqlite:///{tmp_path / 'new.db'}"), source=Source([raw]), seed=False
    )
    report = service.import_recipes()
    assert (report.imported, report.skipped) == (1, [])
    with service.store.engine.connect() as connection:
        ingredient = (
            connection.execute(select(ingredients).where(ingredients.c.id == "kelp_flakes"))
            .mappings()
            .one()
        )
        assert (ingredient["category"], ingredient["canonical_unit"]) == ("Pantry staples", "g")
        assert (
            connection.scalar(
                select(func.count())
                .select_from(import_sources)
                .where(import_sources.c.external_id == "new-profile")
            )
            == 1
        )
        line = connection.execute(select(import_source_lines)).mappings().one()
        assert (line["raw_name"], line["raw_measure"], line["quantity_canonical"]) == (
            "Kelp flakes",
            "1kg",
            1000,
        )
    assert service.store.resolve_alias("  KELP   flakes ").ingredient_ids == ("kelp_flakes",)
    service.store.close()
    reopened = FreshService(
        store=SQLiteStore(f"sqlite:///{tmp_path / 'new.db'}"), source=Source([raw]), seed=False
    )
    repeat = reopened.import_recipes()
    assert (repeat.imported, repeat.updated) == (0, 1)
    with reopened.store.engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(ingredients)
                .where(ingredients.c.id == "kelp_flakes")
            )
            == 1
        )
        assert (
            connection.scalar(
                select(func.count())
                .select_from(import_sources)
                .where(import_sources.c.external_id == "new-profile")
            )
            == 1
        )
    reopened.store.close()


def test_import_catalog_and_audit_roll_back_on_late_recipe_line_failure(tmp_path):
    raw = meal("late-failure", ingredients=[("New herb", "1kg")]) | {
        "reviewed_ingredient_profiles": {
            "New herb": {
                "canonical_id": "new_herb",
                "display_name": "New herb",
                "category": "Herbs",
                "canonical_unit": "g",
            }
        }
    }
    service = FreshService(
        store=SQLiteStore(f"sqlite:///{tmp_path / 'rollback.db'}"), source=Source([raw]), seed=False
    )

    def fail(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "INSERT INTO recipe_ingredients" in statement:
            raise RuntimeError("injected import line failure")

    event.listen(service.store.engine, "before_cursor_execute", fail)
    with pytest.raises(RuntimeError, match="injected import line failure"):
        service.import_recipes()
    event.remove(service.store.engine, "before_cursor_execute", fail)
    with service.store.engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count()).select_from(ingredients).where(ingredients.c.id == "new_herb")
            )
            == 0
        )
        assert (
            connection.scalar(
                select(func.count())
                .select_from(recipes)
                .where(recipes.c.external_id == "late-failure")
            )
            == 0
        )
        assert connection.scalar(select(func.count()).select_from(import_sources)) == 0
    service.store.close()


@pytest.mark.parametrize(
    "patch",
    [
        {"strIngredient1": "Mystery vegetable"},
        {"strMeasure1": "1 cup"},
        {"strInstructions": ""},
        {"strIngredient1": "", "strMeasure1": "100g"},
        {"strIngredient1": 123},
        {"strMeasure1": 100},
    ],
)
def test_bad_source_recipes_are_skipped_with_reasons(patch):
    service = FreshService(source=Source([meal() | patch]), seed=False)
    report = service.import_recipes()
    assert report.imported == 0
    assert len(report.skipped) == 1
    assert report.skipped[0].reason


def test_real_source_snapshot_requires_no_guessed_conversions():
    raw = json.loads(
        (Path(__file__).parent / "fixtures" / "mealdb.json").read_text(encoding="utf8")
    )
    source = Source(raw)
    report = FreshService(source=source, seed=False).import_recipes()
    assert report.imported >= 1
    assert report.skipped
    normalized = normalize_meal(next(m for m in raw if m["idMeal"] == "53137"))
    assert {i.ingredient_id: i.quantity for i in normalized.ingredients} == {
        "milk": 1000,
        "sugar": 300,
        "baking_powder": 1.25,
        "vanilla": 5,
    }


def test_live_adapter_requests_letters_once_and_uses_real_payload_shape():
    calls = []

    def handle(request):
        calls.append(request.url.params["f"])
        assert request.url.host == "www.themealdb.com"
        assert request.url.path.endswith("/search.php")
        return httpx.Response(
            200, json={"meals": [meal()] if request.url.params["f"] == "a" else None}
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        result = list(TheMealDBSource(http).meals())
    assert len(result) == 1
    assert len(calls) == 26


@pytest.mark.parametrize("failure", ["timeout", "http", "json", "shape", "list"])
def test_source_failure_returns_502_and_preserves_everything(client, service, failure):
    def handle(request):
        # Accept a changed candidate on a, then fail b: upserts must not partially apply.
        if request.url.params["f"] == "a":
            return httpx.Response(200, json={"meals": [meal(title="Must not commit")]})
        if failure == "timeout":
            raise httpx.ReadTimeout("Timeout", request=request)
        if failure == "http":
            return httpx.Response(503)
        if failure == "json":
            return httpx.Response(200, content=b"not json")
        if failure == "shape":
            return httpx.Response(200, json={"unknown": []})
        return httpx.Response(200, json={"meals": "not a list"})

    before = deepcopy(service.state)
    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        service.source = TheMealDBSource(http)
        response = client.post("/api/recipes/import")
    assert response.status_code == 502
    assert response.json()["code"] == "SOURCE_UNAVAILABLE"
    assert service.state == before


def test_startup_seeds_offline_baseline_without_live_import_or_page_read_fetches():
    class CountingSource(Source):
        calls = 0

        def meals(self):
            self.calls += 1
            return super().meals()

    source = CountingSource([meal()])
    service = FreshService(source=source)
    with ContractClient(create_app(service)) as client:
        register_test_account(client)
        assert client.get("/api/pantry").json() == []
        for _ in range(3):
            assert len(client.get("/api/recipes").json()) == 15
    assert source.calls == 0
