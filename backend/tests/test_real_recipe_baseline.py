"""Independent expected quantities for unaltered, source-backed MVP candidates."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.catalog import ALIASES, CATALOG, RULE_CATEGORIES, RULES
from app.errors import ServiceError
from app.services.importer import normalize_meal

FIXTURES = Path(__file__).parent / "fixtures" / "mealdb-source"

# Transcribed from the raw ingredient/measure fields, not derived by the parser.
# ml factors are the specification's exact tbsp=15 / tsp=5 / litre=1000.
EXPECTED_LINES = {
    "53137": [
        ("Milk", "1 Litre", "milk", "ml", 1000),
        ("Sugar", "300g", "sugar", "g", 300),
        ("Baking Powder", "1/4 tsp", "baking_powder", "ml", 1.25),
        ("Vanilla Extract", "1 teaspoon", "vanilla", "ml", 5),
    ],
    "52776": [
        ("Plain chocolate", "250g", "plain_chocolate", "g", 250),
        ("Butter", "175g", "butter", "g", 175),
        ("Milk", "2 tablespoons", "milk", "ml", 30),
        ("Eggs", "5", "egg", "pcs", 5),
        ("Granulated Sugar", "175g", "sugar", "g", 175),
        ("Flour", "125g", "flour", "g", 125),
    ],
}


def raw_meal(external_id):
    payload = json.loads((FIXTURES / f"{external_id}.json").read_bytes())
    assert len(payload["meals"]) == 1
    return payload["meals"][0]


@pytest.mark.parametrize("external_id", EXPECTED_LINES)
def test_source_capture_provenance_and_complete_ingredient_accounting(external_id):
    provenance = json.loads((FIXTURES / "provenance.json").read_text(encoding="utf8"))
    record = next(r for r in provenance["records"] if r["external_id"] == external_id)
    assert record["lookup_url"] == (
        f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={external_id}"
    )
    assert record["captured_at_utc"].startswith("2026-10-20T")
    assert (
        hashlib.sha256((FIXTURES / record["raw_file"]).read_bytes()).hexdigest()
        == (record["sha256"])
    )
    meal = raw_meal(external_id)
    assert meal["idMeal"] == external_id
    for field in ("strMeal", "strCategory", "strInstructions", "strMealThumb"):
        assert meal[field].strip()
    actual = [
        (meal.get(f"strIngredient{i}"), meal.get(f"strMeasure{i}"))
        for i in range(1, 21)
        if (meal.get(f"strIngredient{i}") or "").strip()
        or (meal.get(f"strMeasure{i}") or "").strip()
    ]
    assert actual == [(name, measure) for name, measure, *_ in EXPECTED_LINES[external_id]]


@pytest.mark.parametrize("external_id", EXPECTED_LINES)
def test_real_baseline_exact_totals_without_guessed_yield(external_id):
    recipe = normalize_meal(raw_meal(external_id))
    assert recipe.external_id == external_id
    assert recipe.base_servings == 1  # Whole source batch, never inferred human yield.
    expected = {identity: quantity for _, _, identity, _, quantity in EXPECTED_LINES[external_id]}
    assert {line.ingredient_id: line.quantity for line in recipe.ingredients} == expected
    for _, _, identity, unit, _ in EXPECTED_LINES[external_id]:
        assert CATALOG[identity].canonical_unit == unit


def test_real_baseline_has_distinct_ids_and_shared_canonical_stock():
    recipes = [normalize_meal(raw_meal(external_id)) for external_id in EXPECTED_LINES]
    assert len({recipe.external_id for recipe in recipes}) == 2
    identities = [{line.ingredient_id for line in recipe.ingredients} for recipe in recipes]
    assert identities[0] & identities[1] == {"milk", "sugar"}


@pytest.mark.parametrize("measure", ["1 cup", "to taste", "1-2 g", "2 tablespoons", "2"])
def test_chocolate_measure_is_not_guessed_or_cross_dimension(measure):
    meal = deepcopy(raw_meal("52776"))
    meal["strMeasure1"] = measure
    with pytest.raises(ServiceError):
        normalize_meal(meal)


def test_plain_chocolate_is_not_cocoa_or_unspecified_chocolate():
    chocolate = normalize_meal(raw_meal("52776"))
    assert chocolate.ingredients[0].ingredient_id == "plain_chocolate"
    meal = deepcopy(raw_meal("52776"))
    meal["strIngredient1"] = "Cocoa powder"
    assert normalize_meal(meal).ingredients[0].ingredient_id == "cocoa"
    meal["strIngredient1"] = "Chocolate"
    with pytest.raises(ServiceError, match="Unsupported ingredient identity"):
        normalize_meal(meal)


def test_additive_identity_preserves_existing_catalog_aliases_and_rules():
    assert CATALOG["plain_chocolate"].model_dump() == {
        "id": "plain_chocolate",
        "name": "Plain chocolate",
        "category": "Pantry staples",
        "canonical_unit": "g",
    }
    assert {name for name, identity in ALIASES.items() if identity == "plain_chocolate"} == {
        "plain chocolate"
    }
    # Frozen independently before the single additive catalog row, at baseline
    # 66dbf65f176cc4174d5c184a3e6d9de43f240e67. Covers all old fields and aliases,
    # not just the count, plus every rule/category eligibility restriction.
    frozen = json.loads(
        (Path(__file__).parent / "fixtures" / "mealdb-breadth" / "previous-catalog.json").read_text(
            encoding="utf8"
        )
    )
    previous = {
        "catalog": {
            key: value.model_dump(mode="json")
            for key, value in CATALOG.items()
            if key in frozen["catalog"] and key != "plain_chocolate"
        },
        "aliases": {
            key: ALIASES[key]
            for key, value in frozen["aliases"].items()
            if value != "plain_chocolate"
        },
        "rules": {key: value.model_dump(mode="json") for key, value in RULES.items()},
        "rule_categories": {key: sorted(value) for key, value in RULE_CATEGORIES.items()},
    }
    assert len(previous["catalog"]) == 40
    assert hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest() == (
        "a937adb5d1c676f0f0d541e5a8c1e031ee450d337ffa089255ec9af00478f10e"
    )
