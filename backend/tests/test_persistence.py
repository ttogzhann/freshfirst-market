"""File-backed restart, durable rollback and independent-connection inventory tests."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from conftest import Source, meal
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.errors import ServiceError
from app.models import (
    BasketInput,
    BasketPatch,
    CookRequest,
    PantryInput,
    ShoppingGenerationInput,
    ShoppingInput,
    ShoppingPatch,
    TransferInput,
)
from app.services.fresh import FreshService
from app.store import SQLiteStore, ingredients, pantry, recipe_ingredients, recipes, rules, users


def open_service(seed=False):
    return FreshService(source=Source([meal()]), seed=seed, today=lambda: date(2026, 10, 20))


def stock(service, ingredient_id, quantity, unit="g", expiry="2026-11-01"):
    return service.create_pantry(
        PantryInput(
            ingredient_id=ingredient_id,
            quantity=quantity,
            unit=unit,
            expiry_date=expiry,
        )
    )


def cook_request():
    return CookRequest(recipe_id="rec_test1", servings=1, substitutions=[])


def purchase(service):
    item = service.add_shopping(ShoppingInput(label="Eggs", quantity=6, unit="pcs"))
    service.update_shopping(item.id, ShoppingPatch(purchased=True))
    return item


def test_all_entities_survive_a_new_python_process():
    service = open_service()
    service.import_recipes()
    for ingredient_id, quantity, unit in [
        ("pasta", 300, "g"),
        ("milk", 300, "ml"),
        ("butter", 30, "g"),
        ("cream", 400, "ml"),
    ]:
        stock(service, ingredient_id, quantity, unit)
    stock(service, "spinach", 20, expiry="2026-10-19")
    record = service.confirm_cook(cook_request())
    basket_item = service.add_basket(BasketInput(recipe_id="rec_test1", servings=3))
    # Use the actual reviewed milk -> cream rule, never guessed conversions.
    rule = next(
        r
        for r in service.list_rules()
        if r.original_ingredient_id == "milk" and r.substitute_ingredient_id == "cream"
    )
    service.update_basket(
        basket_item.id,
        BasketPatch(
            substitutions=[
                {
                    "rule_id": rule.id,
                    "original_ingredient_id": "milk",
                    "substitute_ingredient_id": "cream",
                }
            ]
        ),
    )
    generated = service.generate_shopping(ShoppingGenerationInput())
    service.update_shopping(generated[0].id, ShoppingPatch(quantity=123))
    service.remove_shopping(generated[-1].id)
    item = purchase(service)
    transfer = TransferInput(quantity=4, expiry_date="2026-11-01")
    service.transfer(item.id, transfer)
    expected = {
        "pantry": [p.model_dump(mode="json") for p in service.list_pantry()],
        "basket": service.get_basket().model_dump(mode="json"),
        "shopping": [s.model_dump(mode="json") for s in service.get_shopping()],
        "history": [record.model_dump(mode="json")],
    }
    service.store.close()
    script = """
import json
from datetime import date
from app.services.fresh import FreshService
s = FreshService(seed=False, today=lambda: date(2026, 10, 20))
print(json.dumps({
    "pantry": [p.model_dump(mode="json") for p in s.list_pantry()],
    "basket": s.get_basket().model_dump(mode="json"),
    "shopping": [i.model_dump(mode="json") for i in s.get_shopping()],
    "history": [h.model_dump(mode="json") for h in s.list_history()],
    "removed_generated": s.state.removed_generated,
    "recipe_count": len(s.list_recipes()),
}))
s.store.close()
"""
    result = json.loads(subprocess.check_output([sys.executable, "-c", script], text=True))
    assert result.pop("removed_generated") is True
    assert result.pop("recipe_count") == 1
    assert result == expected
    restarted = open_service()
    restarted.transfer(item.id, transfer)
    assert [p.model_dump(mode="json") for p in restarted.list_pantry()] == expected["pantry"]
    assert restarted.get_recipe("rec_test1").match.covered == 3
    assert "spinach" not in restarted.stock()
    with pytest.raises(ServiceError, match="Regenerating"):
        restarted.generate_shopping(ShoppingGenerationInput())


def test_seed_is_unique_and_deleted_pantry_stays_deleted():
    service = open_service(seed=True)
    for item in service.list_pantry():
        service.delete_pantry(item.id)
    service.import_recipes()
    service.store.close()
    restarted = open_service(seed=True)
    report = restarted.import_recipes()
    assert restarted.list_pantry() == []
    assert report.imported == 0 and report.updated == 1
    with restarted.store.engine.connect() as connection:
        for table, count in [(ingredients, 77), (rules, 10), (recipes, 1), (recipe_ingredients, 3)]:
            assert connection.scalar(select(func.count()).select_from(table)) == count


def test_import_updates_by_external_id_after_restart_without_losing_references():
    service = open_service()
    service.import_recipes()
    item = service.add_basket(BasketInput(recipe_id="rec_test1", servings=2))
    service.store.close()
    restarted = open_service()
    restarted.source = Source([meal(title="Updated source", ingredients=[("Pasta", "200g")])])
    report = restarted.import_recipes()
    assert (report.imported, report.updated, report.total_recipes) == (0, 1, 1)
    assert restarted.get_basket().items[0].id == item.id
    assert restarted.get_basket().items[0].recipe.title == "Updated source"
    assert restarted.get_basket().totals[0].required == 400
    assert restarted.import_recipes().total_recipes == 1


@pytest.mark.parametrize("operation", ["cook", "transfer"])
def test_database_write_failure_rolls_back_durable_inventory(operation):
    service = open_service()
    service.import_recipes()
    if operation == "cook":
        for ingredient_id, quantity, unit in [
            ("pasta", 100, "g"),
            ("milk", 100, "ml"),
            ("butter", 10, "g"),
        ]:
            stock(service, ingredient_id, quantity, unit)

        def action():
            return service.confirm_cook(cook_request())

        fail_sql = "INSERT INTO cooking_history"
    else:
        item = purchase(service)

        def action():
            return service.transfer(
                item.id,
                TransferInput(
                    quantity=6,
                    expiry_date="2026-11-01",
                ),
            )

        fail_sql = "UPDATE shopping_items"
    before = service.state
    observed = []

    def fail(connection, cursor, statement, parameters, context, executemany):
        observed.append(statement)
        if statement.startswith(fail_sql):
            raise RuntimeError("Injected SQL write failure")

    event.listen(service.store.engine, "before_cursor_execute", fail)
    with pytest.raises(RuntimeError, match="Injected SQL"):
        action()
    event.remove(service.store.engine, "before_cursor_execute", fail)
    assert any(
        "pantry_items" in sql and sql.startswith(("DELETE", "INSERT", "UPDATE")) for sql in observed
    )
    service.store.close()
    assert open_service().state == before


@pytest.mark.parametrize("operation", ["cook", "transfer"])
def test_independent_connections_serialize_inventory(operation):
    first = open_service()
    first.import_recipes()
    item = purchase(first)
    for ingredient_id, quantity, unit in [
        ("pasta", 100, "g"),
        ("milk", 100, "ml"),
        ("butter", 10, "g"),
    ]:
        stock(first, ingredient_id, quantity, unit)
    services = [first] + [open_service() for _ in range(5)]

    def act(service):
        try:
            if operation == "cook":
                service.confirm_cook(cook_request())
            else:
                service.transfer(item.id, TransferInput(quantity=6, expiry_date="2026-11-01"))
            return "success"
        except ServiceError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(act, services))
    if operation == "cook":
        assert results.count("success") == 1
        assert results.count("INSUFFICIENT_STOCK") == 5
        assert len(first.list_history()) == 1
        assert first.list_pantry() == []
    else:
        assert results == ["success"] * 6
        assert next(p.quantity for p in first.list_pantry() if p.ingredient_id == "egg") == 6
    for service in services:
        service.store.close()


def test_database_constraints_enforce_inventory_invariants():
    store = SQLiteStore(os.environ["DATABASE_URL"])
    with pytest.raises(IntegrityError), store.engine.begin() as connection:
        connection.execute(
            pantry.insert().values(
                id="bad",
                ingredient_id="egg",
                quantity_canonical=-1,
                expiry_date=date(2026, 11, 1),
            )
        )
    with store.engine.begin() as connection:
        connection.execute(
            users.insert().values(
                id="u_constraint",
                email="constraint@example.com",
                email_key="constraint@example.com",
                password_hash="unused",
                created_at=1,
            )
        )
    with pytest.raises(IntegrityError), store.engine.begin() as connection:
        for item_id in ["first", "duplicate"]:
            connection.execute(
                pantry.insert().values(
                    id=item_id,
                    owner_id="u_constraint",
                    ingredient_id="egg",
                    quantity_canonical=1,
                    expiry_date=date(2026, 11, 1),
                )
            )
    assert store.state.pantry == {}
    store.close()
