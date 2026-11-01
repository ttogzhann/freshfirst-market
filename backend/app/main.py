"""Run with uv run uvicorn app.main:app --reload (one worker)."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from .auth import AuthFailure, AuthService
from .config import expiry_days
from .errors import ServiceError
from .routers import auth, basket, catalog, cooking, pantry, shopping
from .services.fresh import FreshService

logger = logging.getLogger(__name__)
CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"


def create_app(
    service: FreshService | None = None,
    startup_import: bool = True,
    auth_secret: str | bytes | None = None,
    trusted_origins: tuple[str, ...] | str | None = None,
):
    owns_service = service is None
    service = (
        service
        if service is not None
        else FreshService(expiry_days=expiry_days(os.getenv("FRESHFIRST_EXPIRY_DAYS")), seed=False)
    )

    @asynccontextmanager
    async def lifespan(app):
        try:
            if startup_import:
                await run_in_threadpool(service.seed_recipes)
            yield
        finally:
            if owns_service:
                await run_in_threadpool(service.store.close)

    app = FastAPI(title="FreshFirst API", version="1.0.0", lifespan=lifespan)
    auth_service = AuthService(service.store, secret=auth_secret, origins=trusted_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(auth_service.origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Accept", "X-CSRF-Token"],
        allow_credentials=True,
    )
    app.state.service = service
    app.state.auth = auth_service

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return JSONResponse(
            status_code=exc.status,
            content={"status": exc.status, "code": exc.code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        message = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return JSONResponse(
            status_code=422, content={"status": 422, "code": "VALIDATION_ERROR", "message": message}
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and {"code", "message"} <= detail.keys():
            code, message = detail["code"], detail["message"]
        else:
            code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
            message = str(detail)
        response = JSONResponse(
            status_code=exc.status_code,
            content={"status": exc.status_code, "code": code, "message": message},
            headers=exc.headers,
        )
        if getattr(request.state, "clear_auth_cookie", False):
            response.delete_cookie(
                "freshfirst_session",
                path="/api",
                secure=request.url.scheme == "https"
                or os.getenv("FRESHFIRST_ENV", "").casefold() in {"production", "prod"},
                samesite="lax",
            )
        return response

    @app.exception_handler(AuthFailure)
    async def auth_error(request: Request, exc: AuthFailure):
        headers = {"Retry-After": str(max(1, exc.retry_after))} if exc.retry_after else None
        return JSONResponse(
            status_code=exc.status,
            content={
                "status": exc.status,
                "code": exc.code,
                "message": exc.message,
            },
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.exception("Unexpected API error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "status": 500,
                "code": "INTERNAL_ERROR",
                "message": "Unexpected backend failure. "
                "No partial inventory changes were committed.",
            },
        )

    for router in (
        auth.router,
        catalog.router,
        pantry.router,
        basket.router,
        shopping.router,
        cooking.router,
    ):
        app.include_router(router, prefix="/api")

    # Serve the authored 3.0.3 contract, including the shared error envelopes,
    # instead of FastAPI's default 3.1 document with its incompatible 422 body.
    def contract_openapi():
        if app.openapi_schema is None:
            app.openapi_schema = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        return app.openapi_schema

    app.openapi = contract_openapi
    return app


app = create_app()
