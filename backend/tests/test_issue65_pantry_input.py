from conftest import register_test_account


def pantry_label(client, label, quantity=100, unit="g"):
    return client.post(
        "/api/pantry",
        json={"label": label, "quantity": quantity, "unit": unit, "expiry_date": "2026-11-01"},
    )


def test_authenticated_autocomplete_is_deterministic_and_not_anonymous(client):
    first = client.get("/api/ingredients/autocomplete", params={"q": "mol"})
    second = client.get("/api/ingredients/autocomplete", params={"q": "mol"})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert any(row["ingredient_id"] == "milk" for row in first.json())

    client.post("/api/auth/logout")
    assert client.get("/api/ingredients/autocomplete", params={"q": "mol"}).status_code == 401


def test_autocomplete_is_account_scoped_and_handles_unicode_empty_and_unknown(client):
    private = pantry_label(client, "private pantry note")
    assert private.status_code == 200

    russian_spelling = client.get(
        "/api/ingredients/autocomplete", params={"q": "\u041c\u0401\u0414"}
    )
    russian_folded = client.get("/api/ingredients/autocomplete", params={"q": "\u043c\u0435\u0434"})
    assert russian_spelling.status_code == russian_folded.status_code == 200
    assert [row["ingredient_id"] for row in russian_spelling.json()] == ["honey"]
    assert russian_spelling.json() == russian_folded.json()
    assert (
        client.get("/api/ingredients/autocomplete", params={"q": "unknown pantry food"}).json()
        == []
    )

    second = client.__class__(client.app, raise_server_exceptions=False)
    with second:
        register_test_account(second, "second-autocomplete@example.com")
        assert second.get("/api/pantry").json() == []
        assert (
            second.get("/api/ingredients/autocomplete", params={"q": "private pantry"}).json() == []
        )
        assert second.get("/api/ingredients/autocomplete", params={"q": ""}).status_code == 422

    assert len(client.get("/api/pantry").json()) == 1


def test_ambiguous_autocomplete_returns_sorted_distinct_candidates(client, service):
    with service.store.engine.begin() as connection:
        from app.store import dialect_insert, ingredient_aliases

        for alias_id, ingredient_id in (("issue65-c", "beef"), ("issue65-d", "chicken")):
            connection.execute(
                dialect_insert(ingredient_aliases, service.store.engine)
                .values(
                    id=alias_id,
                    ingredient_id=ingredient_id,
                    locale="en",
                    alias_text="shared autocomplete food",
                    normalized_text="shared autocomplete food",
                    alias_type="reviewed",
                    confidence=1,
                    provenance="issue65-test",
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )

    response = client.get("/api/ingredients/autocomplete", params={"q": "shared autocomplete food"})
    assert response.status_code == 200
    assert [row["ingredient_id"] for row in response.json()] == ["chicken", "beef"]
    assert client.get("/api/pantry").json() == []


def test_exact_multilingual_label_preserves_input_and_canonical_id(client):
    response = pantry_label(client, " МЁД!!! ", unit="ml")
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["ingredient_id"] == "honey"
    assert item["resolution_status"] == "resolved"
    assert item["original_label"] == " МЁД!!! "
    assert item["canonical_dimension"] == "ml"
    assert client.get("/api/pantry").json()[0]["ingredient_id"] == "honey"


def test_autocomplete_confirmation_preserves_label_after_reload(client, service):
    response = client.post(
        "/api/pantry",
        json={
            "ingredient_id": "milk",
            "label": "МОЛОКО",
            "quantity": 100,
            "unit": "ml",
            "expiry_date": "2026-11-01",
        },
    )
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["ingredient_id"] == "milk"
    assert item["original_label"] == "МОЛОКО"
    restored = service.for_owner(client.user_id).list_pantry()[0]
    assert restored.ingredient_id == "milk"
    assert restored.original_label == "МОЛОКО"


def test_suggestion_and_ambiguity_require_explicit_confirmation(client, service):
    suggested = pantry_label(client, "molok", unit="ml")
    assert suggested.status_code == 200
    suggestion = suggested.json()
    assert suggestion["ingredient_id"] is None
    assert suggestion["resolution_status"] == "suggested"
    assert [candidate["id"] for candidate in suggestion["resolution_candidates"]] == ["milk"]
    assert service.stock().get("milk") is None

    confirmed = client.post(
        f"/api/pantry/{suggestion['id']}/resolve", json={"ingredient_id": "milk"}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["ingredient_id"] == "milk"
    assert confirmed.json()["resolution_status"] == "resolved"
    assert confirmed.json()["original_label"] == "molok"

    with service.store.engine.begin() as connection:
        from app.store import dialect_insert, ingredient_aliases

        for alias_id, ingredient_id in (("issue65-a", "beef"), ("issue65-b", "chicken")):
            connection.execute(
                dialect_insert(ingredient_aliases, service.store.engine)
                .values(
                    id=alias_id,
                    ingredient_id=ingredient_id,
                    locale="en",
                    alias_text="shared pantry food",
                    normalized_text="shared pantry food",
                    alias_type="reviewed",
                    confidence=1,
                    provenance="issue65-test",
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
    ambiguous = pantry_label(client, "shared pantry food", quantity=1)
    assert ambiguous.status_code == 200
    ambiguous_item = ambiguous.json()
    assert ambiguous_item["ingredient_id"] is None
    assert ambiguous_item["resolution_status"] == "ambiguous"
    assert {candidate["id"] for candidate in ambiguous_item["resolution_candidates"]} == {
        "beef",
        "chicken",
    }


def test_rejected_or_incompatible_resolution_does_not_mutate_unknown_lot(client, service):
    response = pantry_label(client, "molok", quantity=2, unit="g")
    assert response.status_code == 200
    item = response.json()
    before = item.copy()

    rejected = client.post(f"/api/pantry/{item['id']}/resolve", json={"ingredient_id": "beef"})
    assert rejected.status_code == 422
    unchanged = client.get("/api/pantry").json()[0]
    assert unchanged["ingredient_id"] == before["ingredient_id"] is None
    assert unchanged["resolution_status"] == before["resolution_status"] == "suggested"
    assert unchanged["original_label"] == before["original_label"] == "molok"
    assert service.stock() == {}

    incompatible = client.post(f"/api/pantry/{item['id']}/resolve", json={"ingredient_id": "milk"})
    assert incompatible.status_code == 422
    unchanged = client.get("/api/pantry").json()[0]
    assert unchanged["ingredient_id"] is None
    assert unchanged["resolution_status"] == "suggested"
    assert unchanged["quantity"] == 2
    assert service.stock() == {}


def test_unresolved_input_survives_restart_and_invalid_input_is_atomic(client, service):
    unresolved = pantry_label(client, "dragonfruit", quantity=5)
    assert unresolved.status_code == 200
    item = unresolved.json()
    assert item["resolution_status"] == "unresolved"
    assert item["ingredient_id"] is None
    assert service.stock() == {}

    invalid = pantry_label(client, "another food", quantity=0)
    assert invalid.status_code == 422
    assert len(client.get("/api/pantry").json()) == 1

    restarted = service.for_owner(client.user_id)
    restored = restarted.list_pantry()
    assert len(restored) == 1
    assert restored[0].original_label == "dragonfruit"
    assert restored[0].resolution_status == "unresolved"


def test_resolution_requires_csrf_and_owner_scope(client):
    item = pantry_label(client, "molok").json()
    csrf = client.headers.pop("X-CSRF-Token")
    denied = client.post(f"/api/pantry/{item['id']}/resolve", json={"ingredient_id": "milk"})
    assert denied.status_code == 403
    client.headers["X-CSRF-Token"] = csrf

    other = client.__class__(client.app, raise_server_exceptions=False)
    with other:
        register_test_account(other, "other-issue65@example.com")
        assert (
            other.post(
                f"/api/pantry/{item['id']}/resolve", json={"ingredient_id": "milk"}
            ).status_code
            == 404
        )
