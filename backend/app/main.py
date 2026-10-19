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

from .errors import ServiceError
from .routers import basket, catalog, cooking, pantry, shopping
from .services.fresh import FreshService

logger = logging.getLogger(__name__)
CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"


def create_app(service: FreshService | None = None, startup_import: bool = True):
    owns_service = service is None
    service = (
        service
        if service is not None
        else FreshService(expiry_days=int(os.getenv("FRESHFIRST_EXPIRY_DAYS", "3")))
    )

    @asynccontextmanager
    async def lifespan(app):
        if startup_import:
            try:
                report = await run_in_threadpool(service.import_recipes)
                logger.info("Startup import: %s", report.model_dump())
                if report.total_recipes < 15:
                    logger.warning(
                        "Only %s supported recipes found; target is 15-20. "
                        "Unsupported quantities were not guessed.",
                        report.total_recipes,
                    )
            except ServiceError as exc:
                logger.warning(
                    "Startup import failed: %s. Retry POST /api/recipes/import.", exc.message
                )
        try:
            yield
        finally:
            if owns_service:
                await run_in_threadpool(service.store.close)

    app = FastAPI(title="FreshFirst API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Accept"],
    )
    app.state.service = service

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
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": exc.status_code,
                "code": "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
                "message": str(exc.detail),
            },
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

    for router in (catalog.router, pantry.router, basket.router, shopping.router, cooking.router):
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
