"""Issue #64 storage and migration invariants."""

import os
from datetime import date

import pytest
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError

from app.migrations import migrate
from app.models import PantryInput
from app.services.fresh import FreshService
from app.store import SQLiteStore, pantry


def test_fresh_sqlite_schema_is_repeat_safe_and_preserves_lot_columns(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    first = SQLiteStore(url)
    with first.engine.connect() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("pantry_items")}
        assert {
            "quantity_entered",
            "original_label",
            "normalized_label",
            "resolution_status",
        } <= columns
        assert (
            connection.exec_driver_sql("SELECT MAX(version) FROM schema_migrations").scalar_one()
            == 3
        )
    first.close()

    second = SQLiteStore(url)
    with second.engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT COUNT(*) FROM schema_migrations").scalar_one() == 1
        )
    second.close()


@pytest.mark.skipif(
    not os.getenv("FRESHFIRST_POSTGRES_TEST_URL"),
    reason="set FRESHFIRST_POSTGRES_TEST_URL to run the PostgreSQL migration hook",
)
def test_postgresql_schema_is_repeat_safe():
    url = os.environ["FRESHFIRST_POSTGRES_TEST_URL"]
    store = SQLiteStore(url)
    with store.engine.connect() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("pantry_items")}
        assert "resolution_status" in columns
        assert (
            connection.exec_driver_sql("SELECT MAX(version) FROM schema_migrations").scalar_one()
            == 3
        )
    store.close()


def test_dated_lots_merge_only_when_the_expiry_matches_and_unresolved_is_excluded(tmp_path):
    store = SQLiteStore(f"sqlite:///{tmp_path / 'lots.db'}")
    service = FreshService(store=store, seed=False, today=lambda: date(2026, 11, 2))

    first = service.create_pantry(
        PantryInput(ingredient_id="pasta", quantity=1, unit="kg", expiry_date="2026-11-10")
    )
    same_lot = service.create_pantry(
        PantryInput(ingredient_id="pasta", quantity=500, unit="g", expiry_date="2026-11-10")
    )
    later_lot = service.create_pantry(
        PantryInput(ingredient_id="pasta", quantity=250, unit="g", expiry_date="2026-11-20")
    )
    unresolved = service.create_pantry(
        PantryInput(label="mystery grain", quantity=2, unit="kg", expiry_date="2026-11-20")
    )

    assert first.id == same_lot.id
    assert same_lot.quantity == 1500
    assert later_lot.id != first.id
    assert unresolved.ingredient_id is None
    assert unresolved.resolution_status == "unresolved"
    assert "mystery grain" not in service.stock()

    restarted = FreshService(
        store=SQLiteStore(str(store.engine.url)), seed=False, today=lambda: date(2026, 11, 2)
    )
    assert len(restarted.list_pantry()) == 3
    assert restarted.list_pantry()[0].quantity_entered is not None
    store.close()
    restarted.store.close()


def test_sqlite_migration_failure_rolls_back_and_can_be_retried(tmp_path):
    url = f"sqlite:///{tmp_path / 'retry.db'}"
    store = SQLiteStore(url)
    with store.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM schema_migrations")
        connection.exec_driver_sql(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (2, 1)"
        )

    def fail(connection, cursor, statement, parameters, context, executemany):
        if "INSERT INTO pantry_items_new" in statement:
            raise RuntimeError("injected migration failure")

    event.listen(store.engine, "before_cursor_execute", fail)
    with pytest.raises(RuntimeError, match="injected migration"):
        with store.engine.begin() as connection:
            migrate(connection)
    event.remove(store.engine, "before_cursor_execute", fail)
    with store.engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT MAX(version) FROM schema_migrations").scalar_one()
            == 2
        )
    with store.engine.begin() as connection:
        migrate(connection)
    with store.engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT MAX(version) FROM schema_migrations").scalar_one()
            == 3
        )
    store.close()


def test_pantry_integrity_constraints_remain_strict(tmp_path):
    store = SQLiteStore(f"sqlite:///{tmp_path / 'constraints.db'}")
    with pytest.raises(IntegrityError):
        with store.engine.begin() as connection:
            connection.execute(
                pantry.insert().values(
                    id="bad",
                    ingredient_id=None,
                    quantity_entered=0,
                    quantity_canonical=0,
                    expiry_date=date(2026, 11, 20),
                    resolution_status="unresolved",
                )
            )
    store.close()
