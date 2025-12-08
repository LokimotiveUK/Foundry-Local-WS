"""API routes for Mac Assistant."""

from src.api.routes.chat import router as chat_router
from src.api.routes.models import router as models_router
from src.api.routes.settings import router as settings_router
from src.api.routes.rag import router as rag_router
from src.api.routes.export import router as export_router
from src.api.routes.speech import router as speech_router

__all__ = ["chat_router", "models_router", "settings_router", "rag_router", "export_router", "speech_router"]
