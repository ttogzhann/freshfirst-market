"""Reviewed genuine FF20 source slots; expectations predate normalizer comparison."""

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from conftest import Source

from app.catalog import ALIASES, CATALOG, RULE_CATEGORIES, RULES
from app.errors import ServiceError
from app.models import BasketInput
from app.services.fresh import FreshService
from app.services.importer import PackagedMealSource, normalize_meal

FIXTURES = Path(__file__).parent / "fixtures" / "mealdb-breadth"
REVIEW = json.loads((FIXTURES / "review.json").read_text(encoding="utf8"))
PREVIOUS = json.loads((FIXTURES / "previous-catalog.json").read_text(encoding="utf8"))


@pytest.mark.parametrize("review", REVIEW["records"], ids=lambda row: row["external_id"])
def test_genuine_full_slot_review_and_exact_quantities(review):
    external_id = review["external_id"]
    raw = (FIXTURES / f"{external_id}.json").read_bytes()
    assert raw == (PackagedMealSource.DIRECTORY / f"{external_id}.json").read_bytes()
    manifest = json.loads((PackagedMealSource.DIRECTORY / "provenance.json").read_bytes())
    provenance = next(r for r in manifest["records"] if r["external_id"] == external_id)
    assert provenance["sha256"] == hashlib.sha256(raw).hexdigest()
    source = json.loads(raw)["meals"][0]
    assert source["idMeal"] == external_id
    assert len(review["slots"]) == 20
    for slot in review["slots"]:
        n = slot["slot"]
        assert source.get(f"strIngredient{n}") == slot["raw_ingredient"]
        assert source.get(f"strMeasure{n}") == slot["raw_measure"]
        if "ingredient_id" in slot:
            assert ALIASES[slot["raw_ingredient"].strip().casefold()] == slot["ingredient_id"]
            assert CATALOG[slot["ingredient_id"]].canonical_unit == slot["unit"]
        else:
            assert not (slot["raw_ingredient"] or "").strip()
            assert not (slot["raw_measure"] or "").strip()
    recipe = normalize_meal(source)
    assert {i.ingredient_id: i.quantity for i in recipe.ingredients} == review["expected_totals"]
    assert recipe.title == source["strMeal"].strip() == review["title"]
    assert recipe.category == source["strCategory"].strip() == review["category"]
    assert recipe.instructions == source["strInstructions"].strip()
    assert recipe.image_url == source["strMealThumb"].strip()
    assert recipe.base_servings == 1


def test_additive_catalog_keeps_all_original_meanings_and_rules():
    assert len(PREVIOUS["catalog"]) == 41
    assert {k: CATALOG[k].model_dump(mode="json") for k in PREVIOUS["catalog"]} == PREVIOUS[
        "catalog"
    ]
    assert {k: ALIASES[k] for k in PREVIOUS["aliases"]} == PREVIOUS["aliases"]
    assert {k: v.model_dump(mode="json") for k, v in RULES.items()} == PREVIOUS["rules"]
    assert {k: sorted(v) for k, v in RULE_CATEGORIES.items()} == PREVIOUS["rule_categories"]
    expected = {
        row[0]: dict(zip(["id", "name", "category", "canonical_unit"], row, strict=True))
        for row in REVIEW["new_catalog"]
    }
    assert {
        k: v.model_dump() for k, v in CATALOG.items() if k not in PREVIOUS["catalog"]
    } == expected


def test_reviewed_corpus_breadth_categories_and_duplicate_line_reconciliation():
    assert len(REVIEW["records"]) == 15
    assert len({r["external_id"] for r in REVIEW["records"]}) == 15
    assert {r["category"] for r in REVIEW["records"]} == {
        "Dessert",
        "Miscellaneous",
        "Pork",
        "Side",
        "Vegan",
        "Vegetarian",
    }
    repeated = next(r for r in REVIEW["records"] if r["external_id"] == "53409")
    assert [
        s["expected_quantity"] for s in repeated["slots"] if s.get("ingredient_id") == "sugar"
    ] == [300, 220]
    assert repeated["expected_totals"]["sugar"] == 520


@pytest.mark.parametrize(
    "corruption", ["last_hash", "last_quantity", "duplicate_id", "missing_id", "last_provenance"]
)
def test_entire_package_validated_before_any_seed_write(tmp_path, monkeypatch, corruption):
    directory = tmp_path / "package"
    shutil.copytree(PackagedMealSource.DIRECTORY, directory)
    manifest = json.loads((directory / "provenance.json").read_bytes())
    record = manifest["records"][-1]
    if corruption == "last_hash":
        record["sha256"] = "0" * 64
    elif corruption == "last_quantity":
        path = directory / record["raw_file"]
        payload = json.loads(path.read_bytes())
        payload["meals"][0]["strMeasure1"] = "a handful"
        path.write_text(json.dumps(payload), encoding="utf8")
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif corruption == "duplicate_id":
        manifest["records"][-1] = manifest["records"][0]
    elif corruption == "missing_id":
        manifest["records"].pop()
    else:
        record["captured_at_utc"] = "not a UTC timestamp"
    (directory / "provenance.json").write_text(json.dumps(manifest), encoding="utf8")
    service = FreshService(seed=False)
    before = deepcopy(service.state)
    monkeypatch.setattr(PackagedMealSource, "DIRECTORY", directory)
    with pytest.raises((RuntimeError, ServiceError)):
        service.seed_recipes()
    assert service.state == before


@pytest.mark.parametrize(
    "measure", ["1 cup", "a pinch", "to taste", "1-2g", "", "0g", "-1g", "NaNg", "1 tbsp", "2"]
)
def test_new_mass_identity_keeps_ambiguous_and_incompatible_measures_rejected(measure):
    raw = json.loads((FIXTURES / "52901.json").read_bytes())["meals"][0]
    raw["strMeasure1"] = measure
    with pytest.raises(ServiceError):
        normalize_meal(raw)


def test_corpus_import_repeat_and_update_keep_ids_and_basket_references():
    service = FreshService(seed=False)
    corpus = list(PackagedMealSource().meals())
    service.source = Source(corpus)
    first = service.import_recipes()
    assert (first.imported, first.updated, first.total_recipes) == (15, 0, 15)
    selected = service.add_basket(BasketInput(recipe_id="rec_52901", servings=8))
    before = deepcopy(service.state)
    second = service.import_recipes()
    assert (second.imported, second.updated, second.total_recipes) == (0, 15, 15)
    assert service.state == before
    updated = deepcopy(next(m for m in corpus if m["idMeal"] == "52901"))
    updated["strMeal"] = "Newer live Rock Cakes title"
    updated["strMeasure1"] = "250g"
    service.source = Source([updated])
    assert service.import_recipes().updated == 1
    assert service.state.recipes["rec_52901"].title == updated["strMeal"]
    assert service.state.basket[selected.id] == selected
    service.seed_recipes()
    assert service.state.recipes["rec_52901"].title == updated["strMeal"]
    assert service.state.basket[selected.id] == selected


def test_unsupported_record_is_skipped_but_late_source_failure_is_atomic():
    service = FreshService(seed=False)
    corpus = list(PackagedMealSource().meals())
    rejected = deepcopy(corpus[-1])
    rejected["idMeal"] = "unsupported"
    rejected["strMeasure1"] = "1 cup"
    service.source = Source([*corpus, rejected])
    report = service.import_recipes()
    assert (report.imported, report.total_recipes, len(report.skipped)) == (15, 15, 1)
    assert report.skipped[0].reason == "Unsupported quantity '1 cup'"
    before = deepcopy(service.state)

    class LaterFailure:
        def meals(self):
            changed = deepcopy(corpus[0])
            changed["strMeal"] = "Never committed"
            yield changed
            raise ServiceError(502, "SOURCE_UNAVAILABLE", "Later source page failed")

    service.source = LaterFailure()
    with pytest.raises(ServiceError, match="Later source page failed"):
        service.import_recipes()
    assert service.state == before
