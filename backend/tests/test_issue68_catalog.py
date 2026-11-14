"""Focused Issue #68 corpus and production-seed checks."""

import json

import pytest
from sqlalchemy import func, select

from app.services.fresh import FreshService
from app.services.importer import CuratedCatalogSource, normalize_meal
from app.store import SQLiteStore, import_source_lines, import_sources, recipes


def test_curated_manifest_is_hashed_substantive_and_strictly_normalizable():
    records = list(CuratedCatalogSource().meals())
    assert 80 <= len(records) <= 100
    assert len({record["idMeal"] for record in records}) == len(records)
    assert len({record["strMeal"].casefold() for record in records}) == len(records)
    assert all(" Recipe " not in record["strMeal"] for record in records)
    for raw in records:
        recipe = normalize_meal(raw)
        assert len(recipe.ingredients) >= 3
        assert all(line.quantity > 0 for line in recipe.ingredients)
        assert raw["source_url"].startswith("original-authored://")


def test_manifest_rejects_placeholder_or_generic_records(tmp_path, monkeypatch):
    manifest = json.loads(CuratedCatalogSource.PATH.read_text(encoding="utf8"))
    manifest["records"][0]["strMeal"] = "FreshFirst Breakfast Recipe 001"
    monkeypatch.setattr(CuratedCatalogSource, "PATH", tmp_path / "manifest.json")
    tmp_path.joinpath("manifest.json").write_text(json.dumps(manifest), encoding="utf8")
    with pytest.raises(RuntimeError, match="invalid"):
        list(CuratedCatalogSource().meals())


def test_production_seed_is_repeat_safe_and_supports_combined_discovery(tmp_path):
    service = FreshService(store=SQLiteStore(f"sqlite:///{tmp_path / 'catalog.db'}"), seed=False)
    service.seed_recipes(include_catalog=True)
    first_ids = set(service.state.recipes)
    assert len(first_ids) == 95
    assert service.list_recipes("chicken", "Chicken", "title")
    assert not service.list_recipes("does-not-exist", "Chicken", "title")
    service.seed_recipes(include_catalog=True)
    assert set(service.state.recipes) == first_ids
    with service.store.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(recipes)) == 95


def test_catalog_bootstrap_preserves_newer_recipe_and_complete_source_audit(tmp_path):
    from copy import deepcopy

    from conftest import Source

    database = f"sqlite:///{tmp_path / 'newer-catalog.db'}"
    raw = deepcopy(next(CuratedCatalogSource().meals()))
    raw["strMeal"] = "Updated spinach omelet"
    raw["strMeasure1"] = "4"
    raw["captured_at_utc"] = "2026-11-15T00:00:00+00:00"
    service = FreshService(store=SQLiteStore(database), source=Source([raw]), seed=False)
    service.import_recipes()
    recipe_id = f"rec_{raw['idMeal']}"
    expected_recipe = deepcopy(service.state.recipes[recipe_id])

    def audit(store):
        with store.engine.connect() as connection:
            source = dict(
                connection.execute(
                    select(import_sources).where(import_sources.c.external_id == raw["idMeal"])
                )
                .mappings()
                .one()
            )
            lines = [
                dict(row)
                for row in connection.execute(
                    select(import_source_lines)
                    .where(import_source_lines.c.source_id == source["id"])
                    .order_by(import_source_lines.c.line_number)
                ).mappings()
            ]
            return source, lines

    expected_audit = audit(service.store)
    for _ in range(2):
        service.seed_recipes(include_catalog=True)
        assert service.state.recipes[recipe_id] == expected_recipe
        assert audit(service.store) == expected_audit
    service.store.close()
    restarted = FreshService(store=SQLiteStore(database), seed=False)
    restarted.seed_recipes(include_catalog=True)
    assert restarted.state.recipes[recipe_id] == expected_recipe
    assert audit(restarted.store) == expected_audit
    restarted.store.close()


def _manifest_with_change(monkeypatch, tmp_path, mutate):
    from app.services.catalog_quality import records_hash

    manifest = json.loads(CuratedCatalogSource.PATH.read_text(encoding="utf8"))
    mutate(manifest["records"])
    manifest["catalog_hash"] = records_hash(manifest["records"])
    path = tmp_path / "changed-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf8")
    monkeypatch.setattr(CuratedCatalogSource, "PATH", path)


@pytest.mark.parametrize(
    "defect,code",
    [
        ("duplicate_amounts", "DUPLICATE_CORE_INGREDIENTS"),
        ("duplicate_changed_amounts", "DUPLICATE_CORE_INGREDIENTS"),
        ("generic", "GENERIC_INSTRUCTIONS"),
        ("missing_vanilla", "MISSING_DEFINING_INGREDIENT"),
        ("missing_parsley", "MISSING_DEFINING_INGREDIENT"),
        ("bad_unit", "INVALID_QUANTITY_OR_UNIT"),
        ("ambiguous", "INVALID_QUANTITY_OR_UNIT"),
        ("unknown", "UNKNOWN_OR_DUPLICATE_INGREDIENT"),
        ("extra_slot", "UNACCOUNTED_INGREDIENT_SLOT"),
        ("yield", "INVALID_TIMING_OR_YIELD"),
    ],
)
def test_editorial_checks_reject_resigned_invalid_records(monkeypatch, tmp_path, defect, code):
    from app.services.catalog_quality import CatalogValidationError

    def mutate(records):
        target = records[-1]
        if defect.startswith("duplicate"):
            for key in list(target):
                if key.startswith(("strIngredient", "strMeasure")):
                    del target[key]
            for key, value in records[0].items():
                if key.startswith(("strIngredient", "strMeasure")):
                    target[key] = value
            if defect == "duplicate_changed_amounts":
                target["strMeasure1"] = "8"
        elif defect == "generic":
            target["strInstructions"] = (
                target["strInstructions"].split(". ", 2)[0]
                + ". "
                + target["strInstructions"].split(". ", 2)[1]
                + ". Cook the ingredients in sequence until fully done and serve warm."
            )
        elif defect in {"missing_vanilla", "missing_parsley"}:
            target = records[8 if defect == "missing_vanilla" else 21]
            wanted = "Vanilla extract" if defect == "missing_vanilla" else "Parsley"
            index = next(i for i in range(1, 21) if target.get(f"strIngredient{i}") == wanted)
            del target[f"strIngredient{index}"]
            del target[f"strMeasure{index}"]
        elif defect == "bad_unit":
            target["strMeasure1"] = "120ml"
        elif defect == "ambiguous":
            target["strMeasure1"] = "to taste"
        elif defect == "unknown":
            target["strIngredient1"] = "Unreviewed rice-like ingredient"
        elif defect == "extra_slot":
            target["strIngredient21"] = "Milk"
            target["strMeasure21"] = "100ml"
        elif defect == "yield":
            target["authored_portions"] = 0

    _manifest_with_change(monkeypatch, tmp_path, mutate)
    # Re-signing reaches the quality check: a hash failure alone cannot prove it.
    with pytest.raises(CatalogValidationError) as failure:
        CuratedCatalogSource().meals()
    assert failure.value.as_dict()["code"] == code


def test_catalog_editorial_identity_and_exact_batch_quantities():
    records = list(CuratedCatalogSource().meals())
    assert {r["idMeal"] for r in records} == {f"ff-original-{i:03}" for i in range(1, 81)}
    omelet = normalize_meal(records[0])
    assert omelet.base_servings == 1
    assert records[0]["authored_portions"] == 2
    assert {line.ingredient_id: line.quantity for line in omelet.ingredients} == {
        "egg": 4,
        "spinach": 100,
        "cheese": 40,
        "butter": 10,
        "salt": 1,
    }
    assert records[8]["strMeal"] == "Butter vanilla loaf"
    assert "Vanilla extract" in records[8].values()
    assert records[24]["strCategory"] == "Side"


def test_expanded_catalog_sqlite_rollback_repeat_and_process_restart(tmp_path):
    from catalog_transaction_probe import verify_catalog_transactions

    report = verify_catalog_transactions(f"sqlite:///{tmp_path / 'expanded.db'}")
    assert report["accepted_catalog"] == 80
    assert report["catalog_lines"] == 492
    assert report["late_failure_rolled_back"] is True
    assert report["restart_unchanged"] is True
