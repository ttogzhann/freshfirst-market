import re
from datetime import date
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_schema_validator import OAS30Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

from app.main import create_app
from app.services.fresh import FreshService

TODAY = date(2026, 10, 20)
CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "openapi.yaml").read_text(encoding="utf8")
)
REGISTRY = Registry().with_resource(
    "urn:freshfirst", Resource.from_contents(CONTRACT, default_specification=DRAFT4)
)


def contract_refs(schema):
    if isinstance(schema, list):
        return [contract_refs(value) for value in schema]
    if isinstance(schema, dict):
        return {
            key: "urn:freshfirst" + value if key == "$ref" else contract_refs(value)
            for key, value in schema.items()
        }
    return schema


def meal(external_id="test1", title="Milk pasta", category="Pasta", ingredients=None):
    """Synthetic upstream payloads for isolated calculations, never production seeds."""
    raw = {
        "idMeal": external_id,
        "strMeal": title,
        "strCategory": category,
        "strInstructions": "Cook the quantified ingredients.",
        "strMealThumb": "https://www.themealdb.com/images/test.jpg",
    }
    for n, (name, amount) in enumerate(
        ingredients or [("Pasta", "100g"), ("Milk", "100ml"), ("Butter", "10g")], 1
    ):
        raw[f"strIngredient{n}"], raw[f"strMeasure{n}"] = name, amount
    return raw


class Source:
    def __init__(self, meals):
        self.payload = meals

    def meals(self):
        return iter(self.payload)


class ContractClient(TestClient):
    """Validate actual HTTP responses against the authored contract, not app.openapi()."""

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self.operations = set()

    def request(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        path = response.request.url.path.removeprefix("/api")
        for template, methods in CONTRACT["paths"].items():
            if (
                re.fullmatch(re.sub(r"\{\w+\}", "[^/]+", template), path)
                and method.lower() in methods
            ):
                operation = methods[method.lower()]
                self.operations.add(operation["operationId"])
                assert str(response.status_code) in operation["responses"], response.text
                schema = operation["responses"][str(response.status_code)]
                if "$ref" in schema:
                    schema = CONTRACT["components"]["responses"][schema["$ref"].split("/")[-1]]
                if response.status_code == 204:
                    assert response.content == b""
                else:
                    OAS30Validator(
                        contract_refs(schema["content"]["application/json"]["schema"]),
                        registry=REGISTRY,
                        format_checker=OAS30Validator.FORMAT_CHECKER,
                    ).validate(response.json())
                break
        return response


@pytest.fixture
def service():
    raw = [
        meal(),
        meal("test2", "Second pasta", ingredients=[("Pasta", "100g"), ("Parmesan", "30g")]),
        meal(
            "eggs",
            "Spinach eggs",
            "Breakfast",
            [("Eggs", "3"), ("Spinach", "50g"), ("Cheddar cheese", "30g"), ("Butter", "10g")],
        ),
    ]
    service = FreshService(source=Source(raw), today=lambda: TODAY, seed=False)
    service.import_recipes()
    return service


@pytest.fixture
def client(service):
    with ContractClient(
        create_app(service, startup_import=False), raise_server_exceptions=False
    ) as client:
        yield client


def pantry(client, ingredient_id, quantity, unit="g", expiry="2026-11-01"):
    response = client.post(
        "/api/pantry",
        json={
            "ingredient_id": ingredient_id,
            "quantity": quantity,
            "unit": unit,
            "expiry_date": expiry,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()
