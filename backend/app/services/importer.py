"""TheMealDB adapter. External text is data; only explicit catalog identities are accepted."""

import ssl
import string
from collections.abc import Iterable
from typing import Protocol

import httpx
from pydantic import ValidationError

from ..catalog import ALIASES, CATALOG
from ..errors import ServiceError, invalid
from ..models import Recipe, RecipeIngredient
from .quantities import decimal, parse_measure, rounded


class MealSource(Protocol):
    def meals(self) -> Iterable[dict]: ...


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
