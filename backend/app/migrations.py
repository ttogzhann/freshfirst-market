"""Forward-only schema migration for account ownership."""

import time

from sqlalchemy import inspect, text

VERSION = 3


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
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS ingredient_aliases ("
        "id VARCHAR PRIMARY KEY, ingredient_id VARCHAR NOT NULL REFERENCES ingredients(id),"
        "locale VARCHAR NOT NULL, alias_text VARCHAR NOT NULL, normalized_text VARCHAR NOT NULL,"
        "alias_type VARCHAR NOT NULL, confidence NUMERIC(4,3) NOT NULL, "
        "provenance VARCHAR NOT NULL)"
    )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_ingredient_aliases_normalized "
        "ON ingredient_aliases(normalized_text, locale)"
    )
    _migrate_pantry_lots(connection, current)
    connection.execute(
        text("INSERT INTO schema_migrations(version, applied_at) VALUES (:version, :applied_at)"),
        {"version": VERSION, "applied_at": int(time.time())},
    )


def _migrate_pantry_lots(connection, current):
    """Add lot metadata without replacing the existing pantry identifiers."""
    if current >= 3:
        return
    if connection.dialect.name == "sqlite":
        _rebuild_pantry_lots_sqlite(connection)
        return

    columns = {column["name"] for column in inspect(connection).get_columns("pantry_items")}
    additions = {
        "quantity_entered": "NUMERIC(14, 2)",
        "original_unit": "VARCHAR",
        "canonical_dimension": "VARCHAR",
        "original_label": "VARCHAR",
        "normalized_label": "VARCHAR",
        "resolution_status": "VARCHAR",
    }
    for name, definition in additions.items():
        if name not in columns:
            connection.exec_driver_sql(f"ALTER TABLE pantry_items ADD COLUMN {name} {definition}")
    connection.exec_driver_sql("ALTER TABLE pantry_items ALTER COLUMN ingredient_id DROP NOT NULL")
    connection.exec_driver_sql(
        "ALTER TABLE pantry_items ALTER COLUMN quantity_canonical DROP NOT NULL"
    )
    connection.exec_driver_sql(
        "UPDATE pantry_items SET quantity_entered = quantity_canonical "
        "WHERE quantity_entered IS NULL"
    )
    connection.exec_driver_sql(
        "UPDATE pantry_items p SET original_unit = i.canonical_unit, "
        "canonical_dimension = i.canonical_unit, original_label = i.name, "
        "normalized_label = lower(i.name), resolution_status = 'resolved' "
        "FROM ingredients i WHERE p.ingredient_id = i.id AND p.resolution_status IS NULL"
    )
    connection.exec_driver_sql(
        "ALTER TABLE pantry_items ALTER COLUMN canonical_dimension SET NOT NULL"
    )
    constraints = {
        item["name"] for item in inspect(connection).get_check_constraints("pantry_items")
    }
    if "ck_pantry_items_resolution_status" not in constraints:
        connection.exec_driver_sql(
            "ALTER TABLE pantry_items ADD CONSTRAINT ck_pantry_items_resolution_status "
            "CHECK (resolution_status IN ('resolved', 'unresolved', 'ambiguous', 'suggested'))"
        )
    connection.exec_driver_sql("DROP INDEX IF EXISTS uq_pantry_owner_ingredient")
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pantry_owner_lot "
        "ON pantry_items(owner_id, ingredient_id, canonical_dimension, expiry_date)"
    )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_pantry_items_resolution "
        "ON pantry_items(owner_id, resolution_status)"
    )


def _rebuild_pantry_lots_sqlite(connection):
    connection.exec_driver_sql(
        """
        CREATE TABLE pantry_items_new (
            id VARCHAR NOT NULL PRIMARY KEY,
            owner_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
            ingredient_id VARCHAR REFERENCES ingredients(id),
            quantity_canonical NUMERIC(14, 2),
            expiry_date DATE NOT NULL,
            quantity_entered NUMERIC(14, 2),
            original_unit VARCHAR,
            canonical_dimension VARCHAR NOT NULL,
            original_label VARCHAR,
            normalized_label VARCHAR,
            resolution_status VARCHAR NOT NULL DEFAULT 'resolved',
            CONSTRAINT ck_pantry_items_quantity_canonical CHECK (
                quantity_canonical IS NULL OR quantity_canonical >= 0
            ),
            CONSTRAINT ck_pantry_items_quantity_entered CHECK (
                quantity_entered IS NULL OR quantity_entered > 0
            ),
            CONSTRAINT ck_pantry_items_resolution_status CHECK (
                resolution_status IN ('resolved', 'unresolved', 'ambiguous', 'suggested')
            )
        )
        """
    )
    columns = {column["name"] for column in inspect(connection).get_columns("pantry_items")}
    entered = (
        "quantity_canonical"
        if "quantity_entered" not in columns
        else "COALESCE(quantity_entered, quantity_canonical)"
    )
    unit = "i.canonical_unit"
    label = "i.name"
    connection.exec_driver_sql(
        "INSERT INTO pantry_items_new "
        "(id, owner_id, ingredient_id, quantity_canonical, expiry_date, quantity_entered, "
        "original_unit, canonical_dimension, original_label, normalized_label, resolution_status) "
        "SELECT p.id, p.owner_id, p.ingredient_id, p.quantity_canonical, p.expiry_date, "
        f"{entered}, {unit}, {unit}, {label}, lower({label}), 'resolved' "
        "FROM pantry_items p JOIN ingredients i ON i.id = p.ingredient_id"
    )
    connection.exec_driver_sql("DROP TABLE pantry_items")
    connection.exec_driver_sql("ALTER TABLE pantry_items_new RENAME TO pantry_items")
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX uq_pantry_owner_lot "
        "ON pantry_items(owner_id, ingredient_id, canonical_dimension, expiry_date)"
    )
    connection.exec_driver_sql("CREATE INDEX ix_pantry_items_owner_id ON pantry_items(owner_id)")
    connection.exec_driver_sql(
        "CREATE INDEX ix_pantry_items_resolution ON pantry_items(owner_id, resolution_status)"
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
