"""
FastAPI application entry point.

Run with: uvicorn sleep_scoring_web.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sleep_scoring_web.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    from sleep_scoring_web.db.session import init_db
    from sleep_scoring_web.services.file_watcher import start_file_watcher, stop_file_watcher

    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")
    print(f"Database: {'SQLite' if settings.use_sqlite else 'PostgreSQL'}")

    # Initialize database tables
    await init_db()
    print("Database initialized")

    # Start automatic file watcher
    # This will scan existing files AND watch for new ones in real-time
    # Note: scan runs in background to avoid blocking startup
    await start_file_watcher()
    print("File watcher started - monitoring data directory for new files")

    yield

    # Shutdown
    print("Shutting down...")
    await stop_file_watcher()
    print("File watcher stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Web API for sleep scoring and activity data analysis",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
from sleep_scoring_web.api import activity, auth, diary, export, files, markers, settings as settings_router

app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
app.include_router(files.router, prefix=f"{settings.api_v1_prefix}/files", tags=["files"])
app.include_router(activity.router, prefix=f"{settings.api_v1_prefix}/activity", tags=["activity"])
app.include_router(markers.router, prefix=f"{settings.api_v1_prefix}/markers", tags=["markers"])
app.include_router(export.router, prefix=f"{settings.api_v1_prefix}/export", tags=["export"])
app.include_router(diary.router, prefix=f"{settings.api_v1_prefix}", tags=["diary"])
app.include_router(settings_router.router, prefix=f"{settings.api_v1_prefix}", tags=["settings"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "sleep_scoring_web.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
