"""Inventory and recipe business rules, independent of HTTP routing."""

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from threading import Lock

from ..catalog import CATALOG, RULE_CATEGORIES, RULES
from ..config import expiry_days as validate_expiry_days
from ..errors import ServiceError, invalid, missing
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
    MatchInfo,
    PantryItem,
    RecipeDetail,
    RecipeSummary,
    ShoppingItem,
    SubstitutionSuggestion,
)
from ..store import SQLiteStore
from .importer import PackagedMealSource, TheMealDBSource, normalize_meal
from .quantities import decimal, normalize, positive_rounded, rounded, scale


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
        if ingredient_id not in CATALOG:
            raise invalid("Choose an ingredient from the supported catalog")
        return CATALOG[ingredient_id]

    def recipe(self, recipe_id):
        if recipe_id not in self.state.recipes:
            raise missing("Recipe")
        return self.state.recipes[recipe_id]

    def find(self, collection, item_id, label):
        if item_id not in collection:
            raise missing(label)
        return collection[item_id]

    def stock(self):
        return {
            p.ingredient_id: decimal(p.quantity)
            for p in self.state.pantry.values()
            if p.expiry_date >= self.today()
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
                CATALOG[rule.original_ingredient_id].canonical_unit
                != CATALOG[rule.substitute_ingredient_id].canonical_unit
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
        stock = self.stock()
        aggregate = self.aggregate(demands)
        return [
            DemandLine(
                ingredient_id=i,
                name=CATALOG[i].name,
                unit=CATALOG[i].canonical_unit,
                required=q,
                available=stock.get(i, 0),
                sufficient=stock.get(i, 0) >= aggregate[i],
                substituted_from=original,
            )
            for i, q, original in demands
        ]

    def summary(self, recipe):
        stock = self.stock()
        missing_names, expiring = [], []
        covered = 0
        for line in recipe.ingredients:
            name = CATALOG[line.ingredient_id].name
            available = stock.get(line.ingredient_id, 0)
            if available >= decimal(line.quantity):
                covered += 1
            else:
                missing_names.append(name)
            if available >= decimal(line.quantity) and any(
                p.ingredient_id == line.ingredient_id
                and 0 <= (p.expiry_date - self.today()).days <= self.expiry_days
                for p in self.state.pantry.values()
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
        stock = self.stock()
        for sub in substitutions:
            if (
                sub not in previous
                and stock.get(sub.substitute_ingredient_id, 0) < total[sub.substitute_ingredient_id]
            ):
                raise invalid("The selected substitute has insufficient usable stock")

    def list_ingredients(self):
        return list(CATALOG.values())

    def list_rules(self):
        return list(RULES.values())

    @atomic
    def list_pantry(self):
        return list(self.state.pantry.values())

    def merge_pantry(self, ingredient_id, quantity, expiry_date):
        existing = next(
            (p for p in self.state.pantry.values() if p.ingredient_id == ingredient_id), None
        )
        if existing:
            if existing.expiry_date != expiry_date:
                raise ServiceError(
                    409, "EXPIRY_CONFLICT", "Edit the existing pantry entry: expiry dates differ."
                )
            existing.quantity = rounded(decimal(existing.quantity) + decimal(quantity))
            return existing
        item = PantryItem(
            id=self.store.next_id("p"),
            ingredient_id=ingredient_id,
            quantity=quantity,
            expiry_date=expiry_date,
        )
        self.state.pantry[item.id] = item
        return item

    @atomic
    def create_pantry(self, data):
        ing = self.ingredient(data.ingredient_id)
        quantity = normalize(data.quantity, data.unit, ing.canonical_unit)
        return self.merge_pantry(ing.id, quantity, data.expiry_date)

    @atomic
    def update_pantry(self, item_id, data):
        item = self.find(self.state.pantry, item_id, "Pantry item")
        ing = self.ingredient(data.ingredient_id)
        quantity = normalize(data.quantity, data.unit, ing.canonical_unit)
        if any(p.id != item_id and p.ingredient_id == ing.id for p in self.state.pantry.values()):
            raise ServiceError(
                409, "DUPLICATE_INGREDIENT", "Another pantry entry uses this ingredient."
            )
        item.ingredient_id, item.quantity, item.expiry_date = ing.id, quantity, data.expiry_date
        return item

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
        stock, suggestions = self.stock(), []
        for line in lines:
            if line.sufficient or line.substituted_from:
                continue
            for rule in RULES.values():
                if (
                    rule.original_ingredient_id != line.ingredient_id
                    or recipe.category not in RULE_CATEGORIES[rule.id]
                ):
                    continue
                substitute = CATALOG[rule.substitute_ingredient_id]
                if substitute.canonical_unit != line.unit:
                    continue
                required = positive_rounded(decimal(line.required) * decimal(rule.ratio))
                others = sum(decimal(q) for i, q, _ in demands if i == substitute.id)
                if stock.get(substitute.id, 0) < decimal(required) + others:
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
            lines=lines,
            suggestions=suggestions,
        )

    def seed_recipes(self):
        # Validate the complete package before writing anything. Unlike live import,
        # unsupported baseline records are fatal and existing records are never replaced.
        accepted = [normalize_meal(raw) for raw in PackagedMealSource().meals()]
        with self.store.transaction():
            for recipe in accepted:
                self._upsert_recipe(recipe, missing_only=True)

    def _upsert_recipe(self, recipe, missing_only=False):
        existing = next(
            (r for r in self.state.recipes.values() if r.external_id == recipe.external_id),
            None,
        )
        if existing:
            if missing_only:
                return None
            recipe.id = existing.id
        elif not missing_only and len(self.state.recipes) >= 20:
            return None
        self.state.recipes[recipe.id] = recipe
        return "updated" if existing else "imported"

    def import_recipes(self):
        # Network I/O outside inventory lock; serialize importers and commit only after
        # a successful source traversal. A failed fetch cannot partially replace recipes.
        with self.import_lock:
            report, accepted = ImportReport(), {}
            for raw in self.source.meals():
                try:
                    recipe = normalize_meal(raw)
                except ServiceError as exc:
                    report.skipped.append(
                        ImportSkip(
                            external_id=str(raw.get("idMeal") or ""),
                            title=str(raw.get("strMeal") or ""),
                            reason=exc.message,
                        )
                    )
                    continue
                accepted[recipe.external_id] = recipe
                if len(accepted) >= 20:
                    break
            with self.store.transaction():
                for recipe in accepted.values():
                    result = self._upsert_recipe(recipe)
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
        return BasketView(
            items=[
                BasketItemWithRecipe(**item.model_dump(), recipe=self.recipe(item.recipe_id))
                for item in self.state.basket.values()
            ],
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
        stock = self.stock()
        totals = self.aggregate(self.basket_demands())
        keep = {
            s.id: s
            for s in self.state.shopping.values()
            if s.origin == "manual" and not data.resetAll
        }
        for i, required in totals.items():
            quantity = max(decimal(0), required - stock.get(i, 0))
            if quantity <= 0:
                continue
            item = ShoppingItem(
                id=self.store.next_id("s"),
                ingredient_id=i,
                label=CATALOG[i].name,
                quantity=rounded(quantity),
                unit=CATALOG[i].canonical_unit,
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
                    for i in CATALOG.values()
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
        demands = self.demands(self.recipe(data.recipe_id), data.servings, data.substitutions)
        lines = self.lines(demands)
        return CookPreview(
            recipe_id=data.recipe_id,
            servings=data.servings,
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
        for i, required in total.items():
            pantry = next(
                p
                for p in self.state.pantry.values()
                if p.ingredient_id == i and p.expiry_date >= self.today()
            )
            pantry.quantity = rounded(decimal(pantry.quantity) - required)
            if pantry.quantity <= 0:
                del self.state.pantry[pantry.id]
        record = CookingRecord(
            id=self.store.next_id("h"),
            recipe_id=data.recipe_id,
            recipe_title=self.recipe(data.recipe_id).title,
            servings=data.servings,
            cooked_at=datetime.now(timezone.utc),
            consumed=[Consumption(ingredient_id=i, quantity=q) for i, q in total.items()],
        )
        self.state.history.insert(0, record)
        return record

    @atomic
    def list_history(self):
        return self.state.history

    @atomic
    def dashboard(self):
        ranked = self.rank([self.summary(r) for r in self.state.recipes.values()])
        urgent = [r for r in ranked if r.match.expiring_used]
        return Dashboard(
            total_items=len(self.state.pantry),
            expiring_soon=sum(
                0 <= (p.expiry_date - self.today()).days <= self.expiry_days
                for p in self.state.pantry.values()
            ),
            expired=sum(p.expiry_date < self.today() for p in self.state.pantry.values()),
            recommendations=(urgent or ranked)[:4],
            recent_history=self.state.history[:5],
        )
