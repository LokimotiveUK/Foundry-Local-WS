"""Folder watcher service for auto-ingesting documents."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from src.rag.ingest import IngestionService, get_ingestion_service
from src.storage.watchers import FolderWatcherRepository, get_watcher_repository

logger = logging.getLogger(__name__)


class DocumentEventHandler(FileSystemEventHandler):
    """Handler for file system events that triggers document ingestion."""

    def __init__(
        self,
        watcher_id: str,
        pocket_id: str,
        file_patterns: list[str],
        ingestion_service: IngestionService,
        on_ingest: Callable[[str, str, bool], None] | None = None,
    ):
        """Initialize event handler.

        Args:
            watcher_id: ID of the watcher configuration.
            pocket_id: Target RAG pocket.
            file_patterns: Glob patterns for matching files.
            ingestion_service: Ingestion service instance.
            on_ingest: Callback when file is ingested (watcher_id, file_path, success).
        """
        super().__init__()
        self.watcher_id = watcher_id
        self.pocket_id = pocket_id
        self.file_patterns = file_patterns
        self.ingestion_service = ingestion_service
        self.on_ingest = on_ingest
        self._pending_events: dict[str, float] = {}
        self._debounce_seconds = 2.0
        self._lock = threading.Lock()

    def _matches_pattern(self, filename: str) -> bool:
        """Check if filename matches any configured pattern."""
        return any(fnmatch.fnmatch(filename, pattern) for pattern in self.file_patterns)

    def _should_process(self, event: FileSystemEvent) -> bool:
        """Determine if an event should trigger ingestion."""
        if event.is_directory:
            return False

        path = Path(event.src_path)
        return self._matches_pattern(path.name)

    def _debounce_and_process(self, file_path: str, is_delete: bool = False):
        """Debounce rapid events and process file."""
        import time

        with self._lock:
            current_time = time.time()
            last_event = self._pending_events.get(file_path, 0)

            if current_time - last_event < self._debounce_seconds:
                return

            self._pending_events[file_path] = current_time

        # Process in background thread
        threading.Thread(
            target=self._process_file,
            args=(file_path, is_delete),
            daemon=True,
        ).start()

    def _process_file(self, file_path: str, is_delete: bool):
        """Process a file change."""
        try:
            path = Path(file_path)

            if is_delete:
                # Delete from vector store
                deleted = self.ingestion_service.delete_document(
                    self.pocket_id,
                    file_path,
                )
                logger.info(f"Deleted {file_path}: {deleted} vectors removed")
                if self.on_ingest:
                    self.on_ingest(self.watcher_id, file_path, True)
            else:
                # Ingest or re-ingest
                if path.exists():
                    result = self.ingestion_service.ingest_file(
                        file_path=path,
                        pocket_id=self.pocket_id,
                        force=True,  # Always re-ingest on change
                    )
                    logger.info(
                        f"Ingested {path.name}: "
                        f"{'success' if result.success else 'failed'} "
                        f"({result.chunk_count} chunks)"
                    )
                    if self.on_ingest:
                        self.on_ingest(self.watcher_id, file_path, result.success)

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            if self.on_ingest:
                self.on_ingest(self.watcher_id, file_path, False)

    def on_created(self, event: FileSystemEvent):
        """Handle file creation."""
        if self._should_process(event):
            logger.debug(f"File created: {event.src_path}")
            self._debounce_and_process(event.src_path)

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification."""
        if self._should_process(event):
            logger.debug(f"File modified: {event.src_path}")
            self._debounce_and_process(event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion."""
        if self._should_process(event):
            logger.debug(f"File deleted: {event.src_path}")
            self._debounce_and_process(event.src_path, is_delete=True)

    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename."""
        if hasattr(event, 'dest_path'):
            src_matches = self._matches_pattern(Path(event.src_path).name)
            dest_matches = self._matches_pattern(Path(event.dest_path).name)

            # Delete from old location
            if src_matches:
                logger.debug(f"File moved from: {event.src_path}")
                self._debounce_and_process(event.src_path, is_delete=True)

            # Ingest at new location
            if dest_matches:
                logger.debug(f"File moved to: {event.dest_path}")
                self._debounce_and_process(event.dest_path)


class FolderWatcherService:
    """Service for managing folder watchers."""

    def __init__(
        self,
        repository: FolderWatcherRepository | None = None,
        ingestion_service: IngestionService | None = None,
    ):
        """Initialize watcher service.

        Args:
            repository: Watcher repository.
            ingestion_service: Ingestion service.
        """
        self._repository = repository
        self._ingestion_service = ingestion_service
        self._observer: Observer | None = None
        self._watches: dict[str, Any] = {}  # watcher_id -> watch handle
        self._handlers: dict[str, DocumentEventHandler] = {}
        self._running = False
        self._lock = threading.Lock()
        self._ingest_callbacks: list[Callable[[str, str, bool], None]] = []

    @property
    def repository(self) -> FolderWatcherRepository:
        """Get repository."""
        if self._repository is None:
            self._repository = get_watcher_repository()
        return self._repository

    @property
    def ingestion_service(self) -> IngestionService:
        """Get ingestion service."""
        if self._ingestion_service is None:
            self._ingestion_service = get_ingestion_service()
        return self._ingestion_service

    def add_ingest_callback(self, callback: Callable[[str, str, bool], None]):
        """Add callback for ingestion events.

        Args:
            callback: Function(watcher_id, file_path, success).
        """
        self._ingest_callbacks.append(callback)

    def _on_ingest(self, watcher_id: str, file_path: str, success: bool):
        """Handle ingestion event."""
        for callback in self._ingest_callbacks:
            try:
                callback(watcher_id, file_path, success)
            except Exception as e:
                logger.error(f"Ingest callback error: {e}")

    def start(self):
        """Start the watcher service."""
        with self._lock:
            if self._running:
                return

            self._observer = Observer()
            self._observer.start()
            self._running = True

            # Start all active watchers
            active_watchers = self.repository.get_active_watchers()
            for watcher in active_watchers:
                self._add_watch(watcher)

            logger.info(f"Folder watcher service started with {len(active_watchers)} watchers")

    def stop(self):
        """Stop the watcher service."""
        with self._lock:
            if not self._running:
                return

            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5.0)
                self._observer = None

            self._watches.clear()
            self._handlers.clear()
            self._running = False

            logger.info("Folder watcher service stopped")

    def _add_watch(self, watcher: dict[str, Any]) -> bool:
        """Add a watch for a watcher configuration.

        Args:
            watcher: Watcher dictionary.

        Returns:
            True if watch was added successfully.
        """
        if not self._observer or not self._running:
            return False

        watcher_id = watcher["id"]
        watch_path = watcher["path"]
        pocket_id = watcher["pocket_id"]
        recursive = watcher["recursive"]
        patterns = watcher["file_patterns"]

        # Check if path exists
        path = Path(watch_path)
        if not path.exists():
            logger.warning(f"Watch path does not exist: {watch_path}")
            return False

        if not path.is_dir():
            logger.warning(f"Watch path is not a directory: {watch_path}")
            return False

        # Create event handler
        handler = DocumentEventHandler(
            watcher_id=watcher_id,
            pocket_id=pocket_id,
            file_patterns=patterns,
            ingestion_service=self.ingestion_service,
            on_ingest=self._on_ingest,
        )

        try:
            watch = self._observer.schedule(
                handler,
                watch_path,
                recursive=recursive,
            )
            self._watches[watcher_id] = watch
            self._handlers[watcher_id] = handler
            logger.info(f"Added watch: {watcher['name']} -> {watch_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to add watch: {e}")
            return False

    def _remove_watch(self, watcher_id: str):
        """Remove a watch.

        Args:
            watcher_id: Watcher ID.
        """
        if not self._observer:
            return

        watch = self._watches.pop(watcher_id, None)
        self._handlers.pop(watcher_id, None)

        if watch:
            try:
                self._observer.unschedule(watch)
                logger.info(f"Removed watch: {watcher_id}")
            except Exception as e:
                logger.error(f"Error removing watch: {e}")

    def create_watcher(
        self,
        name: str,
        path: str,
        pocket_id: str,
        recursive: bool = False,
        file_patterns: list[str] | None = None,
        initial_scan: bool = True,
    ) -> dict[str, Any]:
        """Create and start a new watcher.

        Args:
            name: Display name.
            path: Path to watch.
            pocket_id: Target RAG pocket.
            recursive: Watch subdirectories.
            file_patterns: File patterns to match.
            initial_scan: Perform initial ingestion scan.

        Returns:
            Created watcher dictionary.
        """
        watcher = self.repository.create_watcher(
            name=name,
            path=path,
            pocket_id=pocket_id,
            recursive=recursive,
            file_patterns=file_patterns,
        )

        # Add to observer if running
        if self._running:
            self._add_watch(watcher)

        # Perform initial scan
        if initial_scan:
            self.scan_watcher(watcher["id"])

        return watcher

    def update_watcher(
        self,
        watcher_id: str,
        **kwargs,
    ) -> dict[str, Any] | None:
        """Update a watcher.

        Args:
            watcher_id: Watcher ID.
            **kwargs: Fields to update.

        Returns:
            Updated watcher or None.
        """
        watcher = self.repository.update_watcher(watcher_id, **kwargs)

        if watcher and self._running:
            # Restart watch with new config
            self._remove_watch(watcher_id)
            if watcher["is_active"]:
                self._add_watch(watcher)

        return watcher

    def delete_watcher(self, watcher_id: str) -> bool:
        """Delete a watcher.

        Args:
            watcher_id: Watcher ID.

        Returns:
            True if deleted.
        """
        if self._running:
            self._remove_watch(watcher_id)

        return self.repository.delete_watcher(watcher_id)

    def toggle_watcher(self, watcher_id: str, active: bool) -> dict[str, Any] | None:
        """Toggle watcher active state.

        Args:
            watcher_id: Watcher ID.
            active: New active state.

        Returns:
            Updated watcher or None.
        """
        watcher = self.repository.update_watcher(watcher_id, is_active=active)

        if watcher and self._running:
            if active:
                self._add_watch(watcher)
            else:
                self._remove_watch(watcher_id)

        return watcher

    def scan_watcher(self, watcher_id: str) -> dict[str, Any]:
        """Perform manual scan and ingestion for a watcher.

        Args:
            watcher_id: Watcher ID.

        Returns:
            Scan results.
        """
        watcher = self.repository.get_watcher(watcher_id)
        if not watcher:
            return {"error": "Watcher not found"}

        watch_path = Path(watcher["path"])
        if not watch_path.exists():
            return {"error": f"Path does not exist: {watch_path}"}

        patterns = watcher["file_patterns"]
        recursive = watcher["recursive"]

        # Find matching files
        files = []
        for pattern in patterns:
            if recursive:
                files.extend(watch_path.rglob(pattern))
            else:
                files.extend(watch_path.glob(pattern))

        files = sorted(set(files))

        # Ingest files
        results = []
        success_count = 0
        total_chunks = 0

        for file_path in files:
            result = self.ingestion_service.ingest_file(
                file_path=file_path,
                pocket_id=watcher["pocket_id"],
                force=False,  # Don't re-ingest unchanged files
            )
            results.append({
                "file": file_path.name,
                "success": result.success,
                "chunks": result.chunk_count,
                "error": result.error,
            })
            if result.success:
                success_count += 1
                total_chunks += result.chunk_count

        # Update stats
        self.repository.update_scan_stats(watcher_id, len(files))

        return {
            "watcher_id": watcher_id,
            "files_found": len(files),
            "files_ingested": success_count,
            "total_chunks": total_chunks,
            "results": results,
        }

    def get_status(self) -> dict[str, Any]:
        """Get watcher service status.

        Returns:
            Status dictionary.
        """
        watchers = self.repository.list_watchers()
        active_count = sum(1 for w in watchers if w["is_active"])

        return {
            "running": self._running,
            "total_watchers": len(watchers),
            "active_watchers": active_count,
            "watching": list(self._watches.keys()),
        }


# Global singleton
_watcher_service: FolderWatcherService | None = None


def get_watcher_service() -> FolderWatcherService:
    """Get the global watcher service instance."""
    global _watcher_service
    if _watcher_service is None:
        _watcher_service = FolderWatcherService()
    return _watcher_service
