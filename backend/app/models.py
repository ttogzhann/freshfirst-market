"""Typed transport models matching root openapi.yaml field names and constraints."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from .validation import normalize_email

CanonicalUnit = Literal["g", "ml", "pcs"]
InputUnit = Literal["g", "kg", "ml", "l", "tsp", "tbsp", "pcs"]
Servings = Annotated[int, Field(strict=True, ge=1, le=8)]
Quantity = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=1, pattern=r"\S")]


class Model(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class Ingredient(Model):
    id: str
    name: str
    category: str
    canonical_unit: CanonicalUnit


class PantryItem(Model):
    id: str
    ingredient_id: str
    quantity: Nonnegative
    expiry_date: date


class DatedQuantity(Model):
    quantity: Quantity
    expiry_date: Annotated[date, Field(strict=False)]

    @model_validator(mode="before")
    @classmethod
    def calendar_date(cls, value):
        if isinstance(value, dict) and "expiry_date" in value:
            raw = value["expiry_date"]
            if not isinstance(raw, date) and (
                not isinstance(raw, str) or len(raw) != 10 or raw[4] != "-" or raw[7] != "-"
            ):
                raise ValueError("expiry_date must be a calendar date YYYY-MM-DD")
        return value


class PantryInput(DatedQuantity):
    ingredient_id: Text
    unit: InputUnit


class RecipeIngredient(Model):
    ingredient_id: str
    quantity: Quantity


class Recipe(Model):
    id: str
    external_id: str
    title: str
    category: str
    instructions: str
    image_url: str
    base_servings: Servings
    ingredients: list[RecipeIngredient]


class MatchInfo(Model):
    score: Annotated[int, Field(ge=0, le=100)]
    covered: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(ge=0)]
    missing: list[str]
    expiring_used: list[str]


class RecipeSummary(Recipe):
    match: MatchInfo


class SubstitutionRule(Model):
    id: str
    original_ingredient_id: str
    substitute_ingredient_id: str
    ratio: Quantity
    context: str
    note: str


class ConfirmedSubstitution(Model):
    rule_id: str
    original_ingredient_id: str
    substitute_ingredient_id: str


class DemandLine(Model):
    ingredient_id: str
    name: str
    unit: CanonicalUnit
    required: Nonnegative
    available: Nonnegative
    sufficient: bool
    substituted_from: str | None = None


class SubstitutionSuggestion(Model):
    rule: SubstitutionRule
    original_name: str
    substitute_name: str
    required: Nonnegative
    unit: CanonicalUnit


class RecipeDetail(RecipeSummary):
    servings: Servings
    lines: list[DemandLine]
    suggestions: list[SubstitutionSuggestion]


class BasketItem(Model):
    id: str
    recipe_id: str
    servings: Servings
    substitutions: list[ConfirmedSubstitution]


class BasketItemWithRecipe(BasketItem):
    recipe: Recipe


class BasketView(Model):
    items: list[BasketItemWithRecipe]
    totals: list[DemandLine]


class BasketInput(Model):
    recipe_id: Text
    servings: Servings


class Patch(Model):
    """Optional fields may be omitted, but explicit null is not in the contract."""

    @model_validator(mode="before")
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict) and any(
            v is None for k, v in value.items() if k in cls.model_fields
        ):
            raise ValueError("Patch fields must be omitted rather than null")
        return value


class BasketPatch(Patch):
    servings: Servings | None = None
    substitutions: list[ConfirmedSubstitution] | None = None


class ShoppingItem(Model):
    id: str
    ingredient_id: str | None
    label: str
    quantity: Nonnegative
    unit: str
    origin: Literal["generated", "manual"]
    purchased: bool
    transferred_to_pantry: bool
    edited: bool


class ShoppingInput(Model):
    label: Text
    quantity: Quantity
    unit: Text
    ingredient_id: str | None = None


class ShoppingPatch(Patch):
    quantity: Quantity | None = None
    purchased: StrictBool | None = None


class ShoppingGenerationInput(Model):
    resetAll: StrictBool = False
    force: StrictBool = False


class TransferInput(DatedQuantity):
    pass


class CookRequest(Model):
    recipe_id: Text
    servings: Servings
    substitutions: list[ConfirmedSubstitution]


class CookPreview(Model):
    recipe_id: str
    servings: Servings
    lines: list[DemandLine]
    can_cook: bool


class Consumption(Model):
    ingredient_id: str
    quantity: Nonnegative


class CookingRecord(Model):
    id: str
    recipe_id: str
    recipe_title: str
    servings: Servings
    cooked_at: datetime
    consumed: list[Consumption]


class ImportSkip(Model):
    external_id: str
    title: str
    reason: str


class ImportReport(Model):
    imported: Annotated[int, Field(ge=0)] = 0
    updated: Annotated[int, Field(ge=0)] = 0
    skipped: list[ImportSkip] = Field(default_factory=list)
    total_recipes: Annotated[int, Field(ge=0)] = 0


class Dashboard(Model):
    total_items: Annotated[int, Field(ge=0)]
    expiring_soon: Annotated[int, Field(ge=0)]
    expired: Annotated[int, Field(ge=0)]
    recommendations: list[RecipeSummary]
    recent_history: list[CookingRecord]


class Error(Model):
    status: Annotated[int, Field(ge=400, le=599)]
    code: str
    message: str


class AuthCredentials(Model):
    email: Annotated[str, Field(strict=True, min_length=3, max_length=254)]
    password: Annotated[str, Field(strict=True, min_length=12, max_length=128)]

    @field_validator("email", mode="before")
    @classmethod
    def valid_email(cls, value):
        return normalize_email(value)[0]


class Account(Model):
    id: str
    email: str


class AuthSessionResponse(Model):
    authenticated: StrictBool
    user: Account | None
    csrf_token: Annotated[str, Field(min_length=40, max_length=64)]


class AuthResponse(Model):
    user: Account
    csrf_token: Annotated[str, Field(min_length=40, max_length=64)]
