"""Focused Issue #68 corpus and production-seed checks."""

import json

import pytest
from sqlalchemy import func, select

from app.services.fresh import FreshService
from app.services.importer import CuratedCatalogSource, normalize_meal
from app.store import SQLiteStore, recipes


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
