"""Focused real-PostgreSQL persistence checks.

Run with FRESHFIRST_POSTGRES_TEST_URL set to a disposable PostgreSQL database.
The test intentionally skips when no local PostgreSQL resource is supplied so
the normal SQLite suite remains the default developer command.
"""

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth import AuthService
from app.models import (
    BasketInput,
    CookRequest,
    PantryInput,
    ShoppingGenerationInput,
    ShoppingInput,
)
from app.services.fresh import FreshService
from app.store import SQLiteStore, pantry

POSTGRES_URL = os.getenv("FRESHFIRST_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="set FRESHFIRST_POSTGRES_TEST_URL to run the real PostgreSQL checks",
)


class Source:
    def meals(self):
        return iter(
            [
                {
                    "idMeal": "pg-focused",
                    "strMeal": "Postgres focused recipe",
                    "strCategory": "Test",
                    "strInstructions": "Use the ingredients.",
                    "strMealThumb": "https://example.test/postgres.jpg",
                    "strIngredient1": "Pasta",
                    "strMeasure1": "100g",
                    "strIngredient2": "Milk",
                    "strMeasure2": "100ml",
                    "strIngredient3": "Butter",
                    "strMeasure3": "10g",
                }
            ]
        )


def test_postgresql_auth_domain_transactions_and_process_restart(tmp_path):
    store = SQLiteStore(POSTGRES_URL)
    service = FreshService(
        store=store, source=Source(), seed=False, today=lambda: date(2026, 10, 20)
    )
    service.import_recipes()
    recipe_id = next(iter(service.state.recipes))

    auth = AuthService(
        store,
        secret="postgres focused test secret with 32 bytes",
        origins=("http://localhost:5173",),
    )
    anonymous_token, anonymous = auth.create_anonymous_session()
    token, session = auth.register(
        anonymous,
        "pg-owner@example.com",
        "pg-owner@example.com",
        "correct horse battery",
    )
    assert token and anonymous_token
    owner = service.for_owner(session.user_id)

    for ingredient_id, quantity, unit in (
        ("pasta", 100, "g"),
        ("milk", 100, "ml"),
        ("butter", 10, "g"),
    ):
        owner.create_pantry(
            PantryInput(
                ingredient_id=ingredient_id,
                quantity=quantity,
                unit=unit,
                expiry_date="2026-11-01",
            )
        )
    owner.add_basket(BasketInput(recipe_id=recipe_id, servings=1))
    owner.generate_shopping(ShoppingGenerationInput())
    owner.add_shopping(ShoppingInput(label="Manual test item", quantity=1, unit="pcs"))
    assert len(owner.state.shopping) == 1
    cooked = owner.confirm_cook(CookRequest(recipe_id=recipe_id, servings=1, substitutions=[]))
    assert cooked.recipe_id == recipe_id
    assert len(owner.list_history()) == 1

    with pytest.raises(IntegrityError):
        with store.engine.begin() as connection:
            connection.execute(
                pantry.insert().values(
                    id="negative-pg-row",
                    owner_id=session.user_id,
                    ingredient_id="pasta",
                    quantity_canonical=-1,
                    expiry_date=date(2026, 11, 1),
                )
            )

    env = {
        **os.environ,
        "DATABASE_URL": POSTGRES_URL,
        "FRESHFIRST_TEST_OWNER": session.user_id,
    }
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.services.fresh import FreshService; "
            "from app.store import SQLiteStore; "
            "import os; "
            "s=FreshService(store=SQLiteStore(os.environ['DATABASE_URL']), seed=False)"
            ".for_owner(os.environ['FRESHFIRST_TEST_OWNER']); "
            "print(len(s.state.pantry), len(s.state.basket), "
            "len(s.state.shopping), len(s.state.history))",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert probe.stdout.strip() == "0 1 1 1"

    reopened = SQLiteStore(POSTGRES_URL)
    reopened_owner = FreshService(store=reopened, seed=False).for_owner(session.user_id)
    assert len(reopened_owner.state.pantry) == 0
    assert len(reopened_owner.state.basket) == 1
    assert len(reopened_owner.state.shopping) == 1
    assert len(reopened_owner.state.history) == 1

    second_auth = AuthService(
        reopened,
        secret="postgres focused test secret with 32 bytes",
        origins=("http://localhost:5173",),
    )
    second_anonymous_token, second_anonymous = second_auth.create_anonymous_session()
    _, second_session = second_auth.register(
        second_anonymous,
        "pg-other@example.com",
        "pg-other@example.com",
        "correct horse battery",
    )
    assert second_anonymous_token
    assert second_session.user_id != session.user_id
    second_owner = FreshService(store=reopened, seed=False).for_owner(second_session.user_id)
    assert not second_owner.state.pantry

    store.close()
    reopened.close()
