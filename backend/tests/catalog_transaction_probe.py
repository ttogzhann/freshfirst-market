"""Acceptance probe shared by local SQLite and actual Compose PostgreSQL.

Uses only application/runtime dependencies so the same probe can be executed
inside the production image against an isolated PostgreSQL database.
"""

import json
import os
import subprocess
import sys
from copy import deepcopy

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.auth import AuthService
from app.models import BasketInput, CookRequest, PantryInput, ShoppingInput
from app.services.fresh import FreshService
from app.services.importer import CuratedCatalogSource
from app.store import SQLiteStore, metadata


def snapshot(store):
    with store.engine.connect() as connection:
        return {
            table.name: sorted(
                json.dumps(dict(row), sort_keys=True, default=str)
                for row in connection.execute(select(table)).mappings()
            )
            for table in metadata.sorted_tables
        }


def verify_catalog_transactions(database_url):
    store = SQLiteStore(database_url)
    service = FreshService(store=store, source=CuratedCatalogSource(), seed=False)
    service.seed_recipes()  # Retain all genuine baseline IDs and their audits.
    auth = AuthService(
        store,
        secret="catalog acceptance probe secret at least 32 bytes",
        origins=("http://localhost:5173",),
    )
    _, anonymous = auth.create_anonymous_session()
    _, session = auth.register(
        anonymous,
        "catalog-probe@example.test",
        "catalog-probe@example.test",
        "catalog probe password",
    )
    owner = service.for_owner(session.user_id)
    baseline = next(iter(service.state.recipes.values()))
    for line in baseline.ingredients:
        owner.create_pantry(
            PantryInput(
                ingredient_id=line.ingredient_id,
                quantity=line.quantity,
                unit=service.catalog[line.ingredient_id].canonical_unit,
                expiry_date="2030-12-31",
            )
        )
    owner.confirm_cook(CookRequest(recipe_id=baseline.id, servings=1, substitutions=[]))
    owner.create_pantry(
        PantryInput(ingredient_id="milk", quantity=25, unit="ml", expiry_date="2030-12-31")
    )
    owner.add_basket(BasketInput(recipe_id=baseline.id, servings=2))
    owner.add_shopping(ShoppingInput(label="Preserve manual line", quantity=3, unit="pcs"))
    user_before = deepcopy(owner.state)
    before = snapshot(store)
    write = store._write_import_audit
    writes = 0

    def fail_late(connection, *args):
        nonlocal writes
        writes += 1
        if writes == 79:
            # Actual database constraint failure after recipes and 78 audit writes.
            connection.execute(text("INSERT INTO import_sources (id) VALUES ('incomplete-probe')"))
        return write(connection, *args)

    store._write_import_audit = fail_late
    try:
        service.import_recipes()
    except IntegrityError:
        pass
    else:
        raise AssertionError("Late database failure was not raised")
    finally:
        store._write_import_audit = write
    assert writes == 79
    assert snapshot(store) == before
    assert owner.state == user_before
    first = service.import_recipes()
    assert (first.imported, first.updated, len(first.skipped)) == (80, 0, 0)
    second = service.import_recipes()
    assert (second.imported, second.updated, len(second.skipped)) == (0, 80, 0)
    assert owner.state.pantry == user_before.pantry
    assert owner.state.basket == user_before.basket
    assert owner.state.shopping == user_before.shopping
    assert owner.state.history == user_before.history

    raw = deepcopy(next(CuratedCatalogSource().meals()))
    raw["strMeal"] = "Newer owner-preserved omelet source"
    raw["strMeasure1"] = "5"
    raw["captured_at_utc"] = "2026-11-15T00:00:00+00:00"

    class NewerSource:
        def meals(self):
            return iter([raw])

    service.source = NewerSource()
    service.import_recipes()
    before_restart = snapshot(store)
    service.seed_recipes(include_catalog=True)
    assert snapshot(store) == before_restart
    store.close()
    script = "from app.services.fresh import FreshService; s=FreshService(seed=False); s.seed_recipes(include_catalog=True); s.store.close(); print('restart-ok')"
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "restart-ok"
    restarted = SQLiteStore(database_url)
    assert snapshot(restarted) == before_restart
    restarted.close()
    return {
        "accepted_catalog": 80,
        "catalog_lines": 492,
        "late_failure_rolled_back": True,
        "restart_unchanged": True,
        "baseline_preserved": len(before["recipes"]),
    }
