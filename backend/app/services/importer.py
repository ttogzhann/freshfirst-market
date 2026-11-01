"""TheMealDB adapter. External text is data; only explicit catalog identities are accepted."""

import hashlib
import json
import ssl
import string
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import ValidationError

from ..catalog import ALIASES, CATALOG
from ..errors import ServiceError, invalid
from ..models import Recipe, RecipeIngredient
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


def normalize_meal(meal: dict) -> Recipe:
    for key in ("idMeal", "strMeal", "strCategory", "strInstructions", "strMealThumb"):
        if not isinstance(meal.get(key), str) or not meal[key].strip():
            raise invalid(f"Missing required source field {key}")
    quantities = {}
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
        if ingredient_id is None:
            raise invalid(f"Unsupported ingredient identity {raw_name!r}")
        quantity = parse_measure(measure, CATALOG[ingredient_id].canonical_unit)
        quantities[ingredient_id] = quantities.get(ingredient_id, decimal(0)) + decimal(quantity)
    if not quantities:
        raise invalid("Recipe has no quantified ingredients")
    # TheMealDB has no yield field. One serving represents one complete source recipe
    # batch, explicitly described to users in the backend README; no guessed yield.
    try:
        return Recipe(
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
    except ValidationError as exc:
        raise invalid(f"Invalid source recipe: {exc}") from exc
