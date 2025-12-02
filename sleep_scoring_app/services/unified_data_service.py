#!/usr/bin/env python3
"""
Unified Data Service for Sleep Scoring Application
Consolidates all data management functionality into a single service.
"""

from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from sleep_scoring_app.core.constants import ActivityDataPreference, UIColors
from sleep_scoring_app.core.nonwear_data import ActivityDataView, NonwearDataFactory
from sleep_scoring_app.services.data_service import DataManager
from sleep_scoring_app.services.diary_service import DiaryService
from sleep_scoring_app.services.memory_service import BoundedCache, estimate_object_size_mb
from sleep_scoring_app.services.nonwear_service import NonwearDataService
from sleep_scoring_app.utils.participant_extractor import extract_participant_info

if TYPE_CHECKING:
    from datetime import datetime

    from sleep_scoring_app.data.database import DatabaseManager
    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

logger = logging.getLogger(__name__)


class UnifiedDataService:
    """
    Unified service for all data management operations.

    This class uses a singleton pattern to allow access from dataclass methods
    during export operations where dependency injection is impractical.

    The singleton is set automatically in __init__ and accessed via get_instance().
    Primary usage: SleepMetrics._add_actilife_data_source_info() in dataclasses.py

    Note: This is the ONLY service that uses singleton access. All other services
    are passed via constructor injection through the main_window.
    """

    _instance: UnifiedDataService | None = None

    def __init__(self, main_window: SleepScoringMainWindow, db_manager: DatabaseManager) -> None:
        self.main_window = main_window
        self.db_manager = db_manager

        # Initialize components from existing services
        self._init_data_manager()
        self._init_file_manager()
        self._init_data_loader()
        self._init_nonwear_service()
        self._init_diary_service()

        # Bounded cache for marker completion status per file
        # max_size=500: Supports large studies with many participants
        # max_memory_mb=50: Completion data is small (~100 bytes per entry)
        self.marker_status_cache = BoundedCache(max_size=500, max_memory_mb=50)

        # Set this as the singleton instance
        UnifiedDataService._instance = self

    def _init_data_manager(self) -> None:
        """Initialize data manager functionality."""
        self.data_manager = DataManager(database_manager=self.db_manager)

        # Set up activity column preferences using configuration defaults
        from sleep_scoring_app.core.constants import ConfigDefaults

        self.data_manager.set_activity_column_preferences(
            preferred_activity_column=ConfigDefaults.DEFAULT_ACTIVITY_COLUMN, choi_activity_column=ConfigDefaults.DEFAULT_CHOI_ACTIVITY_COLUMN
        )

    def _init_file_manager(self) -> None:
        """Initialize file manager functionality."""
        # File manager state with memory bounds
        self.available_files = []
        self._max_files = 1000  # Limit to prevent memory issues with large directories

    def _init_data_loader(self) -> None:
        """Initialize data loader functionality."""
        # Data loading state - ensure consistency with main window default
        self.current_view_mode = 48  # Default to 48 hours
        # Bounded cache for 48-hour activity datasets
        # max_size=10: Keep 10 most recent participant datasets in memory
        # max_memory_mb=100: Each dataset ~5-10MB, allows quick switching between participants
        self.main_48h_data_cache = BoundedCache(max_size=10, max_memory_mb=100)
        self.main_48h_data = None  # Keep current reference for compatibility

        # Bounded cache for file date ranges (start/end dates per file)
        # max_size=200: Supports studies with many files
        # max_memory_mb=20: Date range tuples are small (~50 bytes each)
        self._cached_date_ranges = BoundedCache(max_size=200, max_memory_mb=20)

        # State validation flags to prevent race conditions
        self._state_update_in_progress = False

    def _init_nonwear_service(self) -> None:
        """Initialize nonwear data service."""
        self.nonwear_service = NonwearDataService(self.db_manager)
        self.nonwear_data_factory = NonwearDataFactory(self.nonwear_service)

    def _init_diary_service(self) -> None:
        """Initialize diary data service."""
        # DiaryService now uses embedded mapping configuration
        self.diary_service = DiaryService(self.db_manager)
        # Bounded cache for diary data per participant
        # max_size=100: Diary entries are typically one per participant per day
        # max_memory_mb=10: Diary data is small (~1KB per entry)
        self.diary_data_cache = BoundedCache(max_size=100, max_memory_mb=10)

    @classmethod
    def get_instance(cls) -> UnifiedDataService | None:
        """Get the singleton instance."""
        return cls._instance

    @classmethod
    def set_instance(cls, instance: UnifiedDataService) -> None:
        """Set the singleton instance."""
        cls._instance = instance

    # === Data Folder Management ===

    def set_data_folder(self, folder_path: str | Path) -> bool:
        """Set data folder and validate it."""
        try:
            self.data_manager.set_data_folder(folder_path)
            return True
        except Exception:
            logger.exception("Error setting data folder")
            return False

    def get_data_folder(self) -> str | None:
        """Get current data folder."""
        return self.data_manager.data_folder

    def toggle_database_mode(self, use_database: bool) -> None:
        """Toggle between database and CSV mode."""
        self.data_manager.toggle_database_mode(use_database)

        # CRITICAL FIX: Clear algorithm caches when data source mode changes
        self._clear_all_algorithm_caches()
        logger.debug("Cleared all algorithm caches due to database mode change")

        # Clear all caches when mode changes since data sources change
        self.invalidate_marker_status_cache()
        self.invalidate_date_ranges_cache()
        self.invalidate_main_data_cache()

    def get_database_mode(self) -> bool:
        """Get current database mode."""
        return self.data_manager.use_database

    def set_activity_column_preferences(
        self, preferred_activity_column: ActivityDataPreference, choi_activity_column: ActivityDataPreference
    ) -> None:
        """Set activity column preferences for data loading and algorithms."""
        self.data_manager.set_activity_column_preferences(preferred_activity_column, choi_activity_column)

        # CRITICAL FIX: Clear ALL algorithm-related caches when activity preferences change
        # This prevents stale algorithm results from being used with new activity sources
        self._clear_all_algorithm_caches()
        logger.debug("Cleared all algorithm caches after activity column preference change")

        # Clear all relevant caches when activity source changes
        # This ensures algorithm results are recalculated with the new activity data
        self.invalidate_marker_status_cache()  # Completion counts may change with new activity source
        self.invalidate_date_ranges_cache()  # Date ranges may be affected by activity source
        self.invalidate_main_data_cache()  # Main data cache contains activity-specific data

        logger.debug("Cleared all caches due to activity column preference change")

    def get_activity_column_preferences(self) -> tuple[str, str]:
        """Get current activity column preferences."""
        return (self.data_manager.preferred_activity_column, self.data_manager.choi_activity_column)

    # === File Discovery and Management ===

    def find_available_files(self) -> list[dict]:
        """Find all available data files with memory bounds."""
        try:
            old_file_count = len(self.available_files)
            logger.info("find_available_files called, current file count: %s", old_file_count)

            all_files = self.data_manager.find_data_files()

            # Apply size limit to prevent memory issues
            if len(all_files) > self._max_files:
                logger.warning("Found %s files, limiting to %s for memory safety", len(all_files), self._max_files)
                self.available_files = all_files[: self._max_files]
            else:
                self.available_files = all_files

            new_file_count = len(self.available_files)

            logger.info("Using %s files (found %s total)", new_file_count, len(all_files))
            if new_file_count > 0:
                logger.info("Sample files: %s", [f.get("display_name", f.get("filename", "unknown")) for f in self.available_files[:3]])

            # Only clear cache if the file list actually changed
            if old_file_count != new_file_count:
                logger.info("File count changed from %s to %s, clearing caches", old_file_count, new_file_count)
                self.marker_status_cache.clear()
                self.invalidate_date_ranges_cache()  # Clear date ranges cache too
            else:
                logger.debug("File count unchanged (%s), keeping cache", new_file_count)

            return self.available_files
        except Exception:
            logger.exception("Error finding available files")
            return []

    def load_available_files(self, preserve_selection: bool = True, load_completion_counts: bool = False) -> None:
        """Load available files and populate UI dropdown."""
        logger.info("load_available_files called with preserve_selection=%s, load_completion_counts=%s", preserve_selection, load_completion_counts)

        # Save current selection if requested
        current_selection = None
        current_date_index = None
        if preserve_selection and hasattr(self.main_window, "file_selector") and self.main_window.file_selector:
            current_selection = self.main_window.file_selector.get_selected_file_info()
            current_date_index = self.main_window.current_date_index if hasattr(self.main_window, "current_date_index") else None
            logger.info("Preserving selection: %s, date_index: %s", current_selection, current_date_index)

        # Find available files
        logger.info("Calling find_available_files()...")
        self.find_available_files()
        logger.info("find_available_files() completed, %s files found", len(self.available_files))

        # Populate UI table (without completion counts for fast loading)
        logger.info("Calling populate_file_table()...")
        self.populate_file_table(load_completion_counts=load_completion_counts)
        logger.info("populate_file_table() completed")

        # Restore selection if requested and possible
        if preserve_selection and current_selection is not None:
            self.restore_file_selection(current_selection, current_date_index)
        elif not self.available_files:
            # No longer auto-generate fake dates - just clear available dates
            self.main_window.available_dates = []
            self.main_window.current_date_index = 0

        # Update folder info label immediately after files are loaded
        if hasattr(self.main_window, "update_folder_info_label"):
            self.main_window.update_folder_info_label()

        # Perform periodic cache cleanup to manage memory
        self.cleanup_caches_if_needed()

        # Load completion counts synchronously during startup
        if not load_completion_counts and self.available_files:
            logger.info("Loading completion counts synchronously during startup")
            try:
                self._batch_load_completion_counts()
                self._update_dropdown_indicators_sync()
                logger.info("Synchronous completion count loading completed")
            except Exception:
                logger.exception("Error in synchronous completion loading")

    def populate_file_table(self, load_completion_counts=False) -> None:
        """Populate file selector table with available files and completion indicators."""
        # Clear the table
        if not (hasattr(self.main_window, "file_selector") and self.main_window.file_selector):
            logger.warning("File selector not available for table population")
            return

        self.main_window.file_selector.clear()

        if self.available_files:
            logger.info("Starting to add %s files...", len(self.available_files))

            # Load completion counts if requested - this also loads date ranges in batch
            if load_completion_counts:
                # Update splash
                if hasattr(self.main_window, "_update_splash"):
                    self.main_window._update_splash("Loading completion status...")
                self._batch_load_completion_counts()

            # Get batch date ranges for all files to avoid redundant queries
            if hasattr(self.main_window, "_update_splash"):
                self.main_window._update_splash("Loading file date ranges...")
            date_ranges_by_file = self._get_batch_file_date_ranges()

            for row_index, file_info in enumerate(self.available_files):
                # Update progress every 10 files
                if hasattr(self.main_window, "_update_splash") and row_index % 10 == 0:
                    self.main_window._update_splash(f"Processing files... ({row_index + 1}/{len(self.available_files)})")

                # Get filename for completion count
                filename = file_info.get("filename")
                if file_info.get("path"):
                    filename = Path(file_info["path"]).name

                if not filename:
                    logger.warning("Skipping file with no filename: %s", file_info)
                    continue

                # Get completion count and determine color
                completed_count, total_count = (0, 0)
                color = None
                if load_completion_counts:
                    completed_count, total_count = self.get_file_completion_count(filename)

                    # Determine color based on completion status
                    if total_count > 0:
                        if completed_count == total_count:
                            color = QColor(UIColors.DATE_WITH_MARKERS)  # Green for complete
                        elif completed_count == 0:
                            color = QColor(UIColors.DATE_NO_SLEEP)  # Red for none
                        else:
                            color = QColor(UIColors.DATE_PARTIAL_COMPLETION)  # Orange for partial

                # Get actual start and end dates from the batch-loaded data
                start_date, end_date = date_ranges_by_file.get(filename, ("", ""))

                # Prepare file info with completion data and actual dates
                table_file_info = {
                    **file_info,
                    "completed_count": completed_count,
                    "total_count": total_count,
                    "start_date": start_date,
                    "end_date": end_date,
                }

                # Add to table
                self.main_window.file_selector.add_file(table_file_info, color)

            logger.info("Successfully added %s files to table", len(self.available_files))
        # No files available - the table will be empty, which is appropriate
        elif self.get_database_mode():
            logger.info("No files imported - database mode")
        else:
            logger.info("No folder loaded - CSV mode")

    def populate_file_dropdown(self, load_completion_counts=False) -> None:
        """Legacy method - redirects to populate_file_table for backward compatibility."""
        self.populate_file_table(load_completion_counts)

    def restore_file_selection(self, previous_selection, previous_date_index) -> None:
        """Restore file selection after file list refresh."""
        if not previous_selection:
            return

        # Check if file_selector and its table exist before accessing
        if not (
            hasattr(self.main_window, "file_selector")
            and self.main_window.file_selector
            and hasattr(self.main_window.file_selector, "table")
            and self.main_window.file_selector.table
        ):
            logger.warning("File selector or table not available for selection restore")
            return

        # Try to find the previously selected file in the table
        for row in range(self.main_window.file_selector.table.rowCount()):
            row_file_info = self.main_window.file_selector.get_file_info_for_row(row)
            if row_file_info and (
                row_file_info.get("filename") == previous_selection.get("filename") or row_file_info.get("path") == previous_selection.get("path")
            ):
                # Select the row in the table
                self.main_window.file_selector.table.selectRow(row)

                # Restore the date index if it was set
                if previous_date_index is not None:
                    self.main_window.current_date_index = previous_date_index

                # Trigger the selection change to reload the file data
                if hasattr(self.main_window, "on_file_selected_from_table"):
                    self.main_window.on_file_selected_from_table(row_file_info)
                break

    def _batch_load_completion_counts(self) -> None:
        """Pre-load completion counts for all files in batch for efficiency."""
        if not self.available_files:
            return

        # Check if we already have cached data for all files
        all_cached = True
        for file_info in self.available_files:
            filename = file_info.get("filename")
            if file_info.get("path"):
                filename = Path(file_info["path"]).name
            if filename and self.marker_status_cache.get(filename) is None:
                all_cached = False
                break

        if all_cached:
            logger.info("All completion counts already cached, skipping batch load")
            return

        logger.info("Batch loading completion counts for all files...")

        # Get all filenames and file info mapping
        filenames = []
        file_info_by_name = {}
        for file_info in self.available_files:
            filename = file_info.get("filename")
            if file_info.get("path"):
                filename = Path(file_info["path"]).name
            if filename:
                filenames.append(filename)
                file_info_by_name[filename] = file_info

        # Batch load all sleep metrics in one query
        try:
            all_metrics = self.db_manager.load_sleep_metrics()
            metrics_by_file = {}
            for metrics in all_metrics:
                filename = metrics.filename
                if filename not in metrics_by_file:
                    metrics_by_file[filename] = []
                metrics_by_file[filename].append(metrics)
        except Exception as e:
            logger.warning("Failed to batch load sleep metrics: %s", e)
            metrics_by_file = {}

        # Batch load all date ranges for database files
        total_dates_by_file = {}
        try:
            # Always use the batch method for efficiency
            if hasattr(self.db_manager, "get_all_file_date_ranges"):
                total_dates_by_file = self.db_manager.get_all_file_date_ranges()
                # Store in bounded cache for reuse in table population to avoid redundant queries
                cache_key = "all_date_ranges"
                data_size = estimate_object_size_mb(total_dates_by_file)
                self._cached_date_ranges.put(cache_key, total_dates_by_file, data_size)
        except Exception as e:
            logger.warning("Failed to batch load date ranges: %s", e)

        # For each file, calculate completion counts and cache them
        for filename in filenames:
            if self.marker_status_cache.get(filename) is not None:
                continue  # Already cached

            try:
                # Get total dates - use cached value if available, otherwise calculate
                total_dates = total_dates_by_file.get(filename, 0)
                if total_dates == 0:
                    # For CSV files, we can't easily batch this, so use a simpler approach
                    file_info = file_info_by_name.get(filename)
                    if file_info and file_info.get("source") != "database":
                        # For CSV files, estimate from file metrics or use reasonable default
                        file_metrics = metrics_by_file.get(filename, [])
                        if file_metrics:
                            # Use number of unique dates from existing metrics as proxy
                            unique_dates = {m.analysis_date for m in file_metrics if m.analysis_date}
                            total_dates = max(len(unique_dates), 7)  # At least 7 days
                        else:
                            total_dates = 7  # Default assumption for CSV files
                    else:
                        total_dates = 0

                # Count completed dates from the batch-loaded metrics
                file_metrics = metrics_by_file.get(filename, [])
                dates_with_user_action = set()
                for metrics in file_metrics:
                    if metrics.analysis_date and (
                        (metrics.daily_sleep_markers and metrics.daily_sleep_markers.get_complete_periods())
                        or (metrics.onset_time == "NO_SLEEP" and metrics.offset_time == "NO_SLEEP")
                    ):
                        dates_with_user_action.add(metrics.analysis_date)

                completed_count = len(dates_with_user_action)

                # Cache the result
                self.marker_status_cache.put(filename, (completed_count, total_dates))

            except Exception as e:
                logger.warning("Error calculating completion for %s: %s", filename, e)
                self.marker_status_cache.put(filename, (0, 0))

        logger.info("Batch loaded completion counts for %s files", len(filenames))

    def _get_batch_file_date_ranges(self) -> dict[str, tuple[str, str]]:
        """
        Get date ranges for all files in one batch operation to avoid redundant queries.

        Returns:
            Dictionary mapping filename to (start_date_str, end_date_str) tuples

        """
        date_ranges_by_file = {}

        try:
            # For database files, use efficient batch query to get all date ranges at once
            if hasattr(self.db_manager, "get_all_file_date_ranges_batch"):
                db_date_ranges = self.db_manager.get_all_file_date_ranges_batch()
                date_ranges_by_file.update(db_date_ranges)
                logger.debug("Loaded date ranges for %s database files in single batch query", len(db_date_ranges))

            # For CSV files, we need to load them individually (but only once per table population)
            csv_files = [f for f in self.available_files if f.get("source") != "database"]
            if csv_files:
                logger.debug("Loading date ranges for %s CSV files", len(csv_files))
                for file_info in csv_files:
                    filename = file_info.get("filename")
                    if file_info.get("path"):
                        filename = Path(file_info["path"]).name

                    if filename and filename not in date_ranges_by_file:
                        try:
                            skip_rows = 10
                            if hasattr(self.main_window, "skip_rows_spin") and self.main_window.skip_rows_spin:
                                skip_rows = self.main_window.skip_rows_spin.value()
                            dates = self.data_manager.load_selected_file(file_info, skip_rows)
                            if dates:
                                start_date = min(dates)
                                end_date = max(dates)
                                date_ranges_by_file[filename] = (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
                            else:
                                date_ranges_by_file[filename] = ("", "")
                        except Exception as e:
                            logger.debug("Error loading CSV file dates for %s: %s", filename, e)
                            date_ranges_by_file[filename] = ("", "")

        except Exception as e:
            logger.warning("Error in batch date range loading: %s", e)

        return date_ranges_by_file

    def _calculate_file_completion_count(self, filename: str) -> tuple[int, int]:
        """Calculate completion count for a single file and cache the result."""
        try:
            # Get total dates for this file
            total_dates = self._get_file_total_dates(filename)

            # Get sleep metrics for this file
            file_metrics = self.db_manager.load_sleep_metrics(filename)

            # Count completed dates
            dates_with_user_action = set()
            for metrics in file_metrics:
                if metrics.analysis_date and (
                    (metrics.daily_sleep_markers and metrics.daily_sleep_markers.get_complete_periods())
                    or (metrics.onset_time == "NO_SLEEP" and metrics.offset_time == "NO_SLEEP")
                ):
                    dates_with_user_action.add(metrics.analysis_date)

            completed_count = len(dates_with_user_action)

            # Cache the result
            result = (completed_count, total_dates)
            self.marker_status_cache.put(filename, result)

            logger.debug("Calculated completion for %s: %s/%s", filename, completed_count, total_dates)
            return result

        except Exception as e:
            logger.warning("Error calculating completion for %s: %s", filename, e)
            result = (0, 0)
            self.marker_status_cache.put(filename, result)
            return result

    def get_file_completion_count(self, filename: str) -> tuple[int, int]:
        """Get file completion count as (completed/total) - returns tuple (completed_count, total_count)."""
        # Check cache first - this should always be populated after batch loading
        cached_result = self.marker_status_cache.get(filename)
        if cached_result is not None:
            return cached_result

        # If not in cache, recalculate it
        logger.debug("File %s not found in completion cache, recalculating", filename)
        return self._calculate_file_completion_count(filename)

    def _get_file_total_dates(self, filename: str) -> int:
        """Get total unique dates from the actual CSV file or database."""
        try:
            # Find the file info first to determine source
            file_info = None
            for info in self.available_files:
                if info.get("filename") == filename or (info.get("path") and Path(info["path"]).name == filename):
                    file_info = info
                    break

            if not file_info:
                return 0

            # Handle database files
            if file_info.get("source") == "database":
                try:
                    dates = self.db_manager.get_file_date_ranges(filename)
                    date_count = len(dates) if dates else 0
                    logger.debug("Database file %s: found %s dates", filename, date_count)
                    return date_count
                except Exception as e:
                    logger.debug("Error getting dates from database for %s: %s", filename, e)
                    return 0

            # Handle CSV files
            file_path = file_info.get("path")
            if not file_path:
                return 0

            # Load the file to get available dates
            skip_rows = 10
            if hasattr(self.main_window, "skip_rows_spin") and self.main_window.skip_rows_spin:
                skip_rows = self.main_window.skip_rows_spin.value()
            available_dates = self.data_manager.load_selected_file(file_info, skip_rows)

            return len(available_dates) if available_dates else 0

        except Exception as e:
            logger.exception("Error getting total dates from file %s: %s", filename, e)
            return 0

    def populate_date_dropdown(self) -> None:
        """Populate date dropdown with available dates and marker indicators."""
        # Store current selection to preserve it
        current_selection = getattr(self.main_window, "current_date_index", 0)

        # Date dropdown MUST exist by the time this is called
        date_dropdown = self.main_window.analysis_tab.date_dropdown

        date_dropdown.clear()

        available_dates = self.main_window.available_dates if hasattr(self.main_window, "available_dates") else None
        if not available_dates:
            date_dropdown.addItem("No dates available")
            # Center align the "No dates available" item
            date_dropdown.setItemData(0, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)
            date_dropdown.setEnabled(False)
            return

        # Get saved markers for current file to show indicators
        saved_data_by_date = {}
        if hasattr(self.main_window, "selected_file") and self.main_window.selected_file:
            try:
                if (
                    hasattr(self.main_window, "export_manager")
                    and self.main_window.export_manager
                    and hasattr(self.main_window.export_manager, "db_manager")
                ):
                    all_saved_metrics = self.main_window.export_manager.db_manager.load_sleep_metrics(
                        filename=Path(self.main_window.selected_file).name
                    )
                else:
                    all_saved_metrics = []
                for metrics in all_saved_metrics:
                    if hasattr(metrics, "analysis_date") and metrics.analysis_date:
                        # Check if it's a "no sleep" record
                        is_no_sleep = (
                            hasattr(metrics, "onset_time")
                            and metrics.onset_time == "NO_SLEEP"
                            and hasattr(metrics, "offset_time")
                            and metrics.offset_time == "NO_SLEEP"
                        )
                        has_markers = (
                            hasattr(metrics, "daily_sleep_markers")
                            and metrics.daily_sleep_markers
                            and metrics.daily_sleep_markers.get_complete_periods()
                            and not is_no_sleep
                        )
                        saved_data_by_date[metrics.analysis_date] = {
                            "has_markers": has_markers,
                            "is_no_sleep": is_no_sleep,
                        }
            except Exception as e:
                logger.debug("Could not load saved markers for dropdown indicators: %s", e)

        # Populate dropdown with date text and visual indicators
        for _i, date in enumerate(available_dates):
            date_str = date.strftime("%Y-%m-%d")

            # Check what type of data exists for this date
            date_data = saved_data_by_date.get(date_str, {})
            has_markers = date_data.get("has_markers", False)
            is_no_sleep = date_data.get("is_no_sleep", False)

            if is_no_sleep or has_markers:
                # Add the date text normally
                date_dropdown.addItem(date_str)

                # Set the text color based on marker type
                index = date_dropdown.count() - 1
                if is_no_sleep:
                    # Red text for no sleep
                    date_dropdown.setItemData(index, QColor(UIColors.DATE_NO_SLEEP), Qt.ItemDataRole.ForegroundRole)
                else:
                    # Green text for markers
                    date_dropdown.setItemData(index, QColor(UIColors.DATE_WITH_MARKERS), Qt.ItemDataRole.ForegroundRole)

                # Center align the dropdown item
                date_dropdown.setItemData(index, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)
            else:
                # Add the date text with normal color
                date_dropdown.addItem(date_str)

                # Center align the dropdown item
                index = date_dropdown.count() - 1
                date_dropdown.setItemData(index, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)

        # Enable dropdown and restore selection
        date_dropdown.setEnabled(True)
        if 0 <= current_selection < len(available_dates):
            date_dropdown.setCurrentIndex(current_selection)

    def load_current_date(self) -> None:
        """Load data for current date - always loads 48h as main dataset."""
        logger.info(
            "LOAD_CURRENT_DATE: Called with available_dates count: %s",
            len(self.main_window.available_dates) if self.main_window.available_dates else 0,
        )

        if not self.main_window.available_dates:
            logger.warning("LOAD_CURRENT_DATE: No available dates, returning early")
            return

        current_date = self.main_window.available_dates[self.main_window.current_date_index]

        # Update UI navigation buttons
        self.main_window.prev_date_btn.setEnabled(self.main_window.current_date_index > 0)
        self.main_window.next_date_btn.setEnabled(self.main_window.current_date_index < len(self.main_window.available_dates) - 1)

        # Update weekday label
        if hasattr(self.main_window, "weekday_label"):
            weekday_name = current_date.strftime("%A")  # Get full weekday name (e.g., "Monday")
            self.main_window.weekday_label.setText(f"Day of Week: {weekday_name}")

        # Update adjacent day markers if enabled (check both the state variable and checkbox)
        checkbox_checked = (
            hasattr(self.main_window, "show_adjacent_day_markers_checkbox") and self.main_window.show_adjacent_day_markers_checkbox.isChecked()
        )

        if checkbox_checked and hasattr(self.main_window, "_load_and_display_adjacent_day_markers"):
            # Small delay to ensure plot is fully loaded before adding adjacent day markers
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(100, self.main_window._load_and_display_adjacent_day_markers)

        # Always load 48h as main dataset (cache per date)
        cache_key = current_date.strftime("%Y-%m-%d")
        cached_data = self.main_window.current_date_48h_cache.get(cache_key)

        if cached_data is None:
            # Get filename for database queries
            filename = self.main_window.current_file_info.get("filename") if hasattr(self.main_window, "current_file_info") else None
            logger.info("LOAD_CURRENT_DATE: Loading real data for date %s, filename: %s", current_date, filename)
            timestamps_48h, activity_data_48h = self.data_manager.load_real_data(current_date, 48, filename)
            logger.info(
                "LOAD_CURRENT_DATE: Loaded %s timestamps and %s activity values",
                len(timestamps_48h) if timestamps_48h else 0,
                len(activity_data_48h) if activity_data_48h else 0,
            )

            # Estimate data size for cache management
            data_size_mb = estimate_object_size_mb((timestamps_48h, activity_data_48h))

            # Cache the data
            self.main_window.current_date_48h_cache.put(cache_key, (timestamps_48h, activity_data_48h), data_size_mb)
        else:
            timestamps_48h, activity_data_48h = cached_data

        # Store as main dataset and cache it
        self.main_48h_data = (timestamps_48h, activity_data_48h)

        # Also cache in bounded cache for memory management
        if timestamps_48h and activity_data_48h:
            main_cache_key = f"main_{cache_key}"
            main_data_size = estimate_object_size_mb((timestamps_48h, activity_data_48h))
            self.main_48h_data_cache.put(main_cache_key, (timestamps_48h, activity_data_48h), main_data_size)

        # First, ensure plot widget has the 48hr data for algorithms and tables
        # This is critical for proper index alignment
        if timestamps_48h and activity_data_48h and hasattr(self.main_window, "plot_widget") and self.main_window.plot_widget:
            self.main_window.plot_widget.main_48h_timestamps = timestamps_48h
            self.main_window.plot_widget.main_48h_activity = activity_data_48h
            # CRITICAL FIX: Clear stale axis_y data cache when loading new date
            # This prevents Sadeh algorithm from using axis_y data from previous dates
            self.main_window.plot_widget.main_48h_axis_y_data = None
            # Also clear axis_y timestamps to prevent alignment issues
            if hasattr(self.main_window.plot_widget, "main_48h_axis_y_timestamps"):
                self.main_window.plot_widget.main_48h_axis_y_timestamps = None
            logger.debug("Cleared stale axis_y cache and set new 48hr data in plot widget: %d points", len(timestamps_48h))
            # Also ensure we have the actual timestamps and activity data set
            self.main_window.plot_widget.timestamps = timestamps_48h
            self.main_window.plot_widget.activity_data = activity_data_48h

        # Always use full 48hr data - view mode only affects visual range
        timestamps, activity_data = timestamps_48h, activity_data_48h

        # Enhanced logging for plot data
        logger.info(
            "PLOT UPDATE: About to update plot with %s timestamps and %s activity values (view mode: %sh)",
            len(timestamps) if timestamps else 0,
            len(activity_data) if activity_data else 0,
            self.current_view_mode,
        )

        if timestamps and activity_data:
            logger.info(
                "PLOT UPDATE: Data range - timestamps: %s to %s, activity range: %s to %s",
                timestamps[0] if timestamps else None,
                timestamps[-1] if timestamps else None,
                min(activity_data) if activity_data else None,
                max(activity_data) if activity_data else None,
            )
        else:
            logger.warning("PLOT UPDATE: No data to plot - timestamps: %s, activity_data: %s", timestamps is not None, activity_data is not None)

        # Update the plot with filename for verification display
        filename = None
        if hasattr(self.main_window, "selected_file") and self.main_window.selected_file:
            filename = Path(self.main_window.selected_file).name

        self.main_window.plot_widget.set_data_and_restrictions(
            timestamps,
            activity_data,
            self.current_view_mode,
            filename=filename,
            activity_column_type=self.data_manager.preferred_activity_column,
            current_date=current_date,
        )

        # Force plot refresh
        try:
            self.main_window.plot_widget.update()
            logger.info("PLOT UPDATE: Plot widget update() called successfully")
        except Exception as e:
            logger.exception("PLOT UPDATE: Error calling plot widget update(): %s", e)

        # Load nonwear data for the plot
        self.load_nonwear_data_for_plot()

    def swap_activity_column(self, new_column_type: str) -> bool:
        """
        Seamlessly swap activity data column without triggering full reload or state loss.

        This method loads only the requested activity column data and uses the plot widget's
        swap_activity_data method to update the display while preserving all plot state.

        Args:
            new_column_type: The activity column to load (e.g., 'axis_y', 'vector_magnitude')

        Returns:
            True if swap was successful, False if failed

        """
        logger.info("SEAMLESS COLUMN SWAP: Initiating swap to %s column", new_column_type)

        try:
            # Check prerequisites
            if not (hasattr(self.main_window, "selected_file") and self.main_window.selected_file):
                logger.warning("SEAMLESS COLUMN SWAP: No file selected")
                return False

            if not (hasattr(self.main_window, "plot_widget") and self.main_window.plot_widget):
                logger.warning("SEAMLESS COLUMN SWAP: No plot widget available")
                return False

            if not (hasattr(self.main_window, "available_dates") and self.main_window.available_dates):
                logger.warning("SEAMLESS COLUMN SWAP: No available dates")
                return False

            # Get current context
            current_date = self.main_window.available_dates[self.main_window.current_date_index]
            filename = self.main_window.current_file_info.get("filename") if hasattr(self.main_window, "current_file_info") else None

            if not filename:
                logger.warning("SEAMLESS COLUMN SWAP: No filename available")
                return False

            logger.info("SEAMLESS COLUMN SWAP: Loading %s data for %s on %s", new_column_type, filename, current_date.date())

            # Load new activity data using targeted loading
            new_data = self.data_manager.load_activity_data_only(
                filename=filename,
                target_date=current_date,
                activity_column=new_column_type,
                hours=48,  # Always load 48h main dataset
            )

            if new_data is None:
                logger.warning("SEAMLESS COLUMN SWAP: Failed to load %s data", new_column_type)
                return False

            new_timestamps_48h, new_activity_data_48h = new_data

            # Filter to current view mode (same as load_current_date logic)
            if self.current_view_mode == 24:
                new_timestamps, new_activity_data = self.data_manager.filter_to_24h_view(new_timestamps_48h, new_activity_data_48h, current_date)
            else:
                new_timestamps, new_activity_data = new_timestamps_48h, new_activity_data_48h

            logger.info("SEAMLESS COLUMN SWAP: Filtered to %s data points for %sh view", len(new_activity_data), self.current_view_mode)

            # Perform seamless swap
            self.main_window.plot_widget.swap_activity_data(
                new_timestamps=new_timestamps, new_activity_data=new_activity_data, new_column_type=new_column_type
            )

            # Update main dataset for consistency
            self.main_48h_data = (new_timestamps_48h, new_activity_data_48h)

            # Update cache with new data
            cache_key = current_date.strftime("%Y-%m-%d") + f"_{new_column_type}"
            data_size_mb = estimate_object_size_mb((new_timestamps_48h, new_activity_data_48h))
            self.main_window.current_date_48h_cache.put(cache_key, (new_timestamps_48h, new_activity_data_48h), data_size_mb)

            # Reload nonwear data for the new activity column
            self.load_nonwear_data_for_plot()

            logger.info("SEAMLESS COLUMN SWAP: Successfully swapped to %s column", new_column_type)
            return True

        except Exception as e:
            logger.exception("SEAMLESS COLUMN SWAP: Unexpected error: %s", e)
            logger.exception("SEAMLESS COLUMN SWAP: Traceback: %s", traceback.format_exc())
            return False

    def invalidate_marker_status_cache(self, filename: str | None = None) -> None:
        """Invalidate marker status cache for a specific file or all files."""
        if filename:
            self.marker_status_cache.pop(filename)
        else:
            self.marker_status_cache.clear()

    def invalidate_date_ranges_cache(self) -> None:
        """Invalidate the date ranges cache to force refresh on next access."""
        self._cached_date_ranges.clear()

    def invalidate_main_data_cache(self) -> None:
        """Invalidate the main data cache to free memory."""
        self.main_48h_data_cache.clear()
        self.main_48h_data = None

    def update_file_table_indicators_only(self) -> None:
        """Update table visuals only. No filter changes, no reloads."""
        if not (hasattr(self.main_window, "file_selector") and self.main_window.file_selector and self.available_files):
            return

        try:
            # Check if file_selector and its table exist before accessing
            if not (hasattr(self.main_window.file_selector, "table") and self.main_window.file_selector.table):
                logger.warning("File selector or table not available for indicators update")
                return

            # Update each row in the table
            for row in range(self.main_window.file_selector.table.rowCount()):
                file_info = self.main_window.file_selector.get_file_info_for_row(row)
                if file_info:
                    filename = file_info.get("filename")

                    if not filename:
                        continue

                    # Get completion count for this file
                    completed_count, total_count = self.get_file_completion_count(filename)

                    # Update the markers column
                    from sleep_scoring_app.ui.widgets.file_selection_table import TableColumn

                    markers_col = self.main_window.file_selector.get_column_index(TableColumn.MARKERS)

                    if markers_col >= 0:
                        marker_item = self.main_window.file_selector.table.item(row, markers_col)
                        if marker_item:
                            marker_text = f"({completed_count}/{total_count})"
                            marker_item.setText(marker_text)

                            # Update color based on completion status
                            if total_count > 0:
                                if completed_count == total_count:
                                    color = QColor(UIColors.DATE_WITH_MARKERS)  # Green for complete
                                elif completed_count == 0:
                                    color = QColor(UIColors.DATE_NO_SLEEP)  # Red for none
                                else:
                                    color = QColor(UIColors.DATE_PARTIAL_COMPLETION)  # Orange for partial
                                marker_item.setForeground(color)
                            else:
                                marker_item.setForeground(QColor())  # Default color

        except Exception:
            logger.exception("Error in table indicator update")

    def update_file_dropdown_indicators_only(self) -> None:
        """Legacy method - redirects to update_file_table_indicators_only for backward compatibility."""
        self.update_file_table_indicators_only()

    def handle_markers_saved(self, file_path: str) -> None:
        """Handle marker save with explicit orchestration."""
        # Update visual indicators for all files
        self.update_file_table_indicators_only()

    def refresh_file_dropdown_indicators(self) -> None:
        """Refresh just the indicators in the file dropdown without full reload."""
        # Use explicit orchestration instead of hidden side effects
        current_file = self.main_window.selected_file
        if current_file:
            self.handle_markers_saved(current_file)
        else:
            # If no current file, just update indicators
            self.update_file_dropdown_indicators_only()

    def _update_dropdown_indicators_sync(self) -> None:
        """Update table indicators synchronously during startup."""
        # Delegate to the new explicit method
        self.update_file_table_indicators_only()

    def verify_cache_consistency(self, filename: str) -> None:
        """Verify and fix cache consistency after marker changes."""
        # Force refresh of this file's completion count
        self.invalidate_marker_status_cache(filename)
        self.get_file_completion_count(filename)  # Recalculate and cache

    def _clear_all_algorithm_caches(self) -> None:
        """Clear all algorithm-related caches to ensure fresh results on state changes."""
        try:
            # 1. Clear plot widget algorithm cache
            if hasattr(self.main_window, "plot_widget") and self.main_window.plot_widget:
                if hasattr(self.main_window.plot_widget, "_algorithm_cache"):
                    self.main_window.plot_widget._algorithm_cache.clear()
                    logger.debug("Cleared plot widget _algorithm_cache")

                # Clear main 48h algorithm results
                self.main_window.plot_widget.main_48h_sadeh_results = None
                logger.debug("Cleared plot widget main_48h_sadeh_results")

                # Clear main 48h axis_y data and timestamps
                self.main_window.plot_widget.main_48h_axis_y_data = None
                if hasattr(self.main_window.plot_widget, "main_48h_axis_y_timestamps"):
                    self.main_window.plot_widget.main_48h_axis_y_timestamps = None
                logger.debug("Cleared plot widget main_48h_axis_y_data and timestamps")

            # 2. Clear main window axis_y data cache
            if hasattr(self.main_window, "_cached_axis_y_data"):
                self.main_window._cached_axis_y_data = None
                logger.debug("Cleared main window _cached_axis_y_data")

            # 3. Clear current date cache to force reload of activity data
            if hasattr(self.main_window, "current_date_48h_cache"):
                self.main_window.current_date_48h_cache.clear()
                logger.debug("Cleared main window current_date_48h_cache")

            # 4. Clear main data service cache
            self.main_48h_data_cache.clear()
            self.main_48h_data = None
            logger.debug("Cleared unified service main_48h_data_cache")

            logger.info("Successfully cleared all algorithm-related caches")

        except Exception as e:
            logger.warning("Error during algorithm cache clearing: %s", e)

    def cleanup_caches_if_needed(self) -> None:
        """Perform periodic cache cleanup to manage memory usage."""
        try:
            # Check if we have too many files loaded
            if len(self.available_files) > self._max_files * 0.8:  # 80% threshold
                logger.info("Files approaching limit (%s/%s), performing cache cleanup", len(self.available_files), self._max_files)

                # Clear some cache entries to free memory
                self._cached_date_ranges.clear()

                # Only keep most recent main data
                if hasattr(self, "main_48h_data_cache"):
                    # Keep only the most recent 3 entries
                    while len(self.main_48h_data_cache.cache) > 3:
                        oldest_key = next(iter(self.main_48h_data_cache.cache))
                        del self.main_48h_data_cache.cache[oldest_key]
                        if oldest_key in self.main_48h_data_cache.access_times:
                            del self.main_48h_data_cache.access_times[oldest_key]
                        if oldest_key in self.main_48h_data_cache.memory_usage:
                            del self.main_48h_data_cache.memory_usage[oldest_key]

        except Exception as e:
            logger.warning("Error during cache cleanup: %s", e)

    # Delegation methods for other functionality
    def set_view_mode(self, hours: int) -> None:
        """Switch between 24h and 48h view modes with atomic state updates."""
        # Prevent concurrent state updates
        if self._state_update_in_progress:
            logger.warning("View mode change already in progress, ignoring request")
            return

        self._state_update_in_progress = True
        try:
            # Validate input
            if hours not in (24, 48):
                logger.error(f"Invalid view mode: {hours}. Must be 24 or 48.")
                return

            # Check if this is actually a change
            if self.current_view_mode == hours:
                logger.debug(f"View mode already set to {hours}h, no change needed")
                return

            logger.info(f"Changing view mode from {self.current_view_mode}h to {hours}h")

            # CRITICAL FIX: Clear all algorithm caches when view mode changes
            # This prevents stale algorithm results from being used with different view ranges
            self._clear_all_algorithm_caches()
            logger.debug("Cleared all algorithm caches due to view mode change")

            # Update state atomically
            old_view_mode = self.current_view_mode
            self.current_view_mode = hours

            # Update UI radio button states
            # These MUST exist by the time this is called - fail if not
            if hours == 24:
                self.main_window.analysis_tab.view_24h_btn.setChecked(True)
            else:
                self.main_window.analysis_tab.view_48h_btn.setChecked(True)
            logger.debug(f"Updated UI radio button states for {hours}h view")

            # ALWAYS update the plot view when mode changes
            if hasattr(self.main_window, "plot_widget") and self.main_window.plot_widget:
                # Get current data from plot widget if main_48h_data not available
                if self.main_48h_data:
                    timestamps, axis_y_data = self.main_48h_data
                elif hasattr(self.main_window.plot_widget, "timestamps") and self.main_window.plot_widget.timestamps:
                    timestamps = self.main_window.plot_widget.timestamps
                    axis_y_data = self.main_window.plot_widget.activity_data
                else:
                    logger.warning("No data available to update plot view")
                    return

                # Get current date if available
                current_date = None
                if hasattr(self.main_window, "available_dates") and self.main_window.available_dates:
                    if hasattr(self.main_window, "current_date_index") and self.main_window.current_date_index < len(
                        self.main_window.available_dates
                    ):
                        current_date = self.main_window.available_dates[self.main_window.current_date_index]

                # Store 48hr data reference if we have it
                if self.main_48h_data and (
                    not hasattr(self.main_window.plot_widget, "main_48h_timestamps") or not self.main_window.plot_widget.main_48h_timestamps
                ):
                    self.main_window.plot_widget.main_48h_timestamps = self.main_48h_data[0]
                    self.main_window.plot_widget.main_48h_activity = self.main_48h_data[1]
                    logger.debug("Set 48hr reference data in plot widget during view mode switch: %d points", len(self.main_48h_data[0]))

                # Capture current zoom range before updating
                current_view_range = self.main_window.plot_widget.vb.viewRange()
                saved_x_range = current_view_range[0]
                saved_y_range = current_view_range[1]
                logger.debug(f"Saved zoom range before view mode switch: x={saved_x_range}, y={saved_y_range}")

                # ALWAYS update the plot - this is the critical fix
                self.main_window.plot_widget.update_data_and_view_only(timestamps, axis_y_data, hours, current_date=current_date)
                logger.info(f"Updated plot view to {hours}h mode")

                # Restore the user's zoom range
                self.main_window.plot_widget.vb.setRange(xRange=saved_x_range, yRange=saved_y_range, padding=0)
                logger.debug("Restored zoom range after view mode switch")

                # Reload nonwear data for the new view
                self.load_nonwear_data_for_plot()

            logger.info(f"View mode successfully changed to {hours}h")

        except Exception as e:
            # Rollback state on error
            self.current_view_mode = old_view_mode if "old_view_mode" in locals() else 24
            logger.exception(f"Error during view mode change: {e}")
            raise
        finally:
            self._state_update_in_progress = False

    def change_view_range_only(self, hours: int) -> None:
        """Change view range without reloading data - preserves sleep markers."""
        self.set_view_mode(hours)

    def filter_to_24h_view(self, timestamps_48h, activity_data_48h, target_date) -> tuple[list, list]:
        """Filter 48h dataset to 24h noon-to-noon view."""
        return self.data_manager.filter_to_24h_view(timestamps_48h, activity_data_48h, target_date)

    def load_nonwear_data_for_plot(self) -> None:
        """Load nonwear data using new immutable architecture."""
        if not (hasattr(self.main_window, "selected_file") and self.main_window.selected_file):
            logger.debug("No file selected, cannot load nonwear data")
            return

        if not (hasattr(self.main_window, "plot_widget") and self.main_window.plot_widget):
            logger.warning("Activity plot not available for nonwear data display")
            return

        # Get current activity data from plot widget
        if not (hasattr(self.main_window.plot_widget, "timestamps") and self.main_window.plot_widget.timestamps):
            logger.debug("Activity data not loaded, cannot load nonwear data")
            return

        try:
            filename = Path(self.main_window.selected_file).name
            logger.debug("Loading nonwear data for file: %s", filename)

            # Always use the full 48hr data for nonwear processing
            # Priority: Use main_48h_timestamps with matching main_48h_activity
            timestamps_to_use = None
            axis_y_data = None

            # First try: Use 48hr timestamps with 48hr activity (most reliable pair)
            if (
                hasattr(self.main_window.plot_widget, "main_48h_timestamps")
                and self.main_window.plot_widget.main_48h_timestamps
                and hasattr(self.main_window.plot_widget, "main_48h_activity")
                and self.main_window.plot_widget.main_48h_activity
            ):
                ts_48h = self.main_window.plot_widget.main_48h_timestamps
                act_48h = self.main_window.plot_widget.main_48h_activity

                if len(ts_48h) == len(act_48h):
                    timestamps_to_use = ts_48h
                    axis_y_data = act_48h
                    logger.debug("Using matched 48hr timestamps/activity: %d points", len(timestamps_to_use))

            # Second try: Use current view timestamps with current activity_data
            if timestamps_to_use is None:
                if (
                    hasattr(self.main_window.plot_widget, "timestamps")
                    and self.main_window.plot_widget.timestamps
                    and hasattr(self.main_window.plot_widget, "activity_data")
                    and self.main_window.plot_widget.activity_data
                ):
                    ts_current = self.main_window.plot_widget.timestamps
                    act_current = self.main_window.plot_widget.activity_data

                    if len(ts_current) == len(act_current):
                        timestamps_to_use = ts_current
                        axis_y_data = act_current
                        logger.debug("Using matched current timestamps/activity: %d points", len(timestamps_to_use))

            if not axis_y_data or not timestamps_to_use:
                logger.warning("Could not obtain matched data for nonwear processing")
                return

            # Final safety check
            if len(timestamps_to_use) != len(axis_y_data):
                logger.error(
                    "Timestamp/data length mismatch after all attempts: %d timestamps vs %d data points", len(timestamps_to_use), len(axis_y_data)
                )
                return

            # Create ActivityDataView from full 48hr data
            activity_view = ActivityDataView.create(
                timestamps=list(timestamps_to_use),
                counts=list(axis_y_data),
                filename=filename,
            )

            # Get nonwear data using the factory (handles caching and computation)
            nonwear_data = self.nonwear_data_factory.get_nonwear_data(activity_view)

            # Set the nonwear data on the activity plot using new interface
            self.main_window.plot_widget.set_nonwear_data(nonwear_data)

            logger.debug(
                "Loaded nonwear data: %d sensor periods, %d choi periods, %d wear minutes, %d nonwear minutes",
                len(nonwear_data.sensor_periods),
                len(nonwear_data.choi_periods),
                len(nonwear_data.activity_view) - nonwear_data.get_nonwear_count("sensor"),
                nonwear_data.get_nonwear_count("sensor"),
            )

        except Exception as e:
            logger.exception("Error loading nonwear data for plot: %s", e)

    def _update_date_dropdown_current_color(self) -> None:
        """Update the color of the currently selected item in the dropdown display."""
        # Date dropdown MUST exist by the time this is called
        date_dropdown = self.main_window.analysis_tab.date_dropdown
        if not date_dropdown or date_dropdown.count() == 0:
            return

        current_index = date_dropdown.currentIndex()
        if current_index < 0:
            return

        # Actively determine the color based on current marker status
        color = None
        if (
            hasattr(self.main_window, "selected_file")
            and self.main_window.selected_file
            and hasattr(self.main_window, "available_dates")
            and self.main_window.available_dates
            and current_index < len(self.main_window.available_dates)
        ):
            # Get current date and filename
            current_date = self.main_window.available_dates[current_index]
            date_str = current_date.strftime("%Y-%m-%d")
            filename = Path(self.main_window.selected_file).name

            try:
                # Check for saved markers for this specific date
                saved_metrics = self.main_window.export_manager.db_manager.load_sleep_metrics(filename=filename, analysis_date=date_str)

                if saved_metrics:
                    latest_record = saved_metrics[0]  # Most recent record
                    is_no_sleep = (
                        hasattr(latest_record, "onset_time")
                        and latest_record.onset_time == "NO_SLEEP"
                        and hasattr(latest_record, "offset_time")
                        and latest_record.offset_time == "NO_SLEEP"
                    )
                    has_markers = (
                        hasattr(latest_record, "daily_sleep_markers")
                        and latest_record.daily_sleep_markers
                        and latest_record.daily_sleep_markers.get_complete_periods()
                        and not is_no_sleep
                    )

                    # Set appropriate color
                    if has_markers:
                        color = QColor(UIColors.DATE_WITH_MARKERS)  # Green
                    elif is_no_sleep:
                        color = QColor(UIColors.DATE_NO_SLEEP)  # Red

                    # Also update the item data in the dropdown for consistency
                    if color:
                        date_dropdown.setItemData(current_index, color, Qt.ItemDataRole.ForegroundRole)
                # If no saved data, use default (no color)
            except Exception as e:
                logger.debug("Error checking marker status for date %s: %s", date_str, e)

        # Fall back to stored color data if dynamic check failed
        if color is None:
            color = date_dropdown.itemData(current_index, Qt.ItemDataRole.ForegroundRole)

        if color and isinstance(color, QColor):
            # Apply the color to the combobox text using stylesheet while preserving centering
            color_hex = color.name()
            style = f"""
                QComboBox {{
                    padding: 8px 20px 8px 20px;
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 120px;
                    color: {color_hex};
                }}
                QLineEdit {{
                    color: {color_hex};
                    text-align: center;
                }}
            """
            date_dropdown.setStyleSheet(style)

            # Also ensure the line edit alignment is preserved programmatically
            line_edit = date_dropdown.lineEdit()
            if line_edit:
                line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            # Reset to default style if no color while preserving centering
            style = """
                QComboBox {
                    padding: 8px 20px 8px 20px;
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 120px;
                }
                QLineEdit {
                    text-align: center;
                }
            """
            date_dropdown.setStyleSheet(style)

            # Ensure alignment is preserved
            line_edit = date_dropdown.lineEdit()
            if line_edit:
                line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # === Diary Data Management ===

    def load_diary_data_for_current_file(self) -> list:
        """Load diary data for currently selected file."""
        if not hasattr(self.main_window, "selected_file") or not self.main_window.selected_file:
            logger.debug("No file selected, cannot load diary data")
            return []

        try:
            # Extract participant ID from filename using centralized extractor
            filename = Path(self.main_window.selected_file).name
            participant_info = extract_participant_info(filename)
            participant_id = participant_info.full_id if participant_info.numerical_id != "Unknown" else None

            if not participant_id:
                logger.debug(f"No participant ID found in filename: {filename}")
                return []

            # Check cache first
            cache_key = f"diary_{participant_id}"
            cached_data = self.diary_data_cache.get(cache_key)
            if cached_data:
                logger.debug(f"Using cached diary data for participant {participant_id}")
                return cached_data

            # Load from database
            diary_data = self.diary_service.get_diary_data_for_participant(participant_id)

            # Cache the data
            if diary_data:
                data_size = estimate_object_size_mb(diary_data)
                self.diary_data_cache.put(cache_key, diary_data, data_size)
                logger.debug(f"Loaded and cached {len(diary_data)} diary entries for participant {participant_id}")
            else:
                logger.debug(f"No diary data found for participant {participant_id}")

            return diary_data

        except Exception as e:
            logger.exception(f"Failed to load diary data for current file: {e}")
            return []

    def get_diary_data_for_date(self, target_date: datetime) -> dict | None:
        """
        Get diary data for currently selected file and specific date.

        Args:
            target_date: Date to retrieve diary data for

        Returns:
            Dictionary with diary data or None if not found

        """
        if not hasattr(self.main_window, "selected_file") or not self.main_window.selected_file:
            return None

        try:
            # Extract participant ID from filename using centralized extractor
            filename = Path(self.main_window.selected_file).name
            participant_info = extract_participant_info(filename)
            participant_id = participant_info.full_id if participant_info.numerical_id != "Unknown" else None

            if not participant_id:
                return None

            # Get diary entry for the specific date
            diary_entry = self.diary_service.get_diary_data_for_date(participant_id, target_date)

            if diary_entry:
                # Convert to dictionary for UI consumption
                return {
                    "participant_id": diary_entry.participant_id,
                    "diary_date": diary_entry.diary_date,
                    "bedtime": diary_entry.bedtime or "--:--",
                    "wake_time": diary_entry.wake_time or "--:--",
                    "sleep_onset_time": diary_entry.sleep_onset_time or "--:--",
                    "sleep_offset_time": diary_entry.sleep_offset_time or "--:--",
                    "in_bed_time": diary_entry.in_bed_time or "--:--",
                    "sleep_quality": diary_entry.sleep_quality,
                    "nap_occurred": diary_entry.nap_occurred,
                    "nap_onset_time": diary_entry.nap_onset_time or "--:--",
                    "nap_offset_time": diary_entry.nap_offset_time or "--:--",
                    "nonwear_occurred": diary_entry.nonwear_occurred,
                    "nonwear_reason": diary_entry.nonwear_reason or "",
                    "diary_notes": diary_entry.diary_notes or "",
                }

            return None

        except Exception as e:
            logger.exception(f"Failed to get diary data for date {target_date}: {e}")
            return None

    def check_current_participant_has_diary_data(self) -> bool:
        """Check if current participant has diary data available."""
        if not hasattr(self.main_window, "selected_file") or not self.main_window.selected_file:
            return False

        try:
            filename = Path(self.main_window.selected_file).name
            participant_info = extract_participant_info(filename)
            participant_id = participant_info.full_id if participant_info.numerical_id != "Unknown" else None

            if not participant_id:
                return False

            return self.diary_service.check_participant_has_diary_data(participant_id)

        except Exception as e:
            logger.exception(f"Failed to check diary data availability: {e}")
            return False

    def get_diary_stats(self) -> dict:
        """Get diary data statistics."""
        try:
            return self.diary_service.get_diary_stats()
        except Exception as e:
            logger.exception(f"Failed to get diary stats: {e}")
            return {
                "total_entries": 0,
                "unique_participants": 0,
                "date_range_start": None,
                "date_range_end": None,
            }

    def clear_diary_cache(self) -> None:
        """Clear the diary data cache."""
        try:
            self.diary_data_cache.clear()
            logger.debug("Diary data cache cleared")
        except Exception as e:
            logger.exception(f"Failed to clear diary cache: {e}")

    # === ActiLife Integration Stubs ===
    # These methods are called by export functionality but not implemented
    # Adding stubs to prevent AttributeError during export

    def get_sadeh_data_source(self, participant_id: str):
        """Get Sadeh data source for participant - stub implementation."""
        from sleep_scoring_app.core.constants import SadehDataSource

        logger.debug(f"get_sadeh_data_source called for {participant_id} - returning CALCULATED (stub)")
        return SadehDataSource.CALCULATED

    def has_actilife_sadeh_data(self, participant_id: str) -> bool:
        """Check if ActiLife Sadeh data exists for participant - stub implementation."""
        logger.debug(f"has_actilife_sadeh_data called for {participant_id} - returning False (stub)")
        return False

    def validate_actilife_against_calculated(self, participant_id: str) -> dict:
        """Validate ActiLife vs calculated data - stub implementation."""
        logger.debug(f"validate_actilife_against_calculated called for {participant_id} - returning empty result (stub)")
        return {"status": "error", "message": "ActiLife validation not implemented"}

    @property
    def config_manager(self):
        """Configuration manager - stub implementation."""
        logger.debug("config_manager accessed - returning None (stub)")
