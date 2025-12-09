"""Storage module for Mac Assistant - SQLite persistence."""

from src.storage.database import Database, get_database, init_database
from src.storage.models import (
    Base,
    ChatSessionModel,
    ChatMessageModel,
    ChatFolderModel,
    ChatTagModel,
    DocumentModel,
    SettingModel,
    ExportModel,
    FolderWatcherModel,
    ProjectModel,
)
from src.storage.chats import ChatRepository, get_chat_repository
from src.storage.folders import FolderRepository, get_folder_repository
from src.storage.documents import DocumentRepository, get_document_repository
from src.storage.settings import SettingsRepository, get_settings_repository
from src.storage.export import ExportService, get_export_service
from src.storage.projects import ProjectRepository, get_project_repository
from src.storage.watchers import FolderWatcherRepository, get_watcher_repository

__all__ = [
    "Database",
    "get_database",
    "init_database",
    "Base",
    "ChatSessionModel",
    "ChatMessageModel",
    "ChatFolderModel",
    "ChatTagModel",
    "DocumentModel",
    "SettingModel",
    "ExportModel",
    "FolderWatcherModel",
    "ProjectModel",
    "ChatRepository",
    "get_chat_repository",
    "FolderRepository",
    "get_folder_repository",
    "DocumentRepository",
    "get_document_repository",
    "SettingsRepository",
    "get_settings_repository",
    "ExportService",
    "get_export_service",
    "ProjectRepository",
    "get_project_repository",
    "FolderWatcherRepository",
    "get_watcher_repository",
]
