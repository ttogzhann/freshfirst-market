"""Dialect-neutral unit of work: transaction-local domain objects, relational SQLAlchemy storage.

BEGIN IMMEDIATE reserves the writer before reading stock, even across processes.
Only changed rows are written; any failure rolls back the whole unit of work.
"""

import os
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock, local
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    event,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.pool import StaticPool

from . import models
from .catalog import ALIASES, CATALOG, RULES, RUSSIAN_ALIASES, TRANSLITERATION_ALIASES
from .ingredient_aliases import normalization_variants, normalize_alias, resolve_rows
from .migrations import migrate

metadata = MetaData()


def dialect_insert(table, engine):
    """Return an INSERT with the conflict methods supported by the active database."""
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as postgresql_insert

        return postgresql_insert(table)
    return sqlite_insert(table)


def identity():
    return Column("id", String, primary_key=True)


def ingredient_ref(name="ingredient_id", **kwargs):
    return Column(name, String, ForeignKey("ingredients.id"), **kwargs)


ingredients = Table(
    "ingredients",
    metadata,
    identity(),
    Column("name", String, nullable=False),
    Column("category", String, nullable=False),
    Column("canonical_unit", String, nullable=False),
    CheckConstraint("canonical_unit IN ('g', 'ml', 'pcs')"),
)
pantry = Table(
    "pantry_items",
    metadata,
    identity(),
    Column("owner_id", String, ForeignKey("users.id", ondelete="CASCADE")),
    ingredient_ref(nullable=True),
    Column("quantity_canonical", Numeric(14, 2), nullable=True),
    Column("expiry_date", Date, nullable=False),
    Column("quantity_entered", Numeric(14, 2), nullable=True),
    Column("original_unit", String, nullable=True),
    Column("canonical_dimension", String, nullable=False),
    Column("original_label", String, nullable=True),
    Column("normalized_label", String, nullable=True),
    Column("resolution_status", String, nullable=False, server_default="resolved"),
    CheckConstraint("quantity_canonical IS NULL OR quantity_canonical >= 0"),
    CheckConstraint("quantity_entered IS NULL OR quantity_entered >= 0"),
    CheckConstraint("resolution_status IN ('resolved', 'unresolved', 'ambiguous', 'suggested')"),
    Index(
        "uq_pantry_owner_lot",
        "owner_id",
        "ingredient_id",
        "canonical_dimension",
        "expiry_date",
        "resolution_status",
        unique=True,
    ),
    Index("ix_pantry_items_owner_id", "owner_id"),
    Index("ix_pantry_items_resolution", "owner_id", "resolution_status"),
)
recipes = Table(
    "recipes",
    metadata,
    identity(),
    Column("external_id", String, nullable=False, unique=True),
    *[
        Column(name, String, nullable=False)
        for name in ("title", "category", "instructions", "image_url")
    ],
    Column("base_servings", Integer, nullable=False),
    CheckConstraint("base_servings BETWEEN 1 AND 8"),
)
recipe_ingredients = Table(
    "recipe_ingredients",
    metadata,
    identity(),
    Column("recipe_id", String, ForeignKey("recipes.id"), nullable=False),
    ingredient_ref(nullable=False),
    Column("quantity_canonical", Numeric(14, 2), nullable=False),
    Column("unit", String, nullable=False),
    CheckConstraint("quantity_canonical > 0"),
)
rules = Table(
    "substitution_rules",
    metadata,
    identity(),
    ingredient_ref("original_ingredient_id", nullable=False),
    ingredient_ref("substitute_ingredient_id", nullable=False),
    Column("ratio", Numeric(14, 6), nullable=False),
    Column("context", String, nullable=False),
    Column("note", String, nullable=False),
    CheckConstraint("ratio > 0"),
)
basket = Table(
    "basket_items",
    metadata,
    identity(),
    Column("owner_id", String, ForeignKey("users.id", ondelete="CASCADE")),
    Column("recipe_id", String, ForeignKey("recipes.id"), nullable=False),
    Column("servings", Integer, nullable=False),
    Column("confirmed_substitutions_json", JSON, nullable=False),
    CheckConstraint("servings BETWEEN 1 AND 8"),
    Index("uq_basket_owner_recipe", "owner_id", "recipe_id", unique=True),
    Index("ix_basket_items_owner_id", "owner_id"),
)
shopping = Table(
    "shopping_items",
    metadata,
    identity(),
    Column("owner_id", String, ForeignKey("users.id", ondelete="CASCADE")),
    ingredient_ref(nullable=True),
    Column("label", String, nullable=False),
    Column("quantity_canonical", Numeric(14, 2), nullable=False),
    Column("unit", String, nullable=False),
    Column("origin", String, nullable=False),
    Column("purchased", Boolean, nullable=False),
    Column("transferred_to_pantry", Boolean, nullable=False),
    Column("edited", Boolean, nullable=False),
    CheckConstraint("quantity_canonical >= 0"),
    CheckConstraint("origin IN ('generated', 'manual')"),
    CheckConstraint("NOT transferred_to_pantry OR purchased"),
    Index("ix_shopping_items_owner_id", "owner_id"),
)
history = Table(
    "cooking_history",
    metadata,
    identity(),
    Column("owner_id", String, ForeignKey("users.id", ondelete="CASCADE")),
    Column("recipe_id", String, ForeignKey("recipes.id"), nullable=False),
    Column("recipe_title", String, nullable=False),
    Column("servings", Integer, nullable=False),
    Column("cooked_at", String, nullable=False),
    Column("consumption_snapshot_json", JSON, nullable=False),
    CheckConstraint("servings BETWEEN 1 AND 8"),
    Index("ix_cooking_history_owner_id", "owner_id"),
)
settings = Table(
    "store_settings",
    metadata,
    identity(),
    Column("owner_id", String, ForeignKey("users.id", ondelete="CASCADE")),
    Column("seq", Integer, nullable=False),
    Column("removed_generated", Boolean, nullable=False),
    Column("pantry_seeded", Boolean, nullable=False),
    Index("uq_store_settings_owner", "owner_id", unique=True),
)
users = Table(
    "users",
    metadata,
    identity(),
    Column("email", String, nullable=False),
    Column("email_key", String, nullable=False, unique=True),
    Column("password_hash", String, nullable=False),
    Column("created_at", Integer, nullable=False),
)
sessions = Table(
    "auth_sessions",
    metadata,
    Column("token_hash", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE")),
    Column("created_at", Integer, nullable=False),
    Column("last_seen_at", Integer, nullable=False),
    Column("idle_expires_at", Integer, nullable=False),
    Column("absolute_expires_at", Integer, nullable=False),
    Column("revoked_at", Integer),
    Index("ix_auth_sessions_user_id", "user_id"),
)
rate_limits = Table(
    "auth_rate_limits",
    metadata,
    Column("bucket_hash", String, primary_key=True),
    Column("window_start", Integer, nullable=False),
    Column("attempts", Integer, nullable=False),
)
ingredient_aliases = Table(
    "ingredient_aliases",
    metadata,
    identity(),
    Column("ingredient_id", String, ForeignKey("ingredients.id"), nullable=False),
    Column("locale", String, nullable=False),
    Column("alias_text", String, nullable=False),
    Column("normalized_text", String, nullable=False),
    Column("alias_type", String, nullable=False),
    Column("confidence", Numeric(4, 3), nullable=False),
    Column("provenance", String, nullable=False),
    Index("ix_ingredient_aliases_normalized", "normalized_text", "locale"),
)


@dataclass
class State:
    pantry: dict[str, models.PantryItem] = field(default_factory=dict)
    recipes: dict[str, models.Recipe] = field(default_factory=dict)
    basket: dict[str, models.BasketItem] = field(default_factory=dict)
    shopping: dict[str, models.ShoppingItem] = field(default_factory=dict)
    history: list[models.CookingRecord] = field(default_factory=list)
    removed_generated: bool = False
    pantry_seeded: bool = False
    seq: int = 0


class SQLiteStore:
    """SQLAlchemy store supporting the default SQLite and configured PostgreSQL dialects."""

    def __init__(self, database_url=None, owner_id=None):
        self.owner_id = owner_id
        url = database_url or os.getenv("DATABASE_URL", "sqlite:///./freshfirst.db")
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgres://")
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
        options = {}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if url in ("sqlite://", "sqlite:///:memory:"):
            options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)
        if self.engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ValueError("FreshFirst supports only SQLite and PostgreSQL DATABASE_URL values")
        self.lock, self.local = RLock(), local()

        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine, "connect")
            def configure(connection, record):
                connection.isolation_level = None
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=30000")

            @event.listens_for(self.engine, "begin")
            def begin(connection):
                connection.exec_driver_sql("BEGIN IMMEDIATE")

        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            migrate(connection)
        with self.engine.begin() as connection:
            for table, values in ((ingredients, CATALOG.values()), (rules, RULES.values())):
                for value in values:
                    connection.execute(
                        dialect_insert(table, self.engine)
                        .values(**value.model_dump())
                        .on_conflict_do_nothing(index_elements=["id"])
                    )
            canonical_names = {value.name.casefold() for value in CATALOG.values()}
            aliases = [
                (
                    key,
                    value,
                    "en",
                    key,
                    "canonical" if key in canonical_names else "alias",
                    1,
                    "catalog.py",
                )
                for key, value in ALIASES.items()
            ]
            aliases += [
                (key, value, "ru", key, "alias", 1, "reviewed-russian")
                for key, value in RUSSIAN_ALIASES.items()
            ]
            aliases += [
                (key, value, "ru-Latn", key, "transliteration", 1, "reviewed-transliteration")
                for key, value in TRANSLITERATION_ALIASES.items()
            ]
            for index, (
                alias,
                ingredient_id,
                locale,
                text_value,
                alias_type,
                confidence,
                provenance,
            ) in enumerate(aliases):
                row = {
                    "id": f"alias_{index:04d}",
                    "ingredient_id": ingredient_id,
                    "locale": locale,
                    "alias_text": alias,
                    "normalized_text": normalize_alias(text_value),
                    "alias_type": alias_type,
                    "confidence": confidence,
                    "provenance": provenance,
                }
                connection.execute(
                    dialect_insert(ingredient_aliases, self.engine)
                    .values(**row)
                    .on_conflict_do_nothing(index_elements=["id"])
                )
            connection.execute(
                dialect_insert(settings, self.engine)
                .values(
                    id="state",
                    seq=0,
                    removed_generated=False,
                    pantry_seeded=False,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
        self._catalog_cache = self._read_catalog()

    def scoped(self, owner_id):
        scoped = object.__new__(SQLiteStore)
        scoped.engine = self.engine
        scoped.lock = self.lock
        scoped.local = self.local
        scoped.owner_id = owner_id
        scoped._catalog_cache = self._catalog_cache
        return scoped

    def _read_catalog(self):
        with self.engine.connect() as connection:
            return {
                row["id"]: models.Ingredient(**row)
                for row in connection.execute(select(ingredients)).mappings()
            }

    @property
    def catalog(self):
        return self._catalog_cache

    def resolve_alias(self, value, locale=None):
        variants = normalization_variants(value)
        with self.engine.connect() as connection:
            query = select(ingredient_aliases).where(
                ingredient_aliases.c.normalized_text.in_(variants)
            )
            if locale:
                query = query.where(
                    or_(
                        func.lower(ingredient_aliases.c.locale) == locale.casefold(),
                        func.lower(ingredient_aliases.c.locale) == "en",
                    )
                )
            exact_rows = list(connection.execute(query).mappings())
            if exact_rows:
                return resolve_rows(exact_rows, value)
            query = select(ingredient_aliases)
            if locale:
                query = query.where(
                    or_(
                        func.lower(ingredient_aliases.c.locale) == locale.casefold(),
                        func.lower(ingredient_aliases.c.locale) == "en",
                    )
                )
            return resolve_rows(connection.execute(query).mappings(), value)

    @property
    def state(self):
        if getattr(self.local, "state", None) is not None:
            return self.local.state
        with self.lock, self.engine.begin() as connection:
            return self._load(connection)

    def _load(self, connection):
        def rows(table):
            query = select(table)
            if "owner_id" in table.c:
                owner = (
                    table.c.owner_id.is_(None)
                    if self.owner_id is None
                    else (table.c.owner_id == self.owner_id)
                )
                query = query.where(owner)
            return [dict(row) for row in connection.execute(query).mappings()]

        config_rows = rows(settings)
        config = (
            config_rows[0]
            if config_rows
            else {
                "seq": 0,
                "removed_generated": False,
                "pantry_seeded": False,
            }
        )
        state = State(**{key: config[key] for key in ("seq", "removed_generated", "pantry_seeded")})
        for row in rows(pantry):
            row["quantity"] = row.pop("quantity_canonical")
            row.setdefault("quantity_entered", row["quantity"])
            if row.get("resolution_status") == "resolved" and row.get("ingredient_id"):
                ingredient = self.catalog[row["ingredient_id"]]
                row["canonical_dimension"] = (
                    row.get("canonical_dimension") or ingredient.canonical_unit
                )
                row["original_unit"] = row.get("original_unit") or ingredient.canonical_unit
                row["original_label"] = row.get("original_label") or ingredient.name
                row["normalized_label"] = row.get("normalized_label") or ingredient.name.casefold()
            state.pantry[row["id"]] = models.PantryItem(**row)
        lines = rows(recipe_ingredients)
        for row in rows(recipes):
            row["ingredients"] = [
                {"ingredient_id": line["ingredient_id"], "quantity": line["quantity_canonical"]}
                for line in lines
                if line["recipe_id"] == row["id"]
            ]
            state.recipes[row["id"]] = models.Recipe(**row)
        for row in rows(basket):
            row["substitutions"] = row.pop("confirmed_substitutions_json")
            state.basket[row["id"]] = models.BasketItem(**row)
        for row in rows(shopping):
            row["quantity"] = row.pop("quantity_canonical")
            state.shopping[row["id"]] = models.ShoppingItem(**row)
        for row in rows(history):
            row["consumed"] = row.pop("consumption_snapshot_json")
            state.history.append(models.CookingRecord(**row))
        state.history.sort(key=lambda record: record.cooked_at, reverse=True)
        return state

    def _rows(self, state):
        result = {table.name: {} for table in metadata.tables.values()}
        for name, table in (
            ("pantry", pantry),
            ("recipes", recipes),
            ("basket", basket),
            ("shopping", shopping),
            ("history", history),
        ):
            collection = getattr(state, name)
            for item in collection.values() if isinstance(collection, dict) else collection:
                row = item.model_dump(mode="json")
                if "owner_id" in table.c:
                    row["owner_id"] = self.owner_id
                if table is pantry:
                    row["expiry_date"] = item.expiry_date
                if table in (pantry, shopping):
                    row["quantity_canonical"] = row.pop("quantity")
                if table is pantry:
                    row["quantity_entered"] = row.get("quantity_entered") or row.get(
                        "quantity_canonical"
                    )
                    if row.get("resolution_status") == "resolved" and row.get("ingredient_id"):
                        ingredient = self.catalog[row["ingredient_id"]]
                        row["canonical_dimension"] = (
                            row.get("canonical_dimension") or ingredient.canonical_unit
                        )
                        row["original_unit"] = row.get("original_unit") or ingredient.canonical_unit
                        row["original_label"] = row.get("original_label") or ingredient.name
                        row["normalized_label"] = (
                            row.get("normalized_label") or ingredient.name.casefold()
                        )
                if table is recipes:
                    for index, line in enumerate(row.pop("ingredients")):
                        line_id = f"{item.id}:{index}"
                        result[recipe_ingredients.name][line_id] = dict(
                            id=line_id,
                            recipe_id=item.id,
                            ingredient_id=line["ingredient_id"],
                            quantity_canonical=line["quantity"],
                            unit=self.catalog[line["ingredient_id"]].canonical_unit,
                        )
                if table is basket:
                    row["confirmed_substitutions_json"] = row.pop("substitutions")
                if table is history:
                    row["consumption_snapshot_json"] = row.pop("consumed")
                result[table.name][item.id] = row
        result[settings.name][self.owner_id or "state"] = dict(
            id=f"state:{self.owner_id}" if self.owner_id else "state",
            owner_id=self.owner_id,
            seq=state.seq,
            removed_generated=state.removed_generated,
            pantry_seeded=state.pantry_seeded,
        )
        return result

    def _save(self, connection, previous, current):
        before, after = self._rows(previous), self._rows(current)
        tables = [recipes, recipe_ingredients, pantry, basket, shopping, history, settings]
        for table in reversed(tables):
            removed = before[table.name].keys() - after[table.name].keys()
            if removed:
                connection.execute(table.delete().where(table.c.id.in_(removed)))
        for table in tables:
            for key, row in after[table.name].items():
                old = before[table.name].get(key)
                if old is None:
                    connection.execute(table.insert().values(**row))
                elif row != old:
                    connection.execute(table.update().where(table.c.id == row["id"]).values(**row))

    @contextmanager
    def transaction(self):
        with self.lock:
            if getattr(self.local, "state", None) is not None:
                raise RuntimeError("Nested store transactions are not supported")
            try:
                with self.engine.begin() as connection:
                    if self.engine.dialect.name == "postgresql":
                        state_id = f"state:{self.owner_id}" if self.owner_id else "state"
                        connection.execute(
                            select(settings.c.id).where(settings.c.id == state_id).with_for_update()
                        )
                    self.local.state = self._load(connection)
                    previous = deepcopy(self.local.state)
                    yield self.local.state
                    self._save(connection, previous, self.local.state)
            finally:
                self.local.state = None

    def close(self):
        self.engine.dispose()

    def next_id(self, prefix):
        if getattr(self.local, "state", None) is None:
            raise RuntimeError("IDs must be allocated inside a transaction")
        self.local.state.seq += 1
        return f"{prefix}_{uuid4().hex}"
