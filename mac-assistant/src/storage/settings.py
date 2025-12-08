"""Settings persistence repository."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from src.storage.database import Database, get_database
from src.storage.models import SettingModel

logger = logging.getLogger(__name__)


class SettingsRepository:
    """Repository for application settings persistence."""

    def __init__(self, database: Database | None = None):
        """Initialize repository.

        Args:
            database: Database instance.
        """
        self.db = database or get_database()

    def _detect_type(self, value: Any) -> str:
        """Detect the type of a value.

        Args:
            value: Value to check.

        Returns:
            Type string.
        """
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, (dict, list)):
            return "json"
        else:
            return "string"

    def _serialize_value(self, value: Any, value_type: str) -> str:
        """Serialize a value for storage.

        Args:
            value: Value to serialize.
            value_type: Type of the value.

        Returns:
            Serialized string.
        """
        if value_type == "json":
            return json.dumps(value)
        elif value_type == "bool":
            return "true" if value else "false"
        else:
            return str(value)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value.

        Args:
            key: Setting key.
            value: Setting value.
        """
        value_type = self._detect_type(value)
        serialized = self._serialize_value(value, value_type)

        with self.db.session_scope() as db_session:
            existing = db_session.query(SettingModel).filter_by(key=key).first()

            if existing:
                existing.value = serialized
                existing.value_type = value_type
                existing.updated_at = datetime.utcnow()
            else:
                setting = SettingModel(
                    key=key,
                    value=serialized,
                    value_type=value_type,
                )
                db_session.add(setting)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            Setting value or default.
        """
        with self.db.session_scope() as db_session:
            setting = db_session.query(SettingModel).filter_by(key=key).first()

            if not setting:
                return default

            return setting.get_typed_value()

    def delete(self, key: str) -> bool:
        """Delete a setting.

        Args:
            key: Setting key.

        Returns:
            True if deleted, False if not found.
        """
        with self.db.session_scope() as db_session:
            setting = db_session.query(SettingModel).filter_by(key=key).first()

            if not setting:
                return False

            db_session.delete(setting)
            return True

    def get_all(self) -> dict[str, Any]:
        """Get all settings.

        Returns:
            Dictionary of all settings.
        """
        with self.db.session_scope() as db_session:
            settings = db_session.query(SettingModel).all()

            return {s.key: s.get_typed_value() for s in settings}

    def set_many(self, settings: dict[str, Any]) -> None:
        """Set multiple settings at once.

        Args:
            settings: Dictionary of settings.
        """
        for key, value in settings.items():
            self.set(key, value)

    def clear(self) -> int:
        """Clear all settings.

        Returns:
            Number of settings cleared.
        """
        with self.db.session_scope() as db_session:
            count = db_session.query(SettingModel).delete()
            logger.info(f"Cleared {count} settings")
            return count

    def export_settings(self) -> dict[str, Any]:
        """Export all settings for backup.

        Returns:
            Dictionary with settings and metadata.
        """
        with self.db.session_scope() as db_session:
            settings = db_session.query(SettingModel).all()

            return {
                "exported_at": datetime.utcnow().isoformat(),
                "settings": [
                    {
                        "key": s.key,
                        "value": s.get_typed_value(),
                        "type": s.value_type,
                    }
                    for s in settings
                ],
            }

    def import_settings(self, data: dict[str, Any], overwrite: bool = True) -> int:
        """Import settings from backup.

        Args:
            data: Exported settings data.
            overwrite: Overwrite existing settings.

        Returns:
            Number of settings imported.
        """
        settings_list = data.get("settings", [])
        imported = 0

        for item in settings_list:
            key = item.get("key")
            value = item.get("value")

            if key is None:
                continue

            if not overwrite:
                existing = self.get(key)
                if existing is not None:
                    continue

            self.set(key, value)
            imported += 1

        logger.info(f"Imported {imported} settings")
        return imported


# Global singleton
_settings_repository: SettingsRepository | None = None


def get_settings_repository() -> SettingsRepository:
    """Get the global settings repository instance."""
    global _settings_repository
    if _settings_repository is None:
        _settings_repository = SettingsRepository()
    return _settings_repository
