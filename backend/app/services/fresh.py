"""Inventory and recipe business rules, independent of HTTP routing."""

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from threading import Lock

from sqlalchemy import select

from ..catalog import RULE_CATEGORIES, RULES
from ..config import expiry_days as validate_expiry_days
from ..errors import ServiceError, invalid, missing
from ..ingredient_aliases import normalization_variants, normalize_alias
from ..models import (
    BasketItem,
    BasketItemWithRecipe,
    BasketView,
    Consumption,
    CookingRecord,
    CookPreview,
    Dashboard,
    DemandLine,
    ImportReport,
    ImportSkip,
    IngredientAutocomplete,
    MatchInfo,
    PantryItem,
    RecipeDetail,
    RecipeSummary,
    ShoppingItem,
    SubstitutionSuggestion,
)
from ..store import SQLiteStore, ingredient_aliases
from .allocation import Allocation, allocate
from .importer import (
    CuratedCatalogSource,
    PackagedMealSource,
    TheMealDBSource,
    normalize_meal_with_audit,
)
from .quantities import FACTORS, decimal, normalize, positive_rounded, rounded, scale


def atomic(method):
    @wraps(method)
    def invoke(self, *args, **kwargs):
        with self.store.transaction():
            # Detach all returned values before releasing the lock.
            return deepcopy(method(self, *args, **kwargs))

    return invoke


class FreshService:
    def __init__(self, store=None, source=None, today=date.today, seed=True, expiry_days=3):
        self.expiry_days = validate_expiry_days(expiry_days)
        self.store = store if store is not None else SQLiteStore()
        self.source = source if source is not None else TheMealDBSource()
        self.today = today
        self.import_lock = Lock()
        if seed:
            self.seed_pantry()

    @property
    def state(self):
        return self.store.state

    def for_owner(self, owner_id):
        service = object.__new__(FreshService)
        service.expiry_days = self.expiry_days
        service.store = self.store.scoped(owner_id)
        service.source = self.source
        service.today = self.today
        service.import_lock = self.import_lock
        return service

    def seed_pantry(self):
        with self.store.transaction():
            if self.state.pantry_seeded:
                return
            self.state.pantry_seeded = True
            if self.state.pantry:
                return
            for ingredient_id, quantity, days in [
                ("egg", 6, 10),
                ("spinach", 120, 2),
                ("chicken", 400, 1),
                ("rice", 1000, 200),
                ("milk", 500, -1),
                ("butter", 200, 30),
                ("garlic", 6, 20),
                ("cheese", 150, 12),
                ("soy_sauce", 250, 180),
                ("onion", 3, 15),
                ("pasta", 500, 300),
                ("tomato", 2, 3),
            ]:
                pid = self.store.next_id("p")
                self.state.pantry[pid] = PantryItem(
                    id=pid,
                    ingredient_id=ingredient_id,
                    quantity=quantity,
                    expiry_date=self.today() + timedelta(days=days),
                )

    def ingredient(self, ingredient_id):
        if ingredient_id not in self.store.catalog:
            raise invalid("Choose an ingredient from the supported catalog")
        return self.store.catalog[ingredient_id]

    @property
    def catalog(self):
        return self.store.catalog

    def recipe(self, recipe_id):
        if recipe_id not in self.state.recipes:
            raise missing("Recipe")
        return self.state.recipes[recipe_id]

    def find(self, collection, item_id, label):
        if item_id not in collection:
            raise missing(label)
        return collection[item_id]

    def stock(self):
        return self.stock_for()

    def allocation(self, ingredient_id, required):
        ingredient = self.ingredient(ingredient_id)
        return allocate(
            self.state.pantry.values(),
            ingredient_id,
            ingredient.canonical_unit,
            required,
            self.today(),
        )

    def stock_for(self, ingredient_ids=None):
        ids = ingredient_ids or self.catalog.keys()
        return {
            ingredient_id: result.available
            for ingredient_id in ids
            if (result := self.allocation(ingredient_id, 0)).available > 0
        }

    def demands(self, recipe, servings, substitutions):
        selected = {}
        for sub in substitutions:
            rule = RULES.get(sub.rule_id)
            if (
                rule is None
                or rule.original_ingredient_id != sub.original_ingredient_id
                or rule.substitute_ingredient_id != sub.substitute_ingredient_id
                or sub.original_ingredient_id in selected
                or not any(
                    i.ingredient_id == sub.original_ingredient_id for i in recipe.ingredients
                )
                or recipe.category not in RULE_CATEGORIES[rule.id]
            ):
                raise invalid("Invalid, duplicate, or context-incompatible substitution")
            # No rule with incompatible stock dimensions is eligible.
            if (
                self.catalog[rule.original_ingredient_id].canonical_unit
                != self.catalog[rule.substitute_ingredient_id].canonical_unit
            ):
                raise invalid("Substitution requires an unsupported unit conversion")
            selected[sub.original_ingredient_id] = rule
        demands = []
        for ingredient in recipe.ingredients:
            quantity = scale(ingredient.quantity, servings, recipe.base_servings)
            rule = selected.get(ingredient.ingredient_id)
            if rule:
                demands.append(
                    (
                        rule.substitute_ingredient_id,
                        positive_rounded(decimal(quantity) * decimal(rule.ratio)),
                        ingredient.ingredient_id,
                    )
                )
            else:
                demands.append((ingredient.ingredient_id, quantity, None))
        return demands

    @staticmethod
    def aggregate(demands):
        total = defaultdict(lambda: decimal(0))
        for ingredient_id, quantity, _ in demands:
            total[ingredient_id] += decimal(quantity)
        return dict(total)

    def lines(self, demands):
        aggregate = self.aggregate(demands)
        allocations = {i: self.allocation(i, q) for i, q in aggregate.items()}
        return [
            self._line(i, q, original, allocations[i], aggregate[i]) for i, q, original in demands
        ]

    def feasible_servings(self, recipe, substitutions):
        """Return the greatest fully covered recipe quantity in the supported range."""
        feasible = 0
        for servings in range(1, 9):
            if all(
                line.sufficient
                for line in self.lines(self.demands(recipe, servings, substitutions))
            ):
                feasible = servings
            else:
                # Requirements only grow with servings, so later counts cannot recover.
                break
        return feasible

    def limiting_lines(self, recipe, substitutions, feasible):
        if feasible >= 8:
            return []
        lines = self.lines(self.demands(recipe, max(1, feasible + 1), substitutions))
        return [line.ingredient_id for line in lines if not line.sufficient]

    def _line(
        self, ingredient_id, required, substituted_from, result: Allocation, aggregate_required
    ):
        allocated = min(result.allocated, decimal(required))
        return DemandLine(
            ingredient_id=ingredient_id,
            name=self.catalog[ingredient_id].name,
            unit=self.catalog[ingredient_id].canonical_unit,
            required=required,
            available=result.available,
            allocated=allocated,
            missing=max(decimal(0), decimal(required) - allocated),
            sufficient=result.allocated >= decimal(aggregate_required),
            allocations=[
                {"lot_id": lot.lot_id, "expiry_date": lot.expiry_date, "quantity": lot.quantity}
                for lot in result.lots
            ],
            substituted_from=substituted_from,
        )

    def summary(self, recipe):
        missing_names, expiring = [], []
        covered = 0
        for line in recipe.ingredients:
            name = self.catalog[line.ingredient_id].name
            result = self.allocation(line.ingredient_id, line.quantity)
            if result.sufficient:
                covered += 1
            else:
                missing_names.append(name)
            if result.sufficient and any(
                0 <= (lot.expiry_date - self.today()).days <= self.expiry_days
                for lot in result.lots
            ):
                expiring.append(name)
        total = len(recipe.ingredients)
        score = (
            int(decimal(covered * 100 / total).quantize(decimal(1), rounding="ROUND_HALF_UP"))
            if total
            else 0
        )
        return RecipeSummary(
            **recipe.model_dump(),
            match=MatchInfo(
                score=score,
                covered=covered,
                total=total,
                missing=missing_names,
                expiring_used=expiring,
            ),
        )

    @staticmethod
    def rank(recipes):
        return sorted(
            recipes, key=lambda r: (-r.match.score, -len(r.match.expiring_used), r.title.casefold())
        )

    def validate_new_choices(self, recipe, servings, substitutions, previous=()):
        demands = self.demands(recipe, servings, substitutions)
        total = self.aggregate(demands)
        for sub in substitutions:
            if (
                sub not in previous
                and not self.allocation(
                    sub.substitute_ingredient_id, total[sub.substitute_ingredient_id]
                ).sufficient
            ):
                raise invalid("The selected substitute has insufficient usable stock")

    def list_ingredients(self):
        return list(self.catalog.values())

    def autocomplete_ingredients(self, query):
        """Return deterministic catalog/alias matches for an authenticated owner."""
        normalized = normalize_alias(query)
        if not normalized:
            return []
        variants = set(normalization_variants(query))
        with self.store.engine.connect() as connection:
            rows = list(connection.execute(select(ingredient_aliases)).mappings())
        matches = []
        for row in rows:
            text = row["normalized_text"]
            row_variants = normalization_variants(row["alias_text"])
            if (
                not set(row_variants).intersection(variants)
                and not text.startswith(normalized)
                and normalized not in text
            ):
                continue
            ingredient = self.catalog.get(row["ingredient_id"])
            if ingredient is None:
                continue
            matches.append(
                IngredientAutocomplete(
                    ingredient_id=ingredient.id,
                    canonical_name=ingredient.name,
                    category=ingredient.category,
                    canonical_unit=ingredient.canonical_unit,
                    matched_alias=row["alias_text"],
                    locale=row["locale"],
                )
            )
        # A canonical ingredient is one candidate even when several reviewed aliases
        # match. Rank exact/shorter aliases first so the selected display is stable
        # regardless of database row order.
        ranked = sorted(
            matches,
            key=lambda item: (
                0 if set(normalization_variants(item.matched_alias)).intersection(variants) else 1,
                len(normalize_alias(item.matched_alias)),
                item.matched_alias.casefold(),
                item.locale.casefold(),
                item.ingredient_id,
            ),
        )
        unique = {}
        for item in ranked:
            unique.setdefault(item.ingredient_id, item)
        return sorted(
            unique.values(),
            key=lambda item: (
                item.canonical_name.casefold(),
                item.matched_alias.casefold(),
                item.locale.casefold(),
            ),
        )[:20]

    def list_rules(self):
        return list(RULES.values())

    def list_pantry(self):
        result = []
        for item in self.state.pantry.values():
            result.append(self._present_pantry(item))
        return result

    def _present_pantry(self, item):
        return item.model_copy(update={"resolution_candidates": self._resolution_candidates(item)})

    def _resolution_candidates(self, item):
        if item.resolution_status not in {"ambiguous", "suggested"} or not item.original_label:
            return []
        match = self.store.resolve_alias(item.original_label)
        return [self.catalog[ingredient_id] for ingredient_id in match.ingredient_ids]

    def merge_pantry(
        self,
        ingredient_id,
        quantity,
        expiry_date,
        *,
        original_label=None,
        normalized_label=None,
        original_unit=None,
        canonical_dimension=None,
        resolution_status="resolved",
        quantity_entered=None,
    ):
        canonical_dimension = canonical_dimension or (
            self.catalog[ingredient_id].canonical_unit if ingredient_id else None
        )
        existing = next(
            (
                p
                for p in self.state.pantry.values()
                if p.ingredient_id == ingredient_id
                and p.canonical_dimension == canonical_dimension
                and p.expiry_date == expiry_date
                and p.resolution_status == resolution_status
                and (ingredient_id or p.normalized_label == normalized_label)
            ),
            None,
        )
        if existing:
            existing.quantity = rounded(decimal(existing.quantity) + decimal(quantity))
            entered_unit = existing.original_unit or original_unit
            factor = FACTORS.get(entered_unit, (None, 1))[1]
            existing.quantity_entered = rounded(decimal(existing.quantity) / decimal(factor))
            return existing
        item = PantryItem(
            id=self.store.next_id("p"),
            ingredient_id=ingredient_id,
            quantity=quantity,
            expiry_date=expiry_date,
            quantity_entered=quantity_entered or quantity,
            original_unit=original_unit,
            canonical_dimension=canonical_dimension,
            original_label=original_label,
            normalized_label=normalized_label,
            resolution_status=resolution_status,
        )
        self.state.pantry[item.id] = item
        return item

    def _pantry_identity(self, data):
        if data.ingredient_id:
            ing = self.ingredient(data.ingredient_id)
            label = data.label or ing.name
            return (
                ing.id,
                label,
                normalize_alias(label),
                data.unit,
                ing.canonical_unit,
                "resolved",
            )
        match = self.store.resolve_alias(data.label)
        status = {
            "exact": "resolved",
            "suggestion": "suggested",
            "ambiguous": "ambiguous",
            "unresolved": "unresolved",
        }[match.status]
        # Suggestions are deliberately unresolved until a user confirms the ID.
        ingredient_id = match.ingredient_ids[0] if status == "resolved" else None
        dimension = FACTORS[data.unit][0]
        return (
            ingredient_id,
            data.label,
            normalize_alias(data.label),
            data.unit,
            dimension,
            status,
        )

    def create_pantry(self, data):
        identity = self._pantry_identity(data)
        with self.store.transaction():
            result = deepcopy(self._save_pantry_input(data, identity))
        return self._present_pantry(result)

    def _save_pantry_input(self, data, identity):
        ingredient_id, label, normalized_label, original_unit, dimension, status = identity
        quantity = normalize(data.quantity, data.unit, dimension)
        if status == "resolved":
            quantity = normalize(
                data.quantity, data.unit, self.catalog[ingredient_id].canonical_unit
            )
        return self.merge_pantry(
            ingredient_id,
            quantity,
            data.expiry_date,
            original_label=label,
            normalized_label=normalized_label,
            original_unit=original_unit,
            canonical_dimension=dimension,
            resolution_status=status,
            quantity_entered=data.quantity,
        )

    def update_pantry(self, item_id, data):
        identity = self._pantry_identity(data)
        with self.store.transaction():
            item = self.find(self.state.pantry, item_id, "Pantry item")
            ingredient_id, label, normalized_label, original_unit, dimension, status = identity
            quantity = normalize(data.quantity, data.unit, dimension)
            if status == "resolved":
                quantity = normalize(
                    data.quantity, data.unit, self.catalog[ingredient_id].canonical_unit
                )
            duplicate = any(
                p.id != item_id
                and p.ingredient_id == ingredient_id
                and p.canonical_dimension == dimension
                and p.expiry_date == data.expiry_date
                and p.resolution_status == status
                and (ingredient_id or p.normalized_label == normalized_label)
                for p in self.state.pantry.values()
            )
            if duplicate:
                raise ServiceError(409, "DUPLICATE_LOT", "An equivalent pantry lot already exists.")
            (
                item.ingredient_id,
                item.quantity,
                item.expiry_date,
                item.quantity_entered,
                item.original_unit,
                item.canonical_dimension,
                item.original_label,
                item.normalized_label,
                item.resolution_status,
            ) = (
                ingredient_id,
                quantity,
                data.expiry_date,
                data.quantity,
                original_unit,
                dimension,
                label,
                normalized_label,
                status,
            )
            result = deepcopy(item)
        return self._present_pantry(result)

    def resolve_pantry(self, item_id, ingredient_id):
        current = self.find(self.state.pantry, item_id, "Pantry item")
        if (
            current.resolution_status not in {"ambiguous", "suggested"}
            or not current.original_label
        ):
            raise ServiceError(
                409, "RESOLUTION_NOT_PENDING", "This pantry entry does not need resolution."
            )
        match = self.store.resolve_alias(current.original_label)
        if ingredient_id not in match.ingredient_ids:
            raise invalid("Choose one of the suggested canonical ingredients")
        ingredient = self.ingredient(ingredient_id)
        with self.store.transaction():
            item = self.find(self.state.pantry, item_id, "Pantry item")
            quantity = normalize(
                item.quantity_entered, item.original_unit, ingredient.canonical_unit
            )
            duplicate = any(
                other.id != item_id
                and other.ingredient_id == ingredient_id
                and other.canonical_dimension == ingredient.canonical_unit
                and other.expiry_date == item.expiry_date
                and other.resolution_status == "resolved"
                for other in self.state.pantry.values()
            )
            if duplicate:
                raise ServiceError(409, "DUPLICATE_LOT", "An equivalent pantry lot already exists.")
            item.ingredient_id = ingredient_id
            item.quantity = quantity
            item.canonical_dimension = ingredient.canonical_unit
            item.resolution_status = "resolved"
            result = deepcopy(item)
        return self._present_pantry(result)

    @atomic
    def delete_pantry(self, item_id):
        self.find(self.state.pantry, item_id, "Pantry item")
        del self.state.pantry[item_id]

    @atomic
    def list_recipes(self, query=None, category=None, sort="match"):
        recipes = [
            self.summary(r)
            for r in self.state.recipes.values()
            if (not query or query.strip().casefold() in r.title.casefold())
            and (not category or r.category == category)
        ]
        return (
            sorted(recipes, key=lambda r: r.title.casefold())
            if sort == "title"
            else self.rank(recipes)
        )

    @atomic
    def get_recipe(self, recipe_id, servings=None, substitutions=()):
        recipe = self.recipe(recipe_id)
        servings = servings if servings is not None else recipe.base_servings
        demands = self.demands(recipe, servings, substitutions)
        lines = self.lines(demands)
        feasible = self.feasible_servings(recipe, substitutions)
        suggestions = []
        for line in lines:
            if line.sufficient or line.substituted_from:
                continue
            for rule in RULES.values():
                if (
                    rule.original_ingredient_id != line.ingredient_id
                    or recipe.category not in RULE_CATEGORIES[rule.id]
                ):
                    continue
                substitute = self.catalog[rule.substitute_ingredient_id]
                if substitute.canonical_unit != line.unit:
                    continue
                required = positive_rounded(decimal(line.required) * decimal(rule.ratio))
                others = sum(decimal(q) for i, q, _ in demands if i == substitute.id)
                if not self.allocation(substitute.id, decimal(required) + others).sufficient:
                    continue
                suggestions.append(
                    SubstitutionSuggestion(
                        rule=rule,
                        original_name=line.name,
                        substitute_name=substitute.name,
                        required=required,
                        unit=substitute.canonical_unit,
                    )
                )
                break
        return RecipeDetail(
            **self.summary(recipe).model_dump(),
            servings=servings,
            original_servings=recipe.base_servings,
            adapted_servings=servings,
            feasible_servings=feasible,
            limiting_lines=self.limiting_lines(recipe, substitutions, feasible),
            lines=lines,
            suggestions=suggestions,
        )

    def seed_recipes(self, include_catalog=False):
        # Validate the complete package before writing anything. Unlike live import,
        # unsupported baseline records are fatal and existing records are never replaced.
        sources = [PackagedMealSource()]
        if include_catalog:
            sources.append(CuratedCatalogSource())
        accepted = [
            (normalize_meal_with_audit(raw, self.catalog, self.store.resolve_alias), raw)
            for source in sources
            for raw in source.meals()
        ]
        with self.store.transaction():
            for normalized, raw in accepted:
                recipe, _, _, source_lines, source = normalized
                self._upsert_recipe(recipe, missing_only=True)
                self.store.stage_import_audit(recipe, raw, source_lines, source)

    def _upsert_recipe(self, recipe, missing_only=False):
        existing = next(
            (r for r in self.state.recipes.values() if r.external_id == recipe.external_id),
            None,
        )
        if existing:
            if missing_only:
                return None
            recipe.id = existing.id
        self.state.recipes[recipe.id] = recipe
        return "updated" if existing else "imported"

    def import_recipes(self):
        # Reviewed import policy: accept every source record that passes strict
        # identity-profile/alias and exact-quantity validation; there is no count
        # ceiling that can silently discard otherwise valid reviewed records.
        # Network I/O stays outside the write transaction, so failed traversal
        # cannot partially replace recipes.
        with self.import_lock:
            report, accepted = ImportReport(), {}
            for raw in self.source.meals():
                try:
                    normalized = normalize_meal_with_audit(
                        raw, self.catalog, self.store.resolve_alias
                    )
                except ServiceError as exc:
                    report.skipped.append(
                        ImportSkip(
                            external_id=str(raw.get("idMeal") or ""),
                            title=str(raw.get("strMeal") or ""),
                            reason=exc.message,
                        )
                    )
                    continue
                recipe, new_ingredients, aliases, source_lines, source = normalized
                accepted[recipe.external_id] = (
                    recipe,
                    new_ingredients,
                    aliases,
                    source_lines,
                    source,
                    raw,
                )
            with self.store.transaction():
                staged_ingredients = {}
                staged_aliases = {}
                for _, (_, new_ingredients, aliases, _, _, _) in accepted.items():
                    for ingredient in new_ingredients:
                        previous = staged_ingredients.get(ingredient.id)
                        if previous is not None and previous != ingredient:
                            raise invalid(f"Conflicting identity profile for {ingredient.id!r}")
                        staged_ingredients[ingredient.id] = ingredient
                    for alias in aliases:
                        previous = staged_aliases.get(alias["normalized_text"])
                        if (
                            previous is not None
                            and previous["ingredient_id"] != alias["ingredient_id"]
                        ):
                            raise invalid(f"Conflicting imported alias {alias['alias_text']!r}")
                        staged_aliases[alias["normalized_text"]] = alias
                self.store.stage_import_catalog(
                    tuple(staged_ingredients.values()), tuple(staged_aliases.values())
                )
                for recipe, _, _, source_lines, source, raw in accepted.values():
                    result = self._upsert_recipe(recipe)
                    self.store.stage_import_audit(recipe, raw, source_lines, source)
                    if result == "updated":
                        report.updated += 1
                    elif result == "imported":
                        report.imported += 1
                report.total_recipes = len(self.state.recipes)
                return report

    def basket_demands(self):
        return [
            line
            for item in self.state.basket.values()
            for line in self.demands(self.recipe(item.recipe_id), item.servings, item.substitutions)
        ]

    @atomic
    def get_basket(self):
        totals = self.aggregate(self.basket_demands())
        items = []
        for item in self.state.basket.values():
            recipe = self.recipe(item.recipe_id)
            feasible = self.feasible_servings(recipe, item.substitutions)
            items.append(
                BasketItemWithRecipe(
                    **item.model_dump(),
                    recipe=recipe,
                    original_servings=recipe.base_servings,
                    adapted_servings=item.servings,
                    feasible_servings=feasible,
                    limiting_lines=self.limiting_lines(recipe, item.substitutions, feasible),
                )
            )
        return BasketView(
            items=items,
            totals=self.lines([(i, q, None) for i, q in totals.items()]),
        )

    @atomic
    def add_basket(self, data):
        self.recipe(data.recipe_id)
        existing = next(
            (b for b in self.state.basket.values() if b.recipe_id == data.recipe_id), None
        )
        if existing:
            existing.servings = data.servings
            return existing
        item = BasketItem(
            id=self.store.next_id("b"),
            recipe_id=data.recipe_id,
            servings=data.servings,
            substitutions=[],
        )
        self.state.basket[item.id] = item
        return item

    @atomic
    def update_basket(self, item_id, data):
        item = self.find(self.state.basket, item_id, "Basket item")
        servings = data.servings if data.servings is not None else item.servings
        substitutions = data.substitutions if data.substitutions is not None else item.substitutions
        self.validate_new_choices(
            self.recipe(item.recipe_id), servings, substitutions, item.substitutions
        )
        item.servings, item.substitutions = servings, substitutions
        return item

    @atomic
    def remove_basket(self, item_id):
        self.find(self.state.basket, item_id, "Basket item")
        del self.state.basket[item_id]

    @atomic
    def get_shopping(self):
        return list(self.state.shopping.values())

    @atomic
    def generate_shopping(self, data):
        edited = self.state.removed_generated or any(
            (s.origin == "generated" and (s.edited or s.purchased))
            or (data.resetAll and s.origin == "manual")
            for s in self.state.shopping.values()
        )
        if edited and not data.force:
            raise ServiceError(
                409,
                "EDITS_WOULD_BE_LOST",
                "Regenerating will overwrite shopping edits. Confirm with force=true.",
            )
        totals = self.aggregate(self.basket_demands())
        keep = {
            s.id: s
            for s in self.state.shopping.values()
            if s.origin == "manual" and not data.resetAll
        }
        for i, required in totals.items():
            quantity = self.allocation(i, required).missing
            if quantity <= 0:
                continue
            item = ShoppingItem(
                id=self.store.next_id("s"),
                ingredient_id=i,
                label=self.catalog[i].name,
                quantity=rounded(quantity),
                unit=self.catalog[i].canonical_unit,
                origin="generated",
                purchased=False,
                transferred_to_pantry=False,
                edited=False,
            )
            keep[item.id] = item
        self.state.shopping, self.state.removed_generated = keep, False
        return list(keep.values())

    @atomic
    def add_shopping(self, data):
        ingredient_id, unit = data.ingredient_id, data.unit.strip()
        if ingredient_id is not None:
            unit = self.ingredient(ingredient_id).canonical_unit
        else:
            match = next(
                (
                    i
                    for i in self.catalog.values()
                    if i.name.casefold() == data.label.strip().casefold()
                    and i.canonical_unit == unit
                ),
                None,
            )
            ingredient_id = match.id if match else None
        item = ShoppingItem(
            id=self.store.next_id("s"),
            ingredient_id=ingredient_id,
            label=data.label.strip(),
            quantity=positive_rounded(data.quantity),
            unit=unit,
            origin="manual",
            purchased=False,
            transferred_to_pantry=False,
            edited=False,
        )
        self.state.shopping[item.id] = item
        return item

    @atomic
    def update_shopping(self, item_id, data):
        item = self.find(self.state.shopping, item_id, "Shopping item")
        if data.purchased is False and item.transferred_to_pantry:
            raise ServiceError(
                409, "ALREADY_TRANSFERRED", "Cannot clear purchased status after transfer."
            )
        if data.quantity is not None:
            item.quantity, item.edited = positive_rounded(data.quantity), True
        if data.purchased is not None:
            item.purchased = data.purchased
        return item

    @atomic
    def remove_shopping(self, item_id):
        item = self.find(self.state.shopping, item_id, "Shopping item")
        if item.origin == "generated":
            self.state.removed_generated = True
        del self.state.shopping[item_id]

    @atomic
    def transfer(self, item_id, data):
        item = self.find(self.state.shopping, item_id, "Shopping item")
        if item.transferred_to_pantry:
            return item
        if not item.purchased:
            raise ServiceError(409, "NOT_PURCHASED", "Mark this item as purchased first.")
        if not item.ingredient_id:
            raise invalid("Only catalog ingredients can be transferred to the pantry")
        self.merge_pantry(item.ingredient_id, positive_rounded(data.quantity), data.expiry_date)
        item.transferred_to_pantry = True
        return item

    def preview(self, data):
        recipe = self.recipe(data.recipe_id)
        demands = self.demands(recipe, data.servings, data.substitutions)
        lines = self.lines(demands)
        feasible = self.feasible_servings(recipe, data.substitutions)
        return CookPreview(
            recipe_id=data.recipe_id,
            servings=data.servings,
            original_servings=recipe.base_servings,
            adapted_servings=data.servings,
            feasible_servings=feasible,
            limiting_lines=self.limiting_lines(recipe, data.substitutions, feasible),
            lines=lines,
            can_cook=all(line.sufficient for line in lines),
        )

    @atomic
    def preview_cook(self, data):
        return self.preview(data)

    @atomic
    def confirm_cook(self, data):
        preview = self.preview(data)
        if not preview.can_cook:
            raise ServiceError(
                409,
                "INSUFFICIENT_STOCK",
                "Insufficient usable stock. Inventory and history are unchanged.",
            )
        total = self.aggregate(
            self.demands(self.recipe(data.recipe_id), data.servings, data.substitutions)
        )
        allocations = {i: self.allocation(i, required) for i, required in total.items()}
        for result in allocations.values():
            if not result.sufficient:
                raise ServiceError(
                    409,
                    "INSUFFICIENT_STOCK",
                    "Insufficient usable stock. Inventory and history are unchanged.",
                )
        for result in allocations.values():
            for lot_allocation in result.lots:
                lot = self.state.pantry[lot_allocation.lot_id]
                lot.quantity = rounded(decimal(lot.quantity) - lot_allocation.quantity)
                if lot.quantity <= 0:
                    del self.state.pantry[lot.id]
        record = CookingRecord(
            id=self.store.next_id("h"),
            recipe_id=data.recipe_id,
            recipe_title=self.recipe(data.recipe_id).title,
            servings=data.servings,
            original_servings=self.recipe(data.recipe_id).base_servings,
            adapted_servings=data.servings,
            cooked_at=datetime.now(timezone.utc),
            consumed=[Consumption(ingredient_id=i, quantity=q) for i, q in total.items()],
        )
        self.state.history.insert(0, record)
        return record

    @atomic
    def list_history(self):
        records = []
        for record in self.state.history:
            if record.original_servings is None or record.adapted_servings is None:
                recipe = self.recipe(record.recipe_id)
                record.original_servings = recipe.base_servings
                record.adapted_servings = record.servings
            records.append(record)
        return records

    @atomic
    def dashboard(self):
        ranked = self.rank([self.summary(r) for r in self.state.recipes.values()])
        urgent = [r for r in ranked if r.match.expiring_used]
        recent = []
        for record in self.state.history[:5]:
            if record.original_servings is None or record.adapted_servings is None:
                recipe = self.recipe(record.recipe_id)
                record.original_servings = recipe.base_servings
                record.adapted_servings = record.servings
            recent.append(record)
        return Dashboard(
            total_items=len(self.state.pantry),
            expiring_soon=sum(
                0 <= (p.expiry_date - self.today()).days <= self.expiry_days
                for p in self.state.pantry.values()
            ),
            expired=sum(p.expiry_date < self.today() for p in self.state.pantry.values()),
            recommendations=(urgent or ranked)[:4],
            recent_history=recent,
        )
