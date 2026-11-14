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
