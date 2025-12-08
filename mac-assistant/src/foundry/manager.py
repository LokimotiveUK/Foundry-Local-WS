"""Foundry Local manager wrapper with enhanced features."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import TYPE_CHECKING

from openai import OpenAI

from src.core.config import Settings, get_settings
from src.core.exceptions import (
    FoundryNotInstalledError,
    FoundryServiceError,
    ModelNotFoundError,
    ModelNotLoadedError,
)
from src.core.models import ModelInfo

if TYPE_CHECKING:
    from foundry_local import FoundryLocalManager as FoundrySDKManager
    from foundry_local.models import FoundryModelInfo

logger = logging.getLogger(__name__)


class FoundryManager:
    """Enhanced Foundry Local manager with metrics and convenience methods."""

    def __init__(self, settings: Settings | None = None):
        """Initialize the Foundry manager.

        Args:
            settings: Application settings. Uses defaults if not provided.
        """
        self.settings = settings or get_settings()
        self._sdk_manager: FoundrySDKManager | None = None
        self._openai_client: OpenAI | None = None
        self._current_model: str | None = None
        self._is_initialized = False

    def _ensure_foundry_installed(self) -> None:
        """Check that Foundry Local CLI is available."""
        try:
            result = subprocess.run(
                ["which", "foundry"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise FoundryNotInstalledError()
        except FileNotFoundError:
            raise FoundryNotInstalledError()
        except subprocess.TimeoutExpired:
            raise FoundryServiceError("Timeout checking for Foundry installation")

    def initialize(self, model_alias: str | None = None) -> None:
        """Initialize the Foundry SDK and optionally load a model.

        Args:
            model_alias: Model to load on startup. Uses default if not provided.
        """
        self._ensure_foundry_installed()

        # Import SDK here to allow graceful failure if not installed
        try:
            from foundry_local import FoundryLocalManager as FoundrySDKManager
        except ImportError:
            raise FoundryServiceError(
                "foundry-local SDK not installed. "
                "Install from: sdk/python/ in this repository"
            )

        model = model_alias or self.settings.default_model

        logger.info(f"Initializing Foundry Local with model: {model}")

        try:
            self._sdk_manager = FoundrySDKManager(
                alias_or_model_id=model,
                bootstrap=True,
            )
            self._current_model = model
            self._is_initialized = True

            # Create OpenAI client
            self._openai_client = OpenAI(
                base_url=self._sdk_manager.endpoint,
                api_key=self._sdk_manager.api_key,
            )

            logger.info(f"Foundry Local initialized at {self._sdk_manager.endpoint}")

        except Exception as e:
            raise FoundryServiceError(f"Failed to initialize Foundry: {e}")

    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._is_initialized

    @property
    def sdk(self) -> "FoundrySDKManager":
        """Get the underlying SDK manager."""
        if not self._sdk_manager:
            raise FoundryServiceError("Foundry not initialized. Call initialize() first.")
        return self._sdk_manager

    @property
    def client(self) -> OpenAI:
        """Get the OpenAI client for chat completions."""
        if not self._openai_client:
            raise FoundryServiceError("OpenAI client not initialized. Call initialize() first.")
        return self._openai_client

    @property
    def endpoint(self) -> str:
        """Get the Foundry service endpoint."""
        return self.sdk.endpoint

    @property
    def current_model(self) -> str | None:
        """Get the currently loaded model alias."""
        return self._current_model

    @property
    def current_model_id(self) -> str | None:
        """Get the currently loaded model's full ID."""
        if not self._current_model:
            return None
        info = self.sdk.get_model_info(self._current_model)
        return info.id if info else None

    def is_service_running(self) -> bool:
        """Check if Foundry service is running."""
        if not self._sdk_manager:
            try:
                from foundry_local import FoundryLocalManager
                temp = FoundryLocalManager(bootstrap=False)
                return temp.is_service_running()
            except Exception:
                return False
        return self._sdk_manager.is_service_running()

    def list_catalog_models(self) -> list[ModelInfo]:
        """List all available models in the catalog."""
        catalog = self.sdk.list_catalog_models()
        cached = {m.id for m in self.sdk.list_cached_models()}
        loaded = {m.id for m in self.sdk.list_loaded_models()}

        return [
            self._to_model_info(m, is_cached=m.id in cached, is_loaded=m.id in loaded)
            for m in catalog
        ]

    def list_cached_models(self) -> list[ModelInfo]:
        """List downloaded models."""
        cached = self.sdk.list_cached_models()
        loaded = {m.id for m in self.sdk.list_loaded_models()}

        return [
            self._to_model_info(m, is_cached=True, is_loaded=m.id in loaded)
            for m in cached
        ]

    def list_loaded_models(self) -> list[ModelInfo]:
        """List currently loaded models."""
        loaded = self.sdk.list_loaded_models()
        return [self._to_model_info(m, is_cached=True, is_loaded=True) for m in loaded]

    def get_model_info(self, alias_or_id: str) -> ModelInfo | None:
        """Get information about a specific model."""
        info = self.sdk.get_model_info(alias_or_id)
        if not info:
            return None

        cached = {m.id for m in self.sdk.list_cached_models()}
        loaded = {m.id for m in self.sdk.list_loaded_models()}

        return self._to_model_info(
            info,
            is_cached=info.id in cached,
            is_loaded=info.id in loaded,
        )

    def _to_model_info(
        self,
        sdk_info: "FoundryModelInfo",
        is_cached: bool = False,
        is_loaded: bool = False,
    ) -> ModelInfo:
        """Convert SDK model info to our ModelInfo."""
        return ModelInfo(
            id=sdk_info.id,
            alias=sdk_info.alias,
            version=sdk_info.version,
            device_type=sdk_info.device_type.value if sdk_info.device_type else "unknown",
            execution_provider=sdk_info.execution_provider.value if sdk_info.execution_provider else "unknown",
            model_size=sdk_info.model_size,
            supports_tool_calling=sdk_info.supports_tool_calling,
            is_loaded=is_loaded,
            is_current=sdk_info.alias == self._current_model or sdk_info.id == self._current_model,
        )

    def download_model(self, alias_or_id: str, force: bool = False) -> ModelInfo:
        """Download a model to local cache.

        Args:
            alias_or_id: Model alias or ID to download.
            force: Force re-download if already cached.

        Returns:
            ModelInfo for the downloaded model.
        """
        logger.info(f"Downloading model: {alias_or_id}")
        sdk_info = self.sdk.download_model(alias_or_id, force=force)
        return self._to_model_info(sdk_info, is_cached=True)

    def load_model(self, alias_or_id: str, ttl: int | None = None) -> ModelInfo:
        """Load a model into memory.

        Args:
            alias_or_id: Model alias or ID to load.
            ttl: Time-to-live in seconds. Uses settings default if not provided.

        Returns:
            ModelInfo for the loaded model.
        """
        ttl = ttl or self.settings.model_ttl
        logger.info(f"Loading model: {alias_or_id} (TTL: {ttl}s)")

        sdk_info = self.sdk.load_model(alias_or_id, ttl=ttl)
        return self._to_model_info(sdk_info, is_cached=True, is_loaded=True)

    def unload_model(self, alias_or_id: str, force: bool = False) -> None:
        """Unload a model from memory.

        Args:
            alias_or_id: Model alias or ID to unload.
            force: Force unload even if TTL hasn't expired.
        """
        logger.info(f"Unloading model: {alias_or_id}")
        self.sdk.unload_model(alias_or_id, force=force)

    def switch_model(self, alias_or_id: str, ttl: int | None = None) -> ModelInfo:
        """Switch to a different model.

        Unloads current model (if any) and loads the new one.

        Args:
            alias_or_id: Model alias or ID to switch to.
            ttl: Time-to-live for the new model.

        Returns:
            ModelInfo for the newly loaded model.
        """
        # Check if model exists
        info = self.sdk.get_model_info(alias_or_id)
        if not info:
            raise ModelNotFoundError(alias_or_id)

        # Unload current model if different
        if self._current_model and self._current_model != alias_or_id:
            try:
                self.unload_model(self._current_model, force=True)
            except Exception as e:
                logger.warning(f"Failed to unload current model: {e}")

        # Ensure model is downloaded
        if info.id not in {m.id for m in self.sdk.list_cached_models()}:
            self.download_model(alias_or_id)

        # Load new model
        model_info = self.load_model(alias_or_id, ttl=ttl)
        self._current_model = alias_or_id

        # Recreate OpenAI client (endpoint might have changed)
        self._openai_client = OpenAI(
            base_url=self.sdk.endpoint,
            api_key=self.sdk.api_key,
        )

        logger.info(f"Switched to model: {alias_or_id}")
        return model_info

    def refresh_model_ttl(self, alias_or_id: str | None = None, ttl: int | None = None) -> None:
        """Refresh the TTL for a loaded model.

        Args:
            alias_or_id: Model to refresh. Uses current model if not provided.
            ttl: New TTL in seconds.
        """
        model = alias_or_id or self._current_model
        if not model:
            raise ModelNotLoadedError("No model loaded")

        self.load_model(model, ttl=ttl)

    def get_cache_location(self) -> str:
        """Get the model cache directory path."""
        return self.sdk.get_cache_location()


# Global singleton instance
_manager: FoundryManager | None = None


def get_foundry_manager() -> FoundryManager:
    """Get the global Foundry manager instance."""
    global _manager
    if _manager is None:
        _manager = FoundryManager()
    return _manager


def initialize_foundry(model_alias: str | None = None) -> FoundryManager:
    """Initialize the global Foundry manager."""
    manager = get_foundry_manager()
    if not manager.is_initialized:
        manager.initialize(model_alias)
    return manager
