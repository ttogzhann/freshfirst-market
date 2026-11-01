import sqlite3
from pathlib import Path

import pytest
from conftest import register_test_account
from fastapi.testclient import TestClient

from app import migrations
from app.main import create_app
from app.services.fresh import FreshService
from app.store import SQLiteStore


def create_legacy_database(path: Path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE ingredients (
                id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, category VARCHAR NOT NULL,
                canonical_unit VARCHAR NOT NULL
            );
            CREATE TABLE recipes (
                id VARCHAR PRIMARY KEY, external_id VARCHAR NOT NULL UNIQUE,
                title VARCHAR NOT NULL, category VARCHAR NOT NULL, instructions VARCHAR NOT NULL,
                image_url VARCHAR NOT NULL, base_servings INTEGER NOT NULL
            );
            CREATE TABLE recipe_ingredients (
                id VARCHAR PRIMARY KEY, recipe_id VARCHAR NOT NULL REFERENCES recipes(id),
                ingredient_id VARCHAR NOT NULL REFERENCES ingredients(id),
                quantity_canonical NUMERIC(14,2) NOT NULL, unit VARCHAR NOT NULL
            );
            CREATE TABLE substitution_rules (
                id VARCHAR PRIMARY KEY,
                original_ingredient_id VARCHAR NOT NULL REFERENCES ingredients(id),
                substitute_ingredient_id VARCHAR NOT NULL REFERENCES ingredients(id),
                ratio NUMERIC(14,6) NOT NULL, context VARCHAR NOT NULL, note VARCHAR NOT NULL
            );
            CREATE TABLE pantry_items (
                id VARCHAR PRIMARY KEY,
                ingredient_id VARCHAR NOT NULL UNIQUE REFERENCES ingredients(id),
                quantity_canonical NUMERIC(14,2) NOT NULL,
                expiry_date DATE NOT NULL
            );
            CREATE TABLE basket_items (
                id VARCHAR PRIMARY KEY,
                recipe_id VARCHAR NOT NULL UNIQUE REFERENCES recipes(id),
                servings INTEGER NOT NULL, confirmed_substitutions_json JSON NOT NULL
            );
            CREATE TABLE shopping_items (
                id VARCHAR PRIMARY KEY, ingredient_id VARCHAR REFERENCES ingredients(id),
                label VARCHAR NOT NULL, quantity_canonical NUMERIC(14,2) NOT NULL,
                unit VARCHAR NOT NULL, origin VARCHAR NOT NULL, purchased BOOLEAN NOT NULL,
                transferred_to_pantry BOOLEAN NOT NULL, edited BOOLEAN NOT NULL
            );
            CREATE TABLE cooking_history (
                id VARCHAR PRIMARY KEY, recipe_id VARCHAR NOT NULL REFERENCES recipes(id),
                recipe_title VARCHAR NOT NULL, servings INTEGER NOT NULL,
                cooked_at VARCHAR NOT NULL,
                consumption_snapshot_json JSON NOT NULL
            );
            CREATE TABLE store_settings (
                id VARCHAR PRIMARY KEY, seq INTEGER NOT NULL, removed_generated BOOLEAN NOT NULL,
                pantry_seeded BOOLEAN NOT NULL
            );
            INSERT INTO ingredients VALUES ('egg','Eggs','Dairy','pcs');
            INSERT INTO ingredients VALUES ('pasta','Pasta','Pantry','g');
            INSERT INTO recipes VALUES
                ('rec_legacy','legacy-1','Legacy meal','Dinner','Keep this recipe','',1);
            INSERT INTO recipe_ingredients VALUES ('rec_legacy:0','rec_legacy','pasta',100,'g');
            INSERT INTO pantry_items VALUES ('legacy-pantry','egg',4,'2026-11-15');
            INSERT INTO basket_items VALUES
                ('legacy-basket','rec_legacy',2,'[{"rule_id":"legacy-rule"}]');
            INSERT INTO shopping_items VALUES
                ('legacy-shopping','egg','Eggs',3,'pcs','manual',1,1,1);
            INSERT INTO cooking_history VALUES
                ('legacy-history','rec_legacy','Legacy meal',2,'2026-10-01T10:00:00+00:00',
                 '[{"ingredient_id":"pasta","quantity":200}]');
            INSERT INTO store_settings VALUES ('state',91,1,1);
            """
        )


def test_forward_migration_preserves_and_quarantines_all_legacy_state(tmp_path):
    database = tmp_path / "legacy.db"
    create_legacy_database(database)
    store = SQLiteStore(f"sqlite:///{database}")
    expected = {
        "pantry_items": [("legacy-pantry", None, "egg", 4, "2026-11-15")],
        "basket_items": [
            (
                "legacy-basket",
                None,
                "rec_legacy",
                2,
                '[{"rule_id":"legacy-rule"}]',
            )
        ],
        "shopping_items": [("legacy-shopping", None, "egg", "Eggs", 3, "pcs", "manual", 1, 1, 1)],
        "cooking_history": [
            (
                "legacy-history",
                None,
                "rec_legacy",
                "Legacy meal",
                2,
                "2026-10-01T10:00:00+00:00",
                '[{"ingredient_id":"pasta","quantity":200}]',
            )
        ],
        "store_settings": [("state", None, 91, 1, 1)],
    }
    with store.engine.connect() as connection:
        for table, rows in expected.items():
            columns = {
                "pantry_items": "id, owner_id, ingredient_id, quantity_canonical, expiry_date",
                "basket_items": ("id, owner_id, recipe_id, servings, confirmed_substitutions_json"),
                "shopping_items": (
                    "id, owner_id, ingredient_id, label, quantity_canonical, unit, origin, "
                    "purchased, transferred_to_pantry, edited"
                ),
                "cooking_history": (
                    "id, owner_id, recipe_id, recipe_title, servings, cooked_at, "
                    "consumption_snapshot_json"
                ),
                "store_settings": ("id, owner_id, seq, removed_generated, pantry_seeded"),
            }[table]
            assert connection.exec_driver_sql(f"SELECT {columns} FROM {table}").all() == rows
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert (
            connection.exec_driver_sql("SELECT version FROM schema_migrations").scalar_one()
            == migrations.VERSION
        )

    service = FreshService(store=store, seed=False)
    app = create_app(service, startup_import=False, auth_secret="m" * 32)
    with TestClient(app) as client:
        register_test_account(client, "new-owner@example.com")
        assert client.get("/api/pantry").json() == []
        assert client.get("/api/basket").json()["items"] == []
        assert client.get("/api/shopping-list").json() == []
        assert client.get("/api/cooking/history").json() == []
        assert client.get("/api/dashboard").json()["total_items"] == 0

    reopened = SQLiteStore(f"sqlite:///{database}")
    with reopened.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM pantry_items").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM basket_items").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM shopping_items").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM cooking_history").scalar_one() == 1
        assert (
            connection.exec_driver_sql("SELECT COUNT(*) FROM schema_migrations").scalar_one() == 1
        )
    reopened.close()
    store.close()


def test_migration_failure_rolls_back_table_rebuild_and_preserves_rows(tmp_path, monkeypatch):
    database = tmp_path / "rollback.db"
    create_legacy_database(database)
    original = migrations._rebuild_owned_table

    def fail_after_first_rebuild(connection, table):
        original(connection, table)
        if table == "pantry_items":
            raise RuntimeError("Injected migration failure")

    monkeypatch.setattr(migrations, "_rebuild_owned_table", fail_after_first_rebuild)
    with pytest.raises(RuntimeError, match="Injected migration failure"):
        SQLiteStore(f"sqlite:///{database}")

    with sqlite3.connect(database) as connection:
        pantry_columns = {row[1] for row in connection.execute("PRAGMA table_info(pantry_items)")}
        basket_columns = {row[1] for row in connection.execute("PRAGMA table_info(basket_items)")}
        assert "owner_id" not in pantry_columns
        assert "owner_id" not in basket_columns
        assert connection.execute(
            "SELECT id, ingredient_id, quantity_canonical, expiry_date FROM pantry_items"
        ).fetchall() == [("legacy-pantry", "egg", 4, "2026-11-15")]
        assert connection.execute(
            "SELECT id, recipe_id, servings, confirmed_substitutions_json FROM basket_items"
        ).fetchall() == [("legacy-basket", "rec_legacy", 2, '[{"rule_id":"legacy-rule"}]')]
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='schema_migrations'"
            ).fetchone()[0]
            == 0
        )
