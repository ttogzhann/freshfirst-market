"""Account credentials, opaque sessions, CSRF proofs and SQLite rate limits."""

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import case, select, update

from .store import dialect_insert, rate_limits, sessions, settings, users

SESSION_COOKIE = "freshfirst_session"
CSRF_HEADER = "X-CSRF-Token"
IDLE_TIMEOUT_SECONDS = 12 * 60 * 60
ABSOLUTE_TIMEOUT_SECONDS = 30 * 24 * 60 * 60
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_IP_LIMIT = 20
LOGIN_ACCOUNT_LIMIT = 10
REGISTER_WINDOW_SECONDS = 60 * 60
REGISTER_IP_LIMIT = 5

PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))

DEFAULT_TRUSTED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


class AuthFailure(Exception):
    def __init__(self, status, code, message, retry_after=None):
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


@dataclass(frozen=True)
class AuthSession:
    token_hash: str
    user_id: str | None
    email: str | None
    created_at: int
    idle_expires_at: int
    absolute_expires_at: int


def trusted_origins(value=None):
    if value is None:
        value = os.getenv("FRESHFIRST_TRUSTED_ORIGINS")
    if value is None:
        supplied = DEFAULT_TRUSTED_ORIGINS
    elif isinstance(value, str):
        supplied = value.split(",")
    else:
        supplied = value
    origins = tuple(origin.strip().rstrip("/") for origin in supplied if origin.strip())
    if not origins or "*" in origins:
        raise ValueError("FRESHFIRST_TRUSTED_ORIGINS must contain explicit origins, not '*'.")
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("FRESHFIRST_TRUSTED_ORIGINS contains an invalid origin.")
    return origins


def hash_password(password):
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash, password):
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
        return False


class AuthService:
    def __init__(self, store, secret=None, origins=None):
        self.store = store
        supplied = secret if secret is not None else os.getenv("FRESHFIRST_AUTH_SECRET")
        if supplied is None:
            raise ValueError(
                "FRESHFIRST_AUTH_SECRET is required and must be shared across backend workers."
            )
        elif isinstance(supplied, str):
            supplied = supplied.encode("utf-8")
        if len(supplied) < 32:
            raise ValueError("FRESHFIRST_AUTH_SECRET must contain at least 32 bytes.")
        self.csrf_key = bytes(supplied)
        self.origins = trusted_origins(origins)

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def csrf_token(self, token):
        digest = hmac.new(
            self.csrf_key, b"freshfirst-csrf:" + token.encode("ascii"), hashlib.sha256
        )
        return base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode("ascii")

    def check_origin(self, origin):
        if origin is not None and origin not in self.origins:
            raise AuthFailure(403, "CSRF_FAILED", "The request could not be verified.")

    def create_anonymous_session(self):
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        idle_expiry = now + IDLE_TIMEOUT_SECONDS
        absolute_expiry = now + ABSOLUTE_TIMEOUT_SECONDS
        digest = self.token_hash(token)
        with self.store.engine.begin() as connection:
            connection.execute(
                sessions.insert().values(
                    token_hash=digest,
                    user_id=None,
                    created_at=now,
                    last_seen_at=now,
                    idle_expires_at=idle_expiry,
                    absolute_expires_at=absolute_expiry,
                    revoked_at=None,
                )
            )
        return token, AuthSession(digest, None, None, now, idle_expiry, absolute_expiry)

    def resolve(self, token):
        if not token or len(token) > 128:
            return None
        digest = self.token_hash(token)
        now = int(time.time())
        with self.store.engine.begin() as connection:
            row = (
                connection.execute(
                    select(sessions, users.c.email)
                    .select_from(sessions.outerjoin(users, sessions.c.user_id == users.c.id))
                    .where(sessions.c.token_hash == digest)
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            if (
                row["revoked_at"] is not None
                or row["idle_expires_at"] <= now
                or row["absolute_expires_at"] <= now
                or (row["user_id"] is not None and row["email"] is None)
            ):
                if row["revoked_at"] is None:
                    connection.execute(
                        update(sessions)
                        .where(sessions.c.token_hash == digest)
                        .values(revoked_at=now)
                    )
                return None
            return AuthSession(
                digest,
                row["user_id"],
                row["email"],
                row["created_at"],
                row["idle_expires_at"],
                row["absolute_expires_at"],
            )

    def touch(self, session):
        now = int(time.time())
        idle_expiry = min(now + IDLE_TIMEOUT_SECONDS, session.absolute_expires_at)
        with self.store.engine.begin() as connection:
            connection.execute(
                update(sessions)
                .where(
                    sessions.c.token_hash == session.token_hash,
                    sessions.c.revoked_at.is_(None),
                    sessions.c.idle_expires_at > now,
                    sessions.c.absolute_expires_at > now,
                )
                .values(last_seen_at=now, idle_expires_at=idle_expiry)
            )

    def revoke(self, session):
        with self.store.engine.begin() as connection:
            connection.execute(
                update(sessions)
                .where(
                    sessions.c.token_hash == session.token_hash,
                    sessions.c.revoked_at.is_(None),
                )
                .values(revoked_at=int(time.time()))
            )

    @staticmethod
    def _bucket_hash(scope, key):
        return hashlib.sha256(f"freshfirst-rate:{scope}:{key}".encode("utf-8")).hexdigest()

    def consume_rate_limits(self, limits, now=None):
        now = int(time.time()) if now is None else int(now)
        retry_after = 0
        with self.store.engine.begin() as connection:
            connection.execute(
                rate_limits.delete().where(rate_limits.c.window_start < now - 24 * 60 * 60)
            )
            for scope, key, limit, window in limits:
                window_start = now - now % window
                bucket = self._bucket_hash(scope, key)
                statement = (
                    dialect_insert(rate_limits, self.store.engine)
                    .values(bucket_hash=bucket, window_start=window_start, attempts=1)
                    .on_conflict_do_update(
                        index_elements=[rate_limits.c.bucket_hash],
                        set_={
                            "window_start": window_start,
                            "attempts": case(
                                (rate_limits.c.window_start != window_start, 1),
                                else_=rate_limits.c.attempts + 1,
                            ),
                        },
                    )
                    .returning(rate_limits.c.attempts)
                )
                attempts = connection.execute(statement).scalar_one()
                if attempts > limit:
                    retry_after = max(retry_after, window_start + window - now)
        if retry_after:
            raise AuthFailure(
                429,
                "RATE_LIMITED",
                "Too many authentication attempts. Try again later.",
                retry_after=retry_after,
            )

    def limit_login(self, client_ip, email_key):
        self.consume_rate_limits(
            [
                ("login-ip", client_ip, LOGIN_IP_LIMIT, LOGIN_WINDOW_SECONDS),
                ("login-account", email_key, LOGIN_ACCOUNT_LIMIT, LOGIN_WINDOW_SECONDS),
            ]
        )

    def limit_registration(self, client_ip):
        self.consume_rate_limits(
            [("register-ip", client_ip, REGISTER_IP_LIMIT, REGISTER_WINDOW_SECONDS)]
        )

    def register(self, old_session, email, email_key, password):
        password_hash = hash_password(password)
        token = secrets.token_urlsafe(32)
        digest = self.token_hash(token)
        now = int(time.time())
        idle_expiry = now + IDLE_TIMEOUT_SECONDS
        absolute_expiry = now + ABSOLUTE_TIMEOUT_SECONDS
        account_id = f"u_{uuid4().hex}"
        with self.store.engine.begin() as connection:
            existing = connection.execute(
                select(users.c.id).where(users.c.email_key == email_key)
            ).first()
            if existing:
                raise AuthFailure(
                    409, "ACCOUNT_EXISTS", "An account with this email already exists."
                )
            connection.execute(
                users.insert().values(
                    id=account_id,
                    email=email,
                    email_key=email_key,
                    password_hash=password_hash,
                    created_at=now,
                )
            )
            connection.execute(
                settings.insert().values(
                    id=f"state:{account_id}",
                    owner_id=account_id,
                    seq=0,
                    removed_generated=False,
                    pantry_seeded=False,
                )
            )
            connection.execute(
                update(sessions)
                .where(
                    sessions.c.token_hash == old_session.token_hash,
                    sessions.c.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            connection.execute(
                sessions.insert().values(
                    token_hash=digest,
                    user_id=account_id,
                    created_at=now,
                    last_seen_at=now,
                    idle_expires_at=idle_expiry,
                    absolute_expires_at=absolute_expiry,
                    revoked_at=None,
                )
            )
        return token, AuthSession(digest, account_id, email, now, idle_expiry, absolute_expiry)

    def login(self, old_session, email, email_key, password):
        with self.store.engine.connect() as connection:
            row = connection.execute(
                select(users.c.id, users.c.email, users.c.password_hash).where(
                    users.c.email_key == email_key
                )
            ).first()
            account = (row.id, row.email, row.password_hash) if row else None
        stored_hash = account[2] if account else _DUMMY_PASSWORD_HASH
        valid = verify_password(stored_hash, password)
        if account is None or not valid:
            raise AuthFailure(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")

        token = secrets.token_urlsafe(32)
        digest = self.token_hash(token)
        now = int(time.time())
        idle_expiry = now + IDLE_TIMEOUT_SECONDS
        absolute_expiry = now + ABSOLUTE_TIMEOUT_SECONDS
        with self.store.engine.begin() as connection:
            connection.execute(
                update(sessions)
                .where(
                    sessions.c.token_hash == old_session.token_hash,
                    sessions.c.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            connection.execute(
                sessions.insert().values(
                    token_hash=digest,
                    user_id=account[0],
                    created_at=now,
                    last_seen_at=now,
                    idle_expires_at=idle_expiry,
                    absolute_expires_at=absolute_expiry,
                    revoked_at=None,
                )
            )
        return token, AuthSession(digest, account[0], account[1], now, idle_expiry, absolute_expiry)

    def account_response(self, session):
        return {"id": session.user_id, "email": session.email}
