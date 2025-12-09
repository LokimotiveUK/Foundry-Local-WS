"""API routes for Mac Assistant."""

from src.api.routes.chat import router as chat_router
from src.api.routes.models import router as models_router
from src.api.routes.settings import router as settings_router
from src.api.routes.rag import router as rag_router
from src.api.routes.export import router as export_router
from src.api.routes.speech import router as speech_router
from src.api.routes.folders import router as folders_router
from src.api.routes.projects import router as projects_router
from src.api.routes.watchers import router as watchers_router

__all__ = [
    "chat_router",
    "models_router",
    "settings_router",
    "rag_router",
    "export_router",
    "speech_router",
    "folders_router",
    "projects_router",
    "watchers_router",
]
