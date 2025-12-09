"""Main FastAPI application for Mac Assistant."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api.routes import chat_router, models_router, settings_router, rag_router, export_router, speech_router, folders_router, projects_router, watchers_router
from src.api.websocket import websocket_router
from src.core.config import Settings, get_settings
from src.core.models import HealthStatus
from src.foundry.manager import FoundryManager, get_foundry_manager, initialize_foundry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[mac-assistant] %(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()
    logger.info("Starting Mac Assistant API...")

    # Initialize database
    try:
        from src.storage.database import init_database
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Initialize Foundry Local
    try:
        manager = initialize_foundry(settings.default_model)
        logger.info(f"Foundry initialized with model: {settings.default_model}")
        logger.info(f"Endpoint: {manager.endpoint}")
    except Exception as e:
        logger.warning(f"Foundry initialization failed: {e}")
        logger.warning("API will start but chat features won't work until Foundry is available")

    # Start folder watcher service
    watcher_service = None
    try:
        from src.services.watcher import get_watcher_service
        watcher_service = get_watcher_service()
        watcher_service.start()
        logger.info("Folder watcher service started")
    except Exception as e:
        logger.warning(f"Folder watcher service failed to start: {e}")

    yield

    # Stop folder watcher service
    if watcher_service:
        try:
            watcher_service.stop()
            logger.info("Folder watcher service stopped")
        except Exception as e:
            logger.error(f"Error stopping watcher service: {e}")

    logger.info("Shutting down Mac Assistant API...")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Mac Desktop AI Assistant",
        description="Local AI assistant with RAG capabilities for macOS",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware - allow local connections
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:*",
            "http://127.0.0.1:*",
            "tauri://localhost",  # For Tauri apps
            "file://*",  # For local HTML files
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(chat_router)
    app.include_router(models_router)
    app.include_router(settings_router)
    app.include_router(rag_router)
    app.include_router(export_router)
    app.include_router(speech_router)
    app.include_router(folders_router)
    app.include_router(projects_router)
    app.include_router(watchers_router)
    app.include_router(websocket_router)

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint with API info."""
        return {
            "name": "Mac Desktop AI Assistant",
            "version": __version__,
            "docs": "/docs",
        }

    # Health check
    @app.get("/health", response_model=HealthStatus)
    async def health_check() -> HealthStatus:
        """Check service health."""
        manager = get_foundry_manager()

        foundry_running = False
        current_model = None

        if manager.is_initialized:
            foundry_running = manager.is_service_running()
            current_model = manager.current_model

        # TODO: Add Qdrant status check when RAG is implemented
        qdrant_status = "not_initialized"

        return HealthStatus(
            status="healthy" if foundry_running else "degraded",
            foundry_running=foundry_running,
            current_model=current_model,
            qdrant_status=qdrant_status,
            version=__version__,
        )

    # Metrics endpoint
    @app.get("/metrics")
    async def get_metrics() -> dict[str, Any]:
        """Get current system metrics."""
        manager = get_foundry_manager()

        metrics = {
            "foundry": {
                "initialized": manager.is_initialized,
                "running": manager.is_service_running() if manager.is_initialized else False,
                "current_model": manager.current_model,
            },
            "api": {
                "version": __version__,
            },
        }

        if manager.is_initialized:
            try:
                loaded = manager.list_loaded_models()
                cached = manager.list_cached_models()
                metrics["models"] = {
                    "loaded_count": len(loaded),
                    "cached_count": len(cached),
                }
            except Exception:
                pass

        return metrics

    return app


# Create default app instance
app = create_app()


def main():
    """Run the API server."""
    import uvicorn

    settings = get_settings()

    logger.info(f"Starting server at http://{settings.api_host}:{settings.api_port}")

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
