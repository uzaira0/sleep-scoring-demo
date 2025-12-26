#!/usr/bin/env python3
"""
Unified File Service.
Pure data service for file discovery and loading.
NO UI references allowed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sleep_scoring_app.core.nonwear_data import NonwearDataFactory
from sleep_scoring_app.services.data_service import DataManager
from sleep_scoring_app.services.memory_service import BoundedCache, estimate_object_size_mb
from sleep_scoring_app.services.nonwear_service import NonwearDataService

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import BatchDeleteResult, DeleteResult, FileInfo
    from sleep_scoring_app.data.database import DatabaseManager
    from sleep_scoring_app.ui.store import UIStore

logger = logging.getLogger(__name__)


class FileService:
    """Unified file operations service."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        store: UIStore,
        max_files: int = 1000,
    ) -> None:
        """Initialize FileService with proper DI."""
        self.db_manager = db_manager
        self.store = store
        self.data_manager = DataManager(database_manager=db_manager)

        # File discovery state
        self._max_files = max_files

        # Initialize internal state
        self._init_state(db_manager)

    @property
    def available_files(self) -> list[FileInfo]:
        """Get available files from Redux store (Single Source of Truth)."""
        return list(self.store.state.available_files)

    def _init_state(self, db_manager: DatabaseManager) -> None:
        """Initialize service state and sub-services."""
        self.main_48h_data = None
        self.main_48h_data_cache = BoundedCache(max_size=10, max_memory_mb=100)
        self.nonwear_service = NonwearDataService(db_manager)
        self.nonwear_data_factory = NonwearDataFactory(self.nonwear_service)
        self.marker_status_cache = BoundedCache(max_size=500, max_memory_mb=50)
        self._cached_date_ranges = BoundedCache(max_size=200, max_memory_mb=20)

    # === Data Operations ===

    def find_available_files(self) -> list[FileInfo]:
        """Find all available data files (DB + Folder)."""
        try:
            return self.data_manager.find_data_files()
        except Exception as e:
            logger.exception(f"FILE SERVICE: Error finding available files: {e}")
            return []

    def find_available_files_with_completion_count(self) -> list[FileInfo]:
        """Find available files and include completion counts."""
        from dataclasses import replace

        from sleep_scoring_app.core.dataclasses import FileInfo as FileInfoClass

        files = self.find_available_files()
        updated_files: list[FileInfo] = []
        for f in files:
            comp, total = self.get_file_completion_count(f.filename, files)
            updated_files.append(replace(f, completed_count=comp, total_dates=total))
        return updated_files

    def load_current_date_core(
        self,
        available_dates: list,
        current_date_index: int,
        current_date_48h_cache: BoundedCache,
        selected_file: str | None,
    ) -> tuple | None:
        """Pure data loading logic for current date."""
        if not available_dates or current_date_index < 0 or current_date_index >= len(available_dates):
            return None

        current_date = available_dates[current_date_index]
        filename = Path(selected_file).name if selected_file else None

        # Check cache
        cache_key = current_date.strftime("%Y-%m-%d")
        cached_data = current_date_48h_cache.get(cache_key)

        if cached_data is None:
            timestamps_48h, activity_data_48h = self.data_manager.load_real_data(current_date, 48, filename)
            if not timestamps_48h:
                return None
            current_date_48h_cache.put(cache_key, (timestamps_48h, activity_data_48h), estimate_object_size_mb((timestamps_48h, activity_data_48h)))
        else:
            timestamps_48h, activity_data_48h = cached_data

        # Store as main dataset
        self.main_48h_data = (timestamps_48h, activity_data_48h)
        return (timestamps_48h, activity_data_48h)

    def get_imported_files(self) -> list[dict[str, Any]]:
        """Get list of imported files from database (raw database records)."""
        try:
            return self.db_manager.get_available_files()
        except Exception as e:
            logger.exception(f"FILE SERVICE: Error getting imported files: {e}")
            return []

    def delete_file(self, filename: str) -> DeleteResult:
        """Delete a file from the database."""
        from sleep_scoring_app.core.constants import DeleteStatus
        from sleep_scoring_app.core.dataclasses import DeleteResult

        try:
            success = self.db_manager.delete_imported_file(filename)
            return DeleteResult(
                filename=filename,
                status=DeleteStatus.SUCCESS if success else DeleteStatus.FAILED,
                message="File deleted successfully" if success else "Failed to delete file",
            )
        except Exception as e:
            logger.exception(f"FILE SERVICE: Error deleting file {filename}: {e}")
            return DeleteResult(filename=filename, status=DeleteStatus.ERROR, message=str(e), error_message=str(e))

    def delete_files(self, filenames: list[str]) -> BatchDeleteResult:
        """Delete multiple files in batch."""
        from sleep_scoring_app.core.constants import DeleteStatus
        from sleep_scoring_app.core.dataclasses import BatchDeleteResult

        results = []
        successful = 0
        failed = 0

        for filename in filenames:
            result = self.delete_file(filename)
            results.append(result)
            if result.status == DeleteStatus.SUCCESS:
                successful += 1
            else:
                failed += 1

        return BatchDeleteResult(total_requested=len(filenames), successful=successful, failed=failed, results=results)

    def get_file_completion_count(self, filename: str, available_files: list[FileInfo] | None = None) -> tuple[int, int]:
        """Get file completion count from database."""
        try:
            # 1. Get total dates for this file
            total_dates = 0
            if available_files:
                for f in available_files:
                    if f.filename == filename:
                        total_dates = f.total_dates
                        break

            if total_dates == 0:
                # Fallback: query DB for unique dates in activity data
                total_dates = len(self.db_manager.get_file_date_ranges(filename))

            # 2. Get completed dates (those with metrics)
            metrics = self.db_manager.load_sleep_metrics(filename=filename)
            completed_dates = len({m.analysis_date for m in metrics})

            return (completed_dates, total_dates)
        except Exception as e:
            logger.debug(f"FILE SERVICE: Error getting completion count for {filename}: {e}")
            return (0, 0)

    def set_data_folder(self, folder_path: str | Path) -> bool:
        """Set data folder and validate."""
        return self.data_manager.set_data_folder(folder_path)

    def get_data_folder(self) -> str | None:
        """Get current data folder."""
        return self.data_manager.data_folder

    def toggle_database_mode(self, use_database: bool) -> None:
        """Toggle database mode."""
        self.data_manager.use_database = use_database

    def get_database_mode(self) -> bool:
        """Get current database mode."""
        return self.data_manager.use_database
