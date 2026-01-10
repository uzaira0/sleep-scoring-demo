"""
FastAPI application entry point.

Run with: uvicorn sleep_scoring_web.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_errors import setup_error_handlers
from fastapi_logging import RequestLoggingMiddleware, get_logger, setup_logging
from fastapi_ratelimit import setup_rate_limiting
from global_auth import SessionAuthMiddleware, create_session_auth_router

from sleep_scoring_web.auth_setup import create_session_storage
from sleep_scoring_web.config import get_settings, settings

# Configure structured logging (JSON in production, text in development)
setup_logging(json_format=settings.environment == "production")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    from sleep_scoring_web.db.session import init_db
    from sleep_scoring_web.services.file_watcher import start_file_watcher, stop_file_watcher

    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database: {'SQLite' if settings.use_sqlite else 'PostgreSQL'}")

    # Initialize database tables
    await init_db()
    logger.info("Database initialized")

    # Start automatic file watcher
    # This will scan existing files AND watch for new ones in real-time
    # Note: scan runs in background to avoid blocking startup
    await start_file_watcher()
    logger.info("File watcher started - monitoring data directory for new files")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await stop_file_watcher()
    logger.info("File watcher stopped")


# Derive root_path from APP_NAME for deployment behind reverse proxy
app_name_env = os.getenv("APP_NAME", "")
root_path = f"/{app_name_env}" if app_name_env else ""

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Web API for sleep scoring and activity data analysis",
    lifespan=lifespan,
    root_path=root_path,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# Install standard error handlers from fastapi-errors
setup_error_handlers(app, debug=settings.debug)
logger.info("Error handlers configured")

# Setup rate limiting (using fastapi-ratelimit)
setup_rate_limiting(app, default_limits=[settings.rate_limit_default])
logger.info("Rate limiting configured", default_limits=[settings.rate_limit_default])

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware - must be before SessionAuthMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Username", "X-Site-Password"],
)

# Create session storage for authentication
session_storage = create_session_storage()

# Add session auth middleware - BLOCKS ALL requests without valid session
# except for allowlisted paths (login, status, health, docs)
app.add_middleware(
    SessionAuthMiddleware,
    get_settings=get_settings,
    session_storage=session_storage,
    allowed_paths=[
        "/api/v1/auth/status",
        "/api/v1/auth/session/login",
        "/api/v1/auth/login",  # Header-based auth for API clients
        "/health",
        "/",
        "/api/v1/docs",
        "/api/v1/redoc",
        "/api/v1/openapi.json",
    ],
)


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


# API info endpoint
@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


# Include routers
from sleep_scoring_web.api import activity, diary, export, files, markers, settings as settings_router

# Session-based auth router - provides login/logout/status endpoints
# Uses the same session_storage as the middleware
session_auth_router = create_session_auth_router(
    get_settings=get_settings,
    session_storage=session_storage,
    prefix="",
    tags=["auth"],
)
app.include_router(session_auth_router, prefix=f"{settings.api_prefix}/auth")

# API routers
app.include_router(files.router, prefix=f"{settings.api_prefix}/files", tags=["files"])
app.include_router(activity.router, prefix=f"{settings.api_prefix}/activity", tags=["activity"])
app.include_router(markers.router, prefix=f"{settings.api_prefix}/markers", tags=["markers"])
app.include_router(export.router, prefix=f"{settings.api_prefix}/export", tags=["export"])
app.include_router(diary.router, prefix=f"{settings.api_prefix}", tags=["diary"])
app.include_router(settings_router.router, prefix=f"{settings.api_prefix}", tags=["settings"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "sleep_scoring_web.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
