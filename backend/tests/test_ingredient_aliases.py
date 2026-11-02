from datetime import date

from app.catalog import ALIASES, CATALOG
from app.ingredient_aliases import normalize_alias
from app.services.fresh import FreshService
from app.store import SQLiteStore, dialect_insert, ingredient_aliases, ingredients


def test_alias_seed_is_additive_normalized_and_restart_safe(tmp_path):
    url = f"sqlite:///{tmp_path / 'aliases.db'}"
    store = SQLiteStore(url)
    with store.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM ingredients").scalar_one() == len(
            CATALOG
        )
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM ingredient_aliases"
        ).scalar_one() >= len(ALIASES)
    assert store.resolve_alias("  МОЛОКО!!! ").ingredient_ids == ("milk",)
    assert store.resolve_alias("moloko").ingredient_ids == ("milk",)
    assert normalize_alias("  Ground—Beef ") == "ground beef"
    store.close()

    restarted = SQLiteStore(url)
    assert restarted.resolve_alias("мёд").ingredient_ids == ("honey",)
    with restarted.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM ingredients").scalar_one() == len(
            CATALOG
        )
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM ingredient_aliases"
        ).scalar_one() >= len(ALIASES)
    restarted.close()


def test_ambiguous_alias_is_not_auto_resolved_and_typo_requires_confirmation(tmp_path):
    store = SQLiteStore(f"sqlite:///{tmp_path / 'ambiguous.db'}")
    with store.engine.begin() as connection:
        for alias_id, ingredient_id in (
            ("test-ambiguous", "beef"),
            ("test-ambiguous-2", "chicken"),
        ):
            connection.execute(
                dialect_insert(ingredient_aliases, store.engine)
                .values(
                    id=alias_id,
                    ingredient_id=ingredient_id,
                    locale="en",
                    alias_text="common test food",
                    normalized_text="common test food",
                    alias_type="test",
                    confidence=1,
                    provenance="test",
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
        connection.execute(
            dialect_insert(ingredient_aliases, store.engine)
            .values(
                id="test-low-confidence",
                ingredient_id="milk",
                locale="en",
                alias_text="milky typo",
                normalized_text="milky typo",
                alias_type="typo",
                confidence=0.5,
                provenance="test",
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
    ambiguous = store.resolve_alias("common test food")
    assert ambiguous.status == "ambiguous"
    assert ambiguous.ingredient_ids == ("beef", "chicken")
    suggestion = store.resolve_alias("molok")
    assert suggestion.status == "suggestion"
    assert suggestion.requires_confirmation is True
    assert suggestion.ingredient_ids == ("milk",)
    assert store.resolve_alias("milky typo").status == "suggestion"
    assert store.resolve_alias("МОЛОКО", locale="RU").ingredient_ids == ("milk",)
    assert store.resolve_alias("not a food").status == "unresolved"
    store.close()


def test_database_catalog_is_authoritative_after_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'catalog.db'}"
    store = SQLiteStore(url)
    with store.engine.begin() as connection:
        connection.execute(
            ingredients.update().where(ingredients.c.id == "milk").values(name="Database Milk")
        )
    store.close()
    restarted = SQLiteStore(url)
    service = FreshService(store=restarted, seed=False, today=lambda: date(2026, 10, 20))
    assert service.ingredient("milk").name == "Database Milk"
    restarted.close()
