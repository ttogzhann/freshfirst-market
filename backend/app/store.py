"""SQLite unit of work: transaction-local domain objects, relational SQLAlchemy storage.

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
    select,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.pool import StaticPool

from . import models
from .catalog import CATALOG, RULES
from .migrations import migrate

metadata = MetaData()


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
    ingredient_ref(nullable=False),
    Column("quantity_canonical", Numeric(14, 2), nullable=False),
    Column("expiry_date", Date, nullable=False),
    CheckConstraint("quantity_canonical >= 0"),
    Index("uq_pantry_owner_ingredient", "owner_id", "ingredient_id", unique=True),
    Index("ix_pantry_items_owner_id", "owner_id"),
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
    def __init__(self, database_url=None, owner_id=None):
        self.owner_id = owner_id
        url = database_url or os.getenv("DATABASE_URL", "sqlite:///./freshfirst.db")
        options = {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)
        if self.engine.dialect.name != "sqlite":
            raise ValueError("FreshFirst v1.0 requires a SQLite DATABASE_URL")
        self.lock, self.local = RLock(), local()

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
                        insert(table)
                        .values(**value.model_dump())
                        .on_conflict_do_nothing(index_elements=["id"])
                    )
            connection.execute(
                insert(settings)
                .values(
                    id="state",
                    seq=0,
                    removed_generated=False,
                    pantry_seeded=False,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )

    def scoped(self, owner_id):
        scoped = object.__new__(SQLiteStore)
        scoped.engine = self.engine
        scoped.lock = self.lock
        scoped.local = self.local
        scoped.owner_id = owner_id
        return scoped

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
                if table is recipes:
                    for index, line in enumerate(row.pop("ingredients")):
                        line_id = f"{item.id}:{index}"
                        result[recipe_ingredients.name][line_id] = dict(
                            id=line_id,
                            recipe_id=item.id,
                            ingredient_id=line["ingredient_id"],
                            quantity_canonical=line["quantity"],
                            unit=CATALOG[line["ingredient_id"]].canonical_unit,
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
