"""Fail-closed editorial/quantity checks for the explicitly authored catalog.

These checks reject known padding and metadata defects; they do not certify
kitchen testing. Culinary review remains an independent QA responsibility.
"""

import hashlib
import json
import re

from ..catalog import ALIASES, CATALOG
from .quantities import parse_measure

VERSION = "ff68-original-v2"
ATTRIBUTION = (
    "AI-assisted original recipes revised for FreshFirst; not kitchen-tested; "
    "no external attribution claimed."
)
RECORD_PROVENANCE = (
    "AI-assisted original recipe revised for FreshFirst; not kitchen-tested; "
    "no external attribution claimed."
)
# These ordinary cooking basics must not manufacture a distinct recipe.
BASICS = {"water", "salt", "black_pepper", "olive_oil", "vegetable_oil", "butter"}
# Explicit title vocabulary, not an inferred conversion/ingredient identity rule.
DEFINING = {
    "spinach": {"spinach"},
    "cheddar": {"cheese"},
    "egg": {"egg"},
    "eggs": {"egg"},
    "omelet": {"egg"},
    "frittata": {"egg"},
    "chicken": {"chicken"},
    "beef": {"beef"},
    "salmon": {"salmon"},
    "rice": {"rice"},
    "garlic": {"garlic"},
    "tomato": {"tomato", "tomato_sauce"},
    "lemon": {"lemon"},
    "mushroom": {"mushroom"},
    "mushrooms": {"mushroom"},
    "cream": {"cream"},
    "creamy": {"cream", "milk", "cheese"},
    "carrot": {"carrot"},
    "carrots": {"carrot"},
    "potato": {"potato"},
    "pepper": {"pepper"},
    "peppers": {"pepper"},
    "vanilla": {"vanilla"},
    "butter": {"butter", "unsalted_butter", "melted_butter"},
    "banana": {"banana"},
    "oat": {"oats"},
    "oats": {"oats"},
    "honey": {"honey"},
    "cocoa": {"cocoa"},
    "chocolate": {"plain_chocolate"},
    "parsley": {"parsley"},
    "yogurt": {"yogurt"},
    "beetroot": {"beetroot"},
    "apple": {"apple"},
    "cinnamon": {"ground_cinnamon"},
    "soy": {"soy_sauce"},
    "noodles": {"vermicelli_pasta"},
    "vermicelli": {"vermicelli_pasta"},
    "pasta": {"pasta", "vermicelli_pasta"},
    "penne": {"pasta"},
    "spaghetti": {"pasta"},
    "toast": {"bread"},
    "bread": {"bread"},
    "cheese": {"cheese", "parmesan"},
    "parmesan": {"parmesan"},
    "walnut": {"walnuts", "ground_walnuts"},
    "berry": {"frozen_mixed_berries", "raspberries"},
    "mascarpone": {"mascarpone"},
    "coconut": {"coconut_flakes"},
    "pumpkin": {"pumpkin"},
    "eggplant": {"eggplant"},
    "chorizo": {"chorizo"},
}


class CatalogValidationError(RuntimeError):
    """A machine-readable exclusion reason; a package failure admits no records."""

    def __init__(self, code, external_id=None):
        self.code = code
        self.external_id = external_id
        super().__init__(f"Curated recipe catalog is invalid: {code} ({external_id or 'manifest'})")

    def as_dict(self):
        return {"code": self.code, "external_id": self.external_id}


def records_hash(records):
    encoded = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf8")).hexdigest()


def validate_catalog(manifest):
    """Validate the complete package before returning even its first record."""
    if not isinstance(manifest, dict) or manifest.get("catalog_version") != VERSION:
        raise CatalogValidationError("INVALID_VERSION")
    records = manifest.get("records")
    if not isinstance(records, list) or not 80 <= len(records) <= 100:
        raise CatalogValidationError("INVALID_COUNT")
    if manifest.get("catalog_hash") != records_hash(records):
        raise CatalogValidationError("HASH_MISMATCH")
    if manifest.get("provenance") != {
        "source_name": "FreshFirst original-authored",
        "source_url": "original-authored://freshfirst/catalog/v1",
        "attribution": ATTRIBUTION,
        "captured_at_utc": "2026-11-14T00:00:00+00:00",
        "reviewed_at_utc": "2026-11-14T00:00:00+00:00",
    }:
        raise CatalogValidationError("INVALID_PROVENANCE")
    ids, titles, signatures = set(), set(), set()
    for record in records:
        if not isinstance(record, dict):
            raise CatalogValidationError("INVALID_RECORD")
        identity = record.get("idMeal")
        if not isinstance(identity, str) or not re.fullmatch(r"ff-original-\d{3}", identity):
            raise CatalogValidationError("INVALID_ID", str(identity))
        title = record.get("strMeal", "")
        if not isinstance(title, str) or not title.strip():
            raise CatalogValidationError("MISSING_TITLE", identity)
        normalized_title = " ".join(title.casefold().split())
        if identity in ids or normalized_title in titles:
            raise CatalogValidationError("DUPLICATE_IDENTITY", identity)
        ids.add(identity)
        titles.add(normalized_title)
        if (
            record.get("source_name") != "FreshFirst original-authored"
            or record.get("source_url") != f"original-authored://freshfirst/catalog/v1/{identity}"
            or record.get("strMealThumb") != record["source_url"]
            or record.get("captured_at_utc") != "2026-11-14T00:00:00+00:00"
            or record.get("reviewed_at_utc") != "2026-11-14T00:00:00+00:00"
            or record.get("catalog_version") != VERSION
            or record.get("provenance") != RECORD_PROVENANCE
        ):
            raise CatalogValidationError("INVALID_RECORD_PROVENANCE", identity)
        if not all(
            isinstance(record.get(k), str) and record[k].strip()
            for k in ("strCategory", "strDescription", "strInstructions")
        ):
            raise CatalogValidationError("MISSING_METADATA", identity)
        if not isinstance(record.get("strPrepTime"), str) or not record["strPrepTime"].isdigit():
            raise CatalogValidationError("INVALID_PREPARATION_TIME", identity)
        prep = int(record["strPrepTime"])
        cook, extra, portions = (
            record.get(k)
            for k in ("cooking_time_minutes", "additional_time_minutes", "authored_portions")
        )
        if not 1 <= prep <= 120 or any(type(x) is not int for x in (cook, extra, portions)):
            raise CatalogValidationError("INVALID_TIMING_OR_YIELD", identity)
        if not (
            0 <= cook <= 180
            and 0 <= extra <= 240
            and 1 <= portions <= 8
            and record.get("base_servings") == 1
        ):
            raise CatalogValidationError("INVALID_TIMING_OR_YIELD", identity)
        expected_heading = (
            f"One batch makes {portions} portions. Preparation: {prep} minutes; "
            f"cooking: {cook} minutes; additional resting/chilling: {extra} minutes. "
        )
        instructions = record["strInstructions"]
        if not instructions.startswith(expected_heading):
            raise CatalogValidationError("INCONSISTENT_YIELD_OR_TIMING", identity)
        method = instructions[len(expected_heading) :].casefold()
        if (
            len(method) < 300
            or "cook the ingredients in sequence" in method
            or "season to taste" in method
            or "fully done" in method
            or not re.search(r"\d+(?: to \d+)? minutes?", method)
            or not re.search(r"heat|bake|fry|boil|simmer|refrigerate|without cooking", method)
        ):
            raise CatalogValidationError("GENERIC_INSTRUCTIONS", identity)
        ingredient_ids = set()
        for index in range(1, 21):
            name, measure = record.get(f"strIngredient{index}"), record.get(f"strMeasure{index}")
            if not name and not measure:
                continue
            if not isinstance(name, str) or not isinstance(measure, str):
                raise CatalogValidationError("UNRESOLVED_INGREDIENT_LINE", identity)
            ingredient_id = ALIASES.get(name.strip().casefold())
            if ingredient_id is None or ingredient_id in ingredient_ids:
                raise CatalogValidationError("UNKNOWN_OR_DUPLICATE_INGREDIENT", identity)
            ingredient_ids.add(ingredient_id)
            try:
                parse_measure(measure, CATALOG[ingredient_id].canonical_unit)
            except Exception as exc:
                raise CatalogValidationError("INVALID_QUANTITY_OR_UNIT", identity) from exc
        if any(
            re.fullmatch(r"str(?:Ingredient|Measure)\d+", k) and int(re.search(r"\d+", k)[0]) > 20
            for k in record
        ):
            raise CatalogValidationError("UNACCOUNTED_INGREDIENT_SLOT", identity)
        if len(ingredient_ids) < 3:
            raise CatalogValidationError("INSUFFICIENT_INGREDIENTS", identity)
        signature = frozenset(ingredient_ids - BASICS)
        if signature in signatures:
            raise CatalogValidationError("DUPLICATE_CORE_INGREDIENTS", identity)
        signatures.add(signature)
        for word in re.findall(r"[a-z]+", normalized_title):
            if word in DEFINING and not ingredient_ids.intersection(DEFINING[word]):
                raise CatalogValidationError("MISSING_DEFINING_INGREDIENT", identity)
        if record["strCategory"] in {"Vegetarian", "Salad"} and ingredient_ids.intersection(
            {"chicken", "beef", "salmon", "bacon", "chorizo", "stock"}
        ):
            raise CatalogValidationError("MISLEADING_CATEGORY", identity)
    return records
