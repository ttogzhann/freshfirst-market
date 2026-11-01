"""Forward-only schema migration for account ownership."""

import time

from sqlalchemy import inspect, text

VERSION = 1


def migrate(connection):
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)"
    )
    current = connection.exec_driver_sql(
        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
    ).scalar_one()
    if current >= VERSION:
        return

    for table in ("pantry_items", "basket_items"):
        columns = {column["name"] for column in inspect(connection).get_columns(table)}
        if "owner_id" not in columns and connection.dialect.name == "sqlite":
            _rebuild_owned_table(connection, table)
        elif "owner_id" not in columns:
            connection.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN owner_id VARCHAR "
                "REFERENCES users(id) ON DELETE CASCADE"
            )

    for table in ("shopping_items", "cooking_history", "store_settings"):
        columns = {column["name"] for column in inspect(connection).get_columns(table)}
        if "owner_id" not in columns:
            connection.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN owner_id VARCHAR "
                "REFERENCES users(id) ON DELETE CASCADE"
            )

    for table in ("pantry_items", "basket_items", "shopping_items", "cooking_history"):
        connection.exec_driver_sql(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_owner_id ON {table}(owner_id)"
        )
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pantry_owner_ingredient "
        "ON pantry_items(owner_id, ingredient_id)"
    )
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_basket_owner_recipe "
        "ON basket_items(owner_id, recipe_id)"
    )
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_store_settings_owner ON store_settings(owner_id)"
    )
    connection.execute(
        text(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (:version, :applied_at)",
        ),
        {"version": VERSION, "applied_at": int(time.time())},
    )


def _rebuild_owned_table(connection, table):
    if table == "pantry_items":
        ddl = """
            CREATE TABLE pantry_items_new (
                id VARCHAR NOT NULL PRIMARY KEY,
                owner_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
                ingredient_id VARCHAR NOT NULL REFERENCES ingredients(id),
                quantity_canonical NUMERIC(14, 2) NOT NULL,
                expiry_date DATE NOT NULL,
                CONSTRAINT ck_pantry_items_quantity_canonical CHECK (quantity_canonical >= 0),
                CONSTRAINT uq_pantry_owner_ingredient UNIQUE (owner_id, ingredient_id)
            )
        """
        columns = "id, owner_id, ingredient_id, quantity_canonical, expiry_date"
        values = "id, NULL, ingredient_id, quantity_canonical, expiry_date"
    else:
        ddl = """
            CREATE TABLE basket_items_new (
                id VARCHAR NOT NULL PRIMARY KEY,
                owner_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
                recipe_id VARCHAR NOT NULL REFERENCES recipes(id),
                servings INTEGER NOT NULL,
                confirmed_substitutions_json JSON NOT NULL,
                CONSTRAINT ck_basket_items_servings CHECK (servings BETWEEN 1 AND 8),
                CONSTRAINT uq_basket_owner_recipe UNIQUE (owner_id, recipe_id)
            )
        """
        columns = "id, owner_id, recipe_id, servings, confirmed_substitutions_json"
        values = "id, NULL, recipe_id, servings, confirmed_substitutions_json"

    connection.exec_driver_sql(ddl)
    connection.exec_driver_sql(f"INSERT INTO {table}_new ({columns}) SELECT {values} FROM {table}")
    connection.exec_driver_sql(f"DROP TABLE {table}")
    connection.exec_driver_sql(f"ALTER TABLE {table}_new RENAME TO {table}")
