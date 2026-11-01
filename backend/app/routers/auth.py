import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth import (
    ABSOLUTE_TIMEOUT_SECONDS,
    SESSION_COOKIE,
    AuthFailure,
    AuthService,
    AuthSession,
)
from ..models import Account, AuthCredentials, AuthResponse, AuthSessionResponse
from ..validation import normalize_email
from .dependencies import (
    AuthenticatedSession,
    Session,
    get_auth,
    require_csrf,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_ip(request):
    return request.client.host if request.client is not None else "unknown"


def _cookie_secure(request):
    return request.url.scheme == "https" or os.getenv("FRESHFIRST_ENV", "").casefold() in {
        "production",
        "prod",
    }


def _set_cookie(response, request, token):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=ABSOLUTE_TIMEOUT_SECONDS,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        path="/api",
    )


def _clear_cookie(response, request):
    response.delete_cookie(
        SESSION_COOKIE,
        secure=_cookie_secure(request),
        samesite="lax",
        path="/api",
    )


def _user(session: AuthSession):
    return Account(id=session.user_id, email=session.email)


def _retry_header(exc):
    return {"Retry-After": str(max(1, exc.retry_after))} if exc.retry_after else None


@router.get("/session", response_model=AuthSessionResponse, operation_id="restoreSession")
def restore_session(
    request: Request,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth)],
):
    response.headers["Cache-Control"] = "no-store"
    token = request.cookies.get(SESSION_COOKIE)
    session = auth.resolve(token)
    if session is None:
        token, session = auth.create_anonymous_session()
        _set_cookie(response, request, token)
        response.headers["Cache-Control"] = "no-store"
    else:
        auth.touch(session)
    return AuthSessionResponse(
        authenticated=session.user_id is not None,
        user=_user(session) if session.user_id is not None else None,
        csrf_token=auth.csrf_token(token),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    operation_id="registerAccount",
)
def register(
    request: Request,
    response: Response,
    credentials: AuthCredentials,
    session: Session,
    csrf: Annotated[None, Depends(require_csrf)],
    auth: Annotated[AuthService, Depends(get_auth)],
):
    if session.user_id is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_AUTHENTICATED", "message": "Log out before registering."},
        )
    email, email_key = normalize_email(credentials.email)
    try:
        auth.limit_registration(_client_ip(request))
        token, new_session = auth.register(session, email, email_key, credentials.password)
    except AuthFailure as exc:
        raise HTTPException(
            status_code=exc.status,
            detail={"code": exc.code, "message": exc.message},
            headers=_retry_header(exc),
        ) from None
    _set_cookie(response, request, token)
    response.headers["Cache-Control"] = "no-store"
    return AuthResponse(user=_user(new_session), csrf_token=auth.csrf_token(token))


@router.post("/login", response_model=AuthResponse, operation_id="loginAccount")
def login(
    request: Request,
    response: Response,
    credentials: AuthCredentials,
    session: Session,
    csrf: Annotated[None, Depends(require_csrf)],
    auth: Annotated[AuthService, Depends(get_auth)],
):
    email, email_key = normalize_email(credentials.email)
    try:
        auth.limit_login(_client_ip(request), email_key)
        token, new_session = auth.login(session, email, email_key, credentials.password)
    except AuthFailure as exc:
        raise HTTPException(
            status_code=exc.status,
            detail={"code": exc.code, "message": exc.message},
            headers=_retry_header(exc),
        ) from None
    _set_cookie(response, request, token)
    return AuthResponse(user=_user(new_session), csrf_token=auth.csrf_token(token))


@router.post("/logout", status_code=204, operation_id="logoutAccount")
def logout(
    request: Request,
    response: Response,
    session: AuthenticatedSession,
    csrf: Annotated[None, Depends(require_csrf)],
    auth: Annotated[AuthService, Depends(get_auth)],
):
    auth.revoke(session)
    _clear_cookie(response, request)
    response.status_code = 204
    response.headers["Cache-Control"] = "no-store"
    return response
