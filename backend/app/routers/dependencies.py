import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request, Response, Security
from fastapi.security import APIKeyCookie, APIKeyHeader

from ..auth import CSRF_HEADER, SESSION_COOKIE, AuthService, AuthSession
from ..services.fresh import FreshService

session_cookie = APIKeyCookie(name=SESSION_COOKIE, scheme_name="SessionCookie", auto_error=False)
csrf_header = APIKeyHeader(name=CSRF_HEADER, scheme_name="CsrfToken", auto_error=False)


def get_auth(request: Request) -> AuthService:
    return request.app.state.auth


def get_public_service(request: Request) -> FreshService:
    return request.app.state.service


def get_session(
    request: Request,
    response: Response,
    token: Annotated[str | None, Security(session_cookie)],
    auth: Annotated[AuthService, Depends(get_auth)],
) -> AuthSession:
    session = auth.resolve(token)
    if session is None:
        if token:
            request.state.clear_auth_cookie = True
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication is required."},
        )
    request.state.auth_token = token
    request.state.auth_session = session
    return session


def require_account(
    request: Request,
    response: Response,
    session: Annotated[AuthSession, Depends(get_session)],
) -> AuthSession:
    if session.user_id is None:
        request.state.clear_auth_cookie = True
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication is required."},
        )
    if request.method in ("GET", "HEAD", "OPTIONS"):
        request.app.state.auth.touch(session)
    return session


def require_csrf(
    request: Request,
    session: Annotated[AuthSession, Depends(get_session)],
    proof: Annotated[str | None, Security(csrf_header)],
    auth: Annotated[AuthService, Depends(get_auth)],
) -> None:
    auth.check_origin(request.headers.get("origin"))
    expected = auth.csrf_token(request.state.auth_token)
    if proof is None or not hmac.compare_digest(proof, expected):
        raise HTTPException(
            status_code=403,
            detail={"code": "CSRF_FAILED", "message": "The request could not be verified."},
        )
    auth.touch(session)


def get_service(
    request: Request,
    session: Annotated[AuthSession, Depends(require_account)],
) -> FreshService:
    request.state.auth_session = session
    return request.app.state.service.for_owner(request.state.auth_session.user_id)


AuthenticatedSession = Annotated[AuthSession, Depends(require_account)]
Session = Annotated[AuthSession, Depends(get_session)]
Service = Annotated[FreshService, Depends(get_service)]
PublicService = Annotated[FreshService, Depends(get_public_service)]
Csrf = Annotated[None, Depends(require_csrf)]
ItemId = Annotated[str, Path(min_length=1)]
