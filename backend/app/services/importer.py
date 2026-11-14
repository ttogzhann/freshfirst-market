"""TheMealDB adapter. External text is data; only explicit catalog identities are accepted."""

import hashlib
import json
import ssl
import string
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import ValidationError

from ..catalog import ALIASES, CATALOG
from ..errors import ServiceError, invalid
from ..ingredient_aliases import normalize_alias
from ..models import Ingredient, Recipe, RecipeIngredient
from .quantities import decimal, parse_measure, rounded


class MealSource(Protocol):
    def meals(self) -> Iterable[dict]: ...


class PackagedMealSource:
    """Reviewed genuine raw responses; corruption is a startup failure, never a skip."""

    DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "mealdb-source"
    REVIEWED_IDS = frozenset(
        {
            "53137",
            "52776",
            "53396",
            "53316",
            "53321",
            "53452",
            "53293",
            "52901",
            "53308",
            "53177",
            "53075",
            "53150",
            "53252",
            "53403",
            "53409",
        }
    )

    def meals(self):
        try:
            manifest = json.loads((self.DIRECTORY / "provenance.json").read_bytes())
            records = manifest["records"]
            if {r["external_id"] for r in records} != self.REVIEWED_IDS or len(records) != len(
                self.REVIEWED_IDS
            ):
                raise ValueError("Invalid reviewed corpus IDs")
            for record in records:
                external_id = record["external_id"]
                if (
                    record["raw_file"] != f"{external_id}.json"
                    or record["lookup_url"]
                    != f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={external_id}"
                    or datetime.fromisoformat(record["captured_at_utc"]).utcoffset() != timedelta(0)
                ):
                    raise ValueError("Invalid baseline provenance")
                raw = (self.DIRECTORY / record["raw_file"]).read_bytes()
                if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                    raise ValueError("Baseline hash mismatch")
                payload = json.loads(raw)
                meals = payload["meals"]
                if (
                    not isinstance(meals, list)
                    or len(meals) != 1
                    or not isinstance(meals[0], dict)
                    or meals[0].get("idMeal") != external_id
                ):
                    raise ValueError("Invalid baseline payload")
                yield meals[0]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("Packaged recipe baseline is invalid") from exc


class CuratedCatalogSource:
    """Reviewed original-authored records for the expanded production catalog."""

    PATH = Path(__file__).resolve().parents[1] / "data" / "catalog" / "manifest.json"

    def meals(self):
        try:
            manifest = json.loads(self.PATH.read_bytes())
            if manifest.get("catalog_version") != "ff68-original-v1":
                raise ValueError("Invalid catalog version")
            encoded = json.dumps(
                manifest.get("records"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            expected_hash = "sha256:" + hashlib.sha256(encoded).hexdigest()
            if manifest.get("catalog_hash") != expected_hash:
                raise ValueError("Catalog manifest hash mismatch")
            provenance = manifest["provenance"]
            required_provenance = {
                "source_name": "FreshFirst original-authored",
                "source_url": "original-authored://freshfirst/catalog/v1",
                "attribution": "Original recipes authored for FreshFirst; no external attribution claimed.",
                "captured_at_utc": "2026-11-14T00:00:00+00:00",
            }
            if provenance != required_provenance:
                raise ValueError("Invalid catalog provenance")
            records = manifest["records"]
            if not isinstance(records, list) or not 80 <= len(records) <= 100:
                raise ValueError("Catalog must contain 80-100 records")
            ids = [record.get("idMeal") for record in records]
            titles = [record.get("strMeal", "").strip().casefold() for record in records]
            if len(set(ids)) != len(ids) or len(set(titles)) != len(titles):
                raise ValueError("Catalog contains duplicate recipe identities")
            for record in records:
                if (
                    record.get("source_name") != provenance["source_name"]
                    or record.get("source_url", "").startswith("original-authored://") is False
                    or not record.get("strDescription", "").strip()
                    or not record.get("strPrepTime", "").isdigit()
                    or record.get("catalog_version") != manifest["catalog_version"]
                    or record.get("provenance")
                    != "Original recipe authored for FreshFirst; no external attribution claimed."
                ):
                    raise ValueError("Invalid catalog record metadata")
                title = record["strMeal"].strip()
                if title.startswith("FreshFirst ") and " Recipe " in title:
                    raise ValueError("Placeholder catalog title")
                ingredient_names = [
                    record.get(f"strIngredient{index}", "").strip()
                    for index in range(1, 21)
                    if record.get(f"strIngredient{index}", "").strip()
                ]
                if len(ingredient_names) < 3 or not all(
                    name.casefold() in record["strInstructions"].casefold()
                    for name in ingredient_names
                ):
                    raise ValueError("Catalog instructions are generic or incomplete")
                yield record
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Curated recipe catalog is invalid") from exc


class TheMealDBSource:
    BASE_URL = "https://www.themealdb.com/api/json/v1/1/"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client

    def meals(self):
        def read(client):
            seen = set()
            for letter in string.ascii_lowercase:
                response = client.get(self.BASE_URL + "search.php", params={"f": letter})
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or "meals" not in payload:
                    raise ValueError("Malformed TheMealDB response")
                meals = payload["meals"]
                if meals is None:
                    continue
                if not isinstance(meals, list) or any(not isinstance(m, dict) for m in meals):
                    raise ValueError("Malformed TheMealDB meal list")
                for meal in meals:
                    external_id = meal.get("idMeal")
                    if external_id not in seen:
                        seen.add(external_id)
                        yield meal

        try:
            if self.client is not None:
                yield from read(self.client)
            else:
                with httpx.Client(
                    timeout=httpx.Timeout(15, connect=5),
                    follow_redirects=False,
                    verify=ssl.create_default_context(),
                ) as client:
                    yield from read(client)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ServiceError(
                502,
                "SOURCE_UNAVAILABLE",
                "TheMealDB is unavailable or returned invalid data. "
                "Previously imported recipes are unchanged.",
            ) from exc


def _profiles(meal):
    profiles = meal.get("reviewed_ingredient_profiles", meal.get("ingredient_profiles", {}))
    if isinstance(profiles, list):
        profiles = {item.get("source_name"): item for item in profiles if isinstance(item, dict)}
    if not isinstance(profiles, dict):
        return {}
    return {normalize_alias(str(key)): value for key, value in profiles.items()}


def normalize_meal_with_audit(meal: dict, catalog=None, resolver=None):
    if catalog is None:
        catalog = CATALOG
    for key in ("idMeal", "strMeal", "strCategory", "strInstructions", "strMealThumb"):
        if not isinstance(meal.get(key), str) or not meal[key].strip():
            raise invalid(f"Missing required source field {key}")
    quantities = {}
    new_ingredients = {}
    source_lines = []
    profiles = _profiles(meal)
    for index in range(1, 21):
        raw_name = meal.get(f"strIngredient{index}")
        measure = meal.get(f"strMeasure{index}")
        raw_name = "" if raw_name is None else raw_name
        measure = "" if measure is None else measure
        if not isinstance(raw_name, str) or not isinstance(measure, str):
            raise invalid("Ingredient identities and quantities must be text")
        name = raw_name.strip().casefold()
        if not name:
            if measure.strip():
                raise invalid("Quantity without an ingredient")
            continue
        ingredient_id = ALIASES.get(name)
        if resolver is not None:
            match = resolver(raw_name)
            if match.status != "exact" and match.ingredient_ids:
                raise invalid(f"Ambiguous or unconfirmed ingredient identity {raw_name!r}")
            ingredient_id = match.ingredient_ids[0] if match.status == "exact" else None
        if ingredient_id is None:
            profile = profiles.get(normalize_alias(raw_name))
            if not isinstance(profile, dict):
                raise invalid(
                    f"Unsupported ingredient identity {raw_name!r}; "
                    "unreviewed identity profile required"
                )
            canonical_id = profile.get("canonical_id", profile.get("id"))
            display_name = profile.get("display_name", profile.get("name"))
            category = profile.get("category")
            canonical_unit = profile.get("canonical_unit", profile.get("dimension"))
            if not all(
                isinstance(value, str) and value.strip()
                for value in (canonical_id, display_name, category, canonical_unit)
            ) or canonical_unit not in {"g", "ml", "pcs"}:
                raise invalid(f"Invalid reviewed identity profile for {raw_name!r}")
            if canonical_id in catalog and catalog[canonical_id].model_dump() != {
                "id": canonical_id,
                "name": display_name.strip(),
                "category": category.strip(),
                "canonical_unit": canonical_unit,
            }:
                raise invalid(f"Conflicting canonical identity profile for {raw_name!r}")
            ingredient_id = canonical_id
            new_ingredients[canonical_id] = Ingredient(
                id=canonical_id,
                name=display_name.strip(),
                category=category.strip(),
                canonical_unit=canonical_unit,
            )
            catalog = {**catalog, canonical_id: new_ingredients[canonical_id]}
        quantity = parse_measure(measure, catalog[ingredient_id].canonical_unit)
        quantities[ingredient_id] = quantities.get(ingredient_id, decimal(0)) + decimal(quantity)
        source_lines.append(
            {
                "raw_name": raw_name,
                "raw_measure": measure,
                "ingredient_id": ingredient_id,
                "quantity_canonical": quantity,
                "unit": catalog[ingredient_id].canonical_unit,
            }
        )
    if not quantities:
        raise invalid("Recipe has no quantified ingredients")
    for ingredient_id, quantity in quantities.items():
        if decimal(quantity) <= 0:
            raise invalid(f"Ingredient quantity must be positive for {ingredient_id}")
    # TheMealDB has no yield field. One serving represents one complete source recipe
    # batch, explicitly described to users in the backend README; no guessed yield.
    try:
        recipe = Recipe(
            id=f"rec_{meal['idMeal']}",
            external_id=meal["idMeal"],
            title=meal["strMeal"].strip(),
            category=meal["strCategory"].strip(),
            instructions=meal["strInstructions"].strip(),
            image_url=meal["strMealThumb"].strip(),
            base_servings=1,
            ingredients=[
                RecipeIngredient(ingredient_id=i, quantity=rounded(q))
                for i, q in quantities.items()
            ],
        )
        aliases = []
        for ingredient_id in new_ingredients:
            source_name = next(
                line["raw_name"] for line in source_lines if line["ingredient_id"] == ingredient_id
            )
            normalized = normalize_alias(source_name)
            alias_id = (
                "alias_import_"
                + hashlib.sha256(f"{normalized}|en|{ingredient_id}".encode("utf-8")).hexdigest()[
                    :32
                ]
            )
            aliases.append(
                {
                    "id": alias_id,
                    "ingredient_id": ingredient_id,
                    "locale": "en",
                    "alias_text": source_name.strip(),
                    "normalized_text": normalized,
                    "alias_type": "source",
                    "confidence": 1,
                    "provenance": meal.get("source_name", "reviewed-source"),
                }
            )
        source = {
            "source_name": meal.get("source_name", "TheMealDB"),
            "source_url": meal.get(
                "source_url",
                meal.get(
                    "lookup_url",
                    f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal['idMeal']}",
                ),
            ),
            "captured_at": meal.get("captured_at", meal.get("captured_at_utc", "unknown")),
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "description": meal.get("strDescription", ""),
            "prep_time_minutes": meal.get("strPrepTime", ""),
            "catalog_version": meal.get("catalog_version", ""),
            "provenance": meal.get("provenance", ""),
        }
        return recipe, tuple(new_ingredients.values()), tuple(aliases), tuple(source_lines), source
    except ValidationError as exc:
        raise invalid(f"Invalid source recipe: {exc}") from exc


def normalize_meal(meal: dict, catalog=None, resolver=None) -> Recipe:
    return normalize_meal_with_audit(meal, catalog, resolver)[0]
