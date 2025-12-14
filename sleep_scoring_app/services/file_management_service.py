#!/usr/bin/env python3
"""
File Management Service for Sleep Scoring Application
Handles file deletion operations with Protocol-first design.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sleep_scoring_app.core.constants import DeleteStatus
from sleep_scoring_app.core.dataclasses import BatchDeleteResult, DeleteResult, ImportedFileInfo

if TYPE_CHECKING:
    from sleep_scoring_app.data.database import DatabaseManager

logger = logging.getLogger(__name__)


@runtime_checkable
class FileManagementService(Protocol):
    """Protocol for file management operations."""

    def get_imported_files(self) -> list[ImportedFileInfo]:
        """Get list of all imported files with metadata."""
        ...

    def delete_file(self, filename: str) -> DeleteResult:
        """Delete a single imported file and all its data."""
        ...

    def delete_files(self, filenames: list[str]) -> BatchDeleteResult:
        """Delete multiple imported files in batch."""
        ...

    def check_has_metrics(self, filename: str) -> bool:
        """Check if a file has associated sleep metrics."""
        ...


class FileManagementServiceImpl:
    """Implementation of file management service using DatabaseManager."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        """
        Initialize the file management service.

        Args:
            db_manager: Database manager instance for file operations

        """
        self.db_manager = db_manager

    def get_imported_files(self) -> list[ImportedFileInfo]:
        """
        Get list of all imported files with metadata.

        Returns:
            List of ImportedFileInfo objects containing file metadata

        """
        try:
            # Get files from database
            files = self.db_manager.get_available_files()

            # Convert to ImportedFileInfo objects
            imported_files = []
            for file_info in files:
                # Check if file has associated metrics
                has_metrics = self.check_has_metrics(file_info["filename"])

                imported_file = ImportedFileInfo(
                    filename=file_info["filename"],
                    participant_id=file_info.get("participant_id", "Unknown"),
                    date_range_start=file_info.get("date_start", ""),
                    date_range_end=file_info.get("date_end", ""),
                    record_count=file_info.get("total_records", 0),
                    import_date=file_info.get("import_date", ""),
                    has_metrics=has_metrics,
                )
                imported_files.append(imported_file)

            logger.debug("Retrieved %d imported files", len(imported_files))
            return imported_files

        except Exception as e:
            logger.exception("Failed to get imported files")
            return []

    def delete_file(self, filename: str) -> DeleteResult:
        """
        Delete a single imported file and all its data.

        Args:
            filename: Name of the file to delete

        Returns:
            DeleteResult with status and details

        """
        try:
            # Check if file exists
            files = self.db_manager.get_available_files()
            file_exists = any(f["filename"] == filename for f in files)

            if not file_exists:
                return DeleteResult(
                    status=DeleteStatus.NOT_FOUND,
                    filename=filename,
                    error_message=f"File not found: {filename}",
                )

            # Check if file has metrics
            has_metrics = self.check_has_metrics(filename)

            # Get record counts before deletion
            record_count = 0
            metrics_count = 0

            for file_info in files:
                if file_info["filename"] == filename:
                    record_count = file_info.get("total_records", 0)
                    break

            # Count metrics if they exist
            if has_metrics:
                metrics_list = self.db_manager.load_sleep_metrics(filename=filename)
                metrics_count = len(metrics_list)

            # Perform deletion (CASCADE will handle related data)
            success = self.db_manager.delete_imported_file(filename)

            if success:
                logger.info("Successfully deleted file: %s (%d records, %d metrics)", filename, record_count, metrics_count)
                return DeleteResult(
                    status=DeleteStatus.SUCCESS,
                    filename=filename,
                    records_deleted=record_count,
                    metrics_deleted=metrics_count,
                )
            return DeleteResult(
                status=DeleteStatus.FAILED,
                filename=filename,
                error_message="Database deletion failed",
            )

        except Exception as e:
            logger.exception("Error deleting file: %s", filename)
            return DeleteResult(
                status=DeleteStatus.FAILED,
                filename=filename,
                error_message=str(e),
            )

    def delete_files(self, filenames: list[str]) -> BatchDeleteResult:
        """
        Delete multiple imported files in batch.

        Args:
            filenames: List of file names to delete

        Returns:
            BatchDeleteResult with overall statistics and individual results

        """
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

        logger.info("Batch deletion complete: %d successful, %d failed out of %d requested", successful, failed, len(filenames))

        return BatchDeleteResult(
            total_requested=len(filenames),
            successful=successful,
            failed=failed,
            results=results,
        )

    def check_has_metrics(self, filename: str) -> bool:
        """
        Check if a file has associated sleep metrics.

        Args:
            filename: Name of the file to check

        Returns:
            True if file has metrics, False otherwise

        """
        try:
            metrics = self.db_manager.load_sleep_metrics(filename=filename)
            return len(metrics) > 0
        except Exception as e:
            logger.warning("Error checking metrics for %s: %s", filename, e)
            return False
