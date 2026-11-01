import hashlib
import json
import time

import pytest
from argon2 import PasswordHasher
from conftest import register_test_account
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app import auth as auth_module
from app.auth import SESSION_COOKIE, verify_password
from app.main import create_app
from app.store import rate_limits, sessions, settings, users

SECRET = "test auth secret with at least 32 bytes"
PASSWORD = "correct horse battery"


@pytest.fixture
def auth_app(service):
    return create_app(
        service,
        startup_import=False,
        auth_secret=SECRET,
        trusted_origins=("http://localhost:5173",),
    )


def register(client, email="fresh@example.com", password=PASSWORD):
    return register_test_account(client, email=email, password=password)


def restored_csrf(client):
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def csrf_headers(token, origin="http://localhost:5173"):
    return {"X-CSRF-Token": token, "Origin": origin}


def db_rows(service, table):
    with service.store.engine.connect() as connection:
        return connection.execute(select(table)).mappings().all()


def test_registration_hashes_password_and_rotates_cookie(service, auth_app):
    with TestClient(auth_app) as client:
        anonymous = client.get("/api/auth/session")
        preauth_id = client.cookies.get(SESSION_COOKIE)
        response = client.post(
            "/api/auth/register",
            json={"email": "  Fresh@Example.com ", "password": PASSWORD},
            headers=csrf_headers(anonymous.json()["csrf_token"]),
        )
        assert response.status_code == 201
        account = response.json()["user"]
        session_id = client.cookies.get(SESSION_COOKIE)
        assert session_id and session_id != preauth_id
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
        assert "Path=/api" in cookie
        assert "Secure" not in cookie

        user = db_rows(service, users)[0]
        assert user["email"] == "Fresh@Example.com"
        assert user["email_key"] == "fresh@example.com"
        assert user["password_hash"].startswith("$argon2id$v=19$m=65536,t=3,p=2$")
        assert PASSWORD not in user["password_hash"]
        assert PasswordHasher().verify(user["password_hash"], PASSWORD)
        assert not verify_password(user["password_hash"], "incorrect horse battery")

        stored = db_rows(service, sessions)
        assert {row["token_hash"] for row in stored} == {
            hashlib.sha256(preauth_id.encode()).hexdigest(),
            hashlib.sha256(session_id.encode()).hexdigest(),
        }
        assert all(session_id not in row["token_hash"] for row in stored)
        by_hash = {row["token_hash"]: row for row in stored}
        assert by_hash[hashlib.sha256(preauth_id.encode()).hexdigest()]["revoked_at"] is not None
        assert by_hash[hashlib.sha256(session_id.encode()).hexdigest()]["user_id"] == account["id"]
        assert response.json()["csrf_token"] not in json.dumps([dict(row) for row in stored])
        assert client.get("/api/auth/session").json()["user"] == account


def test_duplicate_registration_validation_bounds_and_email_identity(service, auth_app):
    with TestClient(auth_app) as first, TestClient(auth_app) as duplicate:
        created = register(first, "fresh@example.com")
        duplicate_csrf = restored_csrf(duplicate)
        before_cookie = duplicate.cookies.get(SESSION_COOKIE)
        response = duplicate.post(
            "/api/auth/register",
            json={"email": " FRESH@EXAMPLE.COM ", "password": PASSWORD},
            headers=csrf_headers(duplicate_csrf),
        )
        assert response.status_code == 409
        assert duplicate.cookies.get(SESSION_COOKIE) == before_cookie
        assert len(db_rows(service, users)) == 1
        assert created["user"]["id"] == db_rows(service, users)[0]["id"]

    with TestClient(auth_app) as client:
        csrf = restored_csrf(client)
        invalid = [
            {"email": "not-an-email", "password": PASSWORD},
            {"email": "valid@example.com", "password": "short"},
            {"email": "valid@example.com", "password": "x" * 129},
            {"email": "x" * 255, "password": PASSWORD},
            {"email": "valid@example.com"},
        ]
        for body in invalid:
            response = client.post("/api/auth/register", json=body, headers=csrf_headers(csrf))
            assert response.status_code == 422
            assert PASSWORD not in response.text
        assert len(db_rows(service, users)) == 1


def test_login_is_generic_rotates_revokes_and_restores_after_restart(
    service, auth_app, monkeypatch
):
    with TestClient(auth_app) as client:
        registered = register(client, "restart@example.com")
        original_session = client.cookies.get(SESSION_COOKIE)
        original_csrf = registered["csrf_token"]
        pantry_response = client.post(
            "/api/pantry",
            json={
                "ingredient_id": "egg",
                "quantity": 3,
                "unit": "pcs",
                "expiry_date": "2026-11-01",
            },
            headers=csrf_headers(original_csrf),
        )
        assert pantry_response.status_code == 200
        assert client.get("/api/auth/session").json()["authenticated"]

        service.store.close()
        restarted_service = type(service)(seed=False)
        restarted_app = create_app(restarted_service, startup_import=False, auth_secret=SECRET)
        with TestClient(restarted_app) as restarted:
            restarted.cookies.set(
                SESSION_COOKIE,
                original_session,
                domain="testserver.local",
                path="/api",
            )
            restored = restarted.get("/api/auth/session")
            assert restored.status_code == 200
            assert restored.json()["authenticated"] is True
            assert restored.json()["user"]["email"] == "restart@example.com"
            restarted.headers.update(csrf_headers(restored.json()["csrf_token"]))
            assert len(restarted.get("/api/pantry").json()) == 1

            old_csrf = restored.json()["csrf_token"]
            old_session = restarted.cookies.get(SESSION_COOKIE)
            logout = restarted.post("/api/auth/logout", headers=csrf_headers(old_csrf))
            assert logout.status_code == 204
            assert "Max-Age=0" in logout.headers["set-cookie"]

            replay = restarted.get(
                "/api/pantry", headers={"Cookie": f"{SESSION_COOKIE}={old_session}"}
            )
            assert replay.status_code == 401
            assert "Max-Age=0" in replay.headers["set-cookie"]
            assert replay.json()["message"] == "Authentication is required."

            new_csrf = restored_csrf(restarted)
            wrong_password = restarted.post(
                "/api/auth/login",
                json={"email": "restart@example.com", "password": "wrong password"},
                headers=csrf_headers(new_csrf),
            )
            unknown_user = restarted.post(
                "/api/auth/login",
                json={"email": "missing@example.com", "password": "wrong password"},
                headers=csrf_headers(new_csrf),
            )
            assert wrong_password.status_code == unknown_user.status_code == 401
            assert wrong_password.json() == unknown_user.json()

            successful = restarted.post(
                "/api/auth/login",
                json={"email": " RESTART@EXAMPLE.COM ", "password": PASSWORD},
                headers=csrf_headers(new_csrf),
            )
            assert successful.status_code == 200
            assert restarted.cookies.get(SESSION_COOKIE) != old_session
            assert restarted.get("/api/auth/session").json()["authenticated"] is True
        restarted_service.store.close()


def test_csrf_origin_and_anonymous_api_boundary(auth_app):
    with TestClient(auth_app) as client:
        assert client.get("/api/ingredients").status_code == 200
        assert client.get("/api/substitution-rules").status_code == 200
        for path in (
            "/api/pantry",
            "/api/recipes",
            "/api/basket",
            "/api/shopping-list",
            "/api/cooking/history",
            "/api/dashboard",
        ):
            assert client.get(path).status_code == 401
        assert client.post("/api/recipes/import").status_code == 401

        account = register(client)
        valid = account["csrf_token"]
        payload = {
            "ingredient_id": "egg",
            "quantity": 2,
            "unit": "pcs",
            "expiry_date": "2026-11-01",
        }
        no_proof = client.post(
            "/api/pantry",
            json=payload,
            headers={"X-CSRF-Token": "", "Origin": "http://localhost:5173"},
        )
        untrusted = client.post(
            "/api/pantry",
            json=payload,
            headers=csrf_headers(valid, origin="https://attacker.example"),
        )
        assert no_proof.status_code == untrusted.status_code == 403
        assert client.get("/api/pantry").json() == []


def test_rate_limits_are_shared_and_throttled_requests_do_not_authenticate(
    service, auth_app, monkeypatch
):
    monkeypatch.setattr(auth_module, "REGISTER_IP_LIMIT", 2)
    second_service = type(service)(seed=False)
    second_app = create_app(
        second_service,
        startup_import=False,
        auth_secret=SECRET,
        trusted_origins=("http://localhost:5173",),
    )
    with (
        TestClient(auth_app) as first,
        TestClient(second_app) as second,
        TestClient(auth_app) as third,
    ):
        clients = (first, second, third)
        tokens = [restored_csrf(client) for client in clients]
        for index, (client, csrf) in enumerate(zip(clients[:2], tokens[:2], strict=True)):
            response = client.post(
                "/api/auth/register",
                json={"email": f"account{index}@example.com", "password": PASSWORD},
                headers=csrf_headers(csrf),
            )
            assert response.status_code == 201

        prior_sessions = len(db_rows(service, sessions))
        blocked = third.post(
            "/api/auth/register",
            json={"email": "blocked@example.com", "password": PASSWORD},
            headers=csrf_headers(tokens[2]),
        )
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"].isdigit()
        assert blocked.json()["code"] == "RATE_LIMITED"
        assert len(db_rows(service, users)) == 2
        assert len(db_rows(service, sessions)) == prior_sessions
        assert third.cookies.get(SESSION_COOKIE)
    second_service.store.close()

    with service.store.engine.begin() as connection:
        connection.execute(rate_limits.delete())
    with TestClient(auth_app) as client:
        registered = register(client, "limited@example.com")
        csrf = registered["csrf_token"]
        failures = []
        for _ in range(auth_module.LOGIN_ACCOUNT_LIMIT):
            failures.append(
                client.post(
                    "/api/auth/login",
                    json={"email": "limited@example.com", "password": "incorrect password"},
                    headers=csrf_headers(csrf),
                )
            )
        assert all(response.status_code == 401 for response in failures)
        before_session_count = len(db_rows(service, sessions))
        blocked = client.post(
            "/api/auth/login",
            json={"email": "limited@example.com", "password": "incorrect password"},
            headers=csrf_headers(csrf),
        )
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"].isdigit()
        assert len(db_rows(service, sessions)) == before_session_count
        assert client.get("/api/auth/session").json()["authenticated"] is True


def test_two_account_domain_and_id_isolation_with_empty_new_accounts(service, auth_app):
    with TestClient(auth_app) as first, TestClient(auth_app) as second:
        first_account = register(first, "first@example.com")["user"]
        second_account = register(second, "second@example.com")["user"]
        first_csrf = first.headers["X-CSRF-Token"]
        second_csrf = second.headers["X-CSRF-Token"]

        for client in (first, second):
            assert client.get("/api/pantry").json() == []
            assert client.get("/api/basket").json()["items"] == []
            assert client.get("/api/shopping-list").json() == []
            assert client.get("/api/cooking/history").json() == []

        def add_pantry(client, csrf, ingredient, amount, unit):
            return client.post(
                "/api/pantry",
                json={
                    "ingredient_id": ingredient,
                    "quantity": amount,
                    "unit": unit,
                    "expiry_date": "2026-11-01",
                },
                headers=csrf_headers(csrf),
            )

        first_egg = add_pantry(first, first_csrf, "egg", 6, "pcs").json()
        second_egg = add_pantry(second, second_csrf, "egg", 2, "pcs").json()
        assert first.get("/api/pantry").json() == [first_egg]
        assert second.get("/api/pantry").json() == [second_egg]

        first_basket = first.post(
            "/api/basket/items",
            json={"recipe_id": "rec_test1", "servings": 1},
            headers=csrf_headers(first_csrf),
        ).json()
        first_shopping = first.post(
            "/api/shopping-list/items",
            json={"label": "Eggs", "quantity": 6, "unit": "pcs"},
            headers=csrf_headers(first_csrf),
        ).json()
        assert second.get("/api/basket").json()["items"] == []
        assert second.get("/api/shopping-list").json() == []

        protected_attempts = [
            second.put(
                f"/api/pantry/{first_egg['id']}",
                json={
                    "ingredient_id": "egg",
                    "quantity": 90,
                    "unit": "pcs",
                    "expiry_date": "2026-11-01",
                },
                headers=csrf_headers(second_csrf),
            ),
            second.delete(f"/api/pantry/{first_egg['id']}", headers=csrf_headers(second_csrf)),
            second.patch(
                f"/api/basket/items/{first_basket['id']}",
                json={"servings": 2},
                headers=csrf_headers(second_csrf),
            ),
            second.delete(
                f"/api/basket/items/{first_basket['id']}",
                headers=csrf_headers(second_csrf),
            ),
            second.patch(
                f"/api/shopping-list/items/{first_shopping['id']}",
                json={"purchased": True},
                headers=csrf_headers(second_csrf),
            ),
            second.delete(
                f"/api/shopping-list/items/{first_shopping['id']}",
                headers=csrf_headers(second_csrf),
            ),
            second.post(
                f"/api/shopping-list/items/{first_shopping['id']}/transfer-to-pantry",
                json={"quantity": 6, "expiry_date": "2026-11-01"},
                headers=csrf_headers(second_csrf),
            ),
        ]
        assert all(response.status_code == 404 for response in protected_attempts)
        assert first.get("/api/pantry").json() == [first_egg]
        assert first.get("/api/basket").json()["items"][0]["id"] == first_basket["id"]
        assert first.get("/api/shopping-list").json()[0]["purchased"] is False
        assert second.get("/api/pantry").json() == [second_egg]

        for ingredient, quantity, unit in (
            ("pasta", 100, "g"),
            ("milk", 100, "ml"),
            ("butter", 10, "g"),
        ):
            assert add_pantry(first, first_csrf, ingredient, quantity, unit).status_code == 200
        cook = first.post(
            "/api/cooking/confirm",
            json={"recipe_id": "rec_test1", "servings": 1, "substitutions": []},
            headers=csrf_headers(first_csrf),
        )
        assert cook.status_code == 201
        assert len(first.get("/api/cooking/history").json()) == 1
        assert second.get("/api/cooking/history").json() == []
        assert second.get("/api/dashboard").json()["total_items"] == 1

        first_session = first.get("/api/auth/session").json()
        assert first_session["user"]["id"] == first_account["id"]
        assert second.get("/api/auth/session").json()["user"]["id"] == second_account["id"]
        setting_rows = db_rows(service, settings)
        by_owner = {row["owner_id"]: row for row in setting_rows if row["owner_id"]}
        assert set(by_owner) == {first_account["id"], second_account["id"]}
        assert by_owner[first_account["id"]]["pantry_seeded"] is False
        assert by_owner[second_account["id"]]["pantry_seeded"] is False


def test_expired_session_is_rejected_and_cleared(service, auth_app):
    with TestClient(auth_app) as client:
        register(client)
        token = client.cookies.get(SESSION_COOKIE)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with service.store.engine.begin() as connection:
            connection.execute(
                update(sessions)
                .where(sessions.c.token_hash == digest)
                .values(idle_expires_at=int(time.time()) - 1)
            )
        response = client.get("/api/pantry")
        assert response.status_code == 401
        assert "Max-Age=0" in response.headers["set-cookie"]
        assert client.cookies.get(SESSION_COOKIE) is None
        assert client.get("/api/auth/session").json()["authenticated"] is False


def test_password_hash_and_csrf_secrets_are_not_returned_in_errors(service, auth_app):
    with TestClient(auth_app) as client:
        register(client, "secrets@example.com")
        token = client.cookies.get(SESSION_COOKIE)
        csrf = client.headers["X-CSRF-Token"]
        response = client.post(
            "/api/pantry",
            json={"ingredient_id": "not-real", "quantity": 1, "unit": "g", "expiry_date": "bad"},
            headers=csrf_headers(csrf),
        )
        assert response.status_code == 422
        assert token not in response.text
        assert csrf not in response.text
        assert PASSWORD not in response.text
        with service.store.engine.connect() as connection:
            raw_session = connection.execute(
                select(sessions.c.token_hash).where(
                    sessions.c.token_hash == hashlib.sha256(token.encode()).hexdigest()
                )
            ).scalar_one()
            stored_hash = connection.execute(select(users.c.password_hash)).scalar_one()
        assert raw_session != token
        assert csrf not in raw_session
        assert PASSWORD not in stored_hash
