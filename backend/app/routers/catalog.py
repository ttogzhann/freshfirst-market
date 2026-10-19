import json
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import TypeAdapter, ValidationError

from ..errors import invalid
from ..models import (
    ConfirmedSubstitution,
    Dashboard,
    ImportReport,
    Ingredient,
    RecipeDetail,
    RecipeSummary,
    SubstitutionRule,
)
from .dependencies import ItemId, Service

router = APIRouter()


@router.get(
    "/ingredients",
    response_model=list[Ingredient],
    operation_id="listIngredients",
    tags=["Catalog"],
)
def ingredients(service: Service):
    return service.list_ingredients()


@router.get(
    "/substitution-rules",
    response_model=list[SubstitutionRule],
    operation_id="listSubstitutionRules",
    tags=["Catalog"],
)
def rules(service: Service):
    return service.list_rules()


@router.get(
    "/recipes", response_model=list[RecipeSummary], operation_id="listRecipes", tags=["Recipes"]
)
def recipes(
    service: Service,
    query: str | None = None,
    category: str | None = None,
    sort: Literal["match", "title"] = "match",
):
    return service.list_recipes(query, category, sort)


@router.post(
    "/recipes/import", response_model=ImportReport, operation_id="importRecipes", tags=["Recipes"]
)
def import_recipes(service: Service):
    return service.import_recipes()


@router.get(
    "/recipes/{id}",
    response_model=RecipeDetail,
    response_model_exclude_none=True,
    operation_id="getRecipe",
    tags=["Recipes"],
)
def detail(
    service: Service,
    id: ItemId,
    servings: Annotated[int | None, Query(ge=1, le=8)] = None,
    substitutions: str = "[]",
):
    try:
        choices = TypeAdapter(list[ConfirmedSubstitution]).validate_python(
            json.loads(substitutions)
        )
    except (ValueError, ValidationError):
        raise invalid(
            "substitutions must be a JSON array of confirmed substitution objects"
        ) from None
    return service.get_recipe(id, servings, choices)


@router.get("/dashboard", response_model=Dashboard, operation_id="getDashboard", tags=["Dashboard"])
def dashboard(service: Service):
    return service.dashboard()
