#!/usr/bin/env python3
"""
Unit tests for UnifiedDataService.

Tests the facade pattern that delegates to focused sub-services for
file loading, navigation, caching, and diary management.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from sleep_scoring_app.services.unified_data_service import UnifiedDataService


class TestUnifiedDataService:
    """Tests for UnifiedDataService class."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        return MagicMock()

    @pytest.fixture
    def unified_service(self, mock_db_manager):
        """Create UnifiedDataService instance."""
        return UnifiedDataService(db_manager=mock_db_manager)

    @pytest.fixture
    def ui_components(self):
        """Create mock UI components."""
        return {
            "selected_file": "test_file.csv",
            "available_dates": ["2024-01-10", "2024-01-11"],
            "current_date_index": 0,
            "current_file_info": {"filename": "test_file.csv"},
            "plot_widget": MagicMock(),
            "analysis_tab": MagicMock(),
        }

    # === Initialization Tests ===

    def test_init_creates_sub_services(self, unified_service):
        """Test that initialization creates all sub-services."""
        assert unified_service._file_service is not None
        assert unified_service._algorithm_service is not None
        assert unified_service._diary_service is not None
        assert unified_service._navigation_service is not None
        assert unified_service._cache_service is not None
        assert unified_service._file_listing_service is not None
        assert unified_service._date_navigation_service is not None

    def test_init_sets_singleton_instance(self, unified_service):
        """Test that initialization sets singleton instance."""
        assert UnifiedDataService._instance is unified_service
        assert UnifiedDataService.get_instance() is unified_service

    def test_init_exposes_data_manager(self, unified_service):
        """Test that data_manager is exposed for legacy compatibility."""
        assert unified_service.data_manager is not None

    # === UI Components Tests ===

    def test_set_ui_components(self, unified_service, ui_components):
        """Test setting UI components."""
        unified_service.set_ui_components(ui_components)

        assert unified_service._ui_components == ui_components

    def test_set_ui_components_delegates_to_sub_services(self, unified_service, ui_components):
        """Test that setting UI components delegates to sub-services."""
        with patch.object(unified_service._cache_service, "set_ui_components") as mock_cache:
            with patch.object(unified_service._file_listing_service, "set_ui_components") as mock_listing:
                with patch.object(unified_service._date_navigation_service, "set_ui_components") as mock_date:
                    unified_service.set_ui_components(ui_components)

        mock_cache.assert_called_once_with(ui_components)
        mock_listing.assert_called_once_with(ui_components)
        mock_date.assert_called_once_with(ui_components)

    # === Property Accessor Tests ===

    def test_available_files_getter(self, unified_service):
        """Test getting available_files property."""
        unified_service._file_service.available_files = [{"filename": "test.csv"}]

        assert unified_service.available_files == [{"filename": "test.csv"}]

    def test_available_files_setter(self, unified_service):
        """Test setting available_files property."""
        unified_service.available_files = [{"filename": "new.csv"}]

        assert unified_service._file_service.available_files == [{"filename": "new.csv"}]

    def test_current_view_mode_getter(self, unified_service):
        """Test getting current_view_mode property."""
        unified_service._file_service.current_view_mode = 48

        assert unified_service.current_view_mode == 48

    def test_current_view_mode_setter(self, unified_service):
        """Test setting current_view_mode property."""
        unified_service.current_view_mode = 24

        assert unified_service._file_service.current_view_mode == 24

    def test_diary_service_property(self, unified_service):
        """Test diary_service property accessor."""
        assert unified_service.diary_service is unified_service._diary_service

    # === Singleton Pattern Tests ===

    def test_get_instance_returns_singleton(self, unified_service):
        """Test get_instance returns the singleton instance."""
        instance = UnifiedDataService.get_instance()

        assert instance is unified_service

    def test_set_instance(self):
        """Test manually setting singleton instance."""
        new_instance = MagicMock()
        UnifiedDataService.set_instance(new_instance)

        assert UnifiedDataService.get_instance() is new_instance

        # Cleanup
        UnifiedDataService.set_instance(None)

    # === Data Folder Management Tests ===

    def test_set_data_folder_delegates(self, unified_service):
        """Test set_data_folder delegates to file service."""
        with patch.object(unified_service._file_service, "set_data_folder", return_value=True):
            result = unified_service.set_data_folder("/test/folder")

        assert result is True
        unified_service._file_service.set_data_folder.assert_called_once_with("/test/folder")

    def test_get_data_folder_delegates(self, unified_service):
        """Test get_data_folder delegates to file service."""
        unified_service._file_service.get_data_folder = MagicMock(return_value="/test/folder")

        result = unified_service.get_data_folder()

        assert result == "/test/folder"

    def test_toggle_database_mode_delegates(self, unified_service):
        """Test toggle_database_mode delegates correctly."""
        with patch.object(unified_service._file_service, "toggle_database_mode"):
            with patch.object(unified_service._cache_service, "clear_all_caches_on_mode_change"):
                unified_service.toggle_database_mode(True)

        unified_service._file_service.toggle_database_mode.assert_called_once_with(True)
        unified_service._cache_service.clear_all_caches_on_mode_change.assert_called_once()

    def test_get_database_mode_delegates(self, unified_service):
        """Test get_database_mode delegates to file service."""
        unified_service._file_service.get_database_mode = MagicMock(return_value=True)

        result = unified_service.get_database_mode()

        assert result is True

    def test_set_activity_column_preferences_delegates(self, unified_service):
        """Test set_activity_column_preferences delegates correctly."""
        from sleep_scoring_app.core.constants import ActivityDataPreference

        with patch.object(unified_service._file_service, "set_activity_column_preferences"):
            with patch.object(unified_service._cache_service, "clear_all_caches_on_activity_column_change"):
                unified_service.set_activity_column_preferences(
                    ActivityDataPreference.AXIS_Y,
                    ActivityDataPreference.VECTOR_MAGNITUDE,
                )

        unified_service._file_service.set_activity_column_preferences.assert_called_once()

    # === File Discovery Tests ===

    def test_find_available_files_delegates(self, unified_service):
        """Test find_available_files delegates to file service."""
        expected_files = [{"filename": "test.csv"}]
        unified_service._file_service.find_available_files = MagicMock(return_value=expected_files)

        result = unified_service.find_available_files()

        assert result == expected_files

    def test_load_available_files_delegates(self, unified_service):
        """Test load_available_files delegates correctly."""
        unified_service.available_files = [{"filename": "test.csv"}]

        with patch.object(unified_service._file_listing_service, "load_available_files"):
            with patch.object(unified_service._cache_service, "cleanup_caches_if_needed"):
                unified_service.load_available_files(preserve_selection=True)

        unified_service._file_listing_service.load_available_files.assert_called_once_with(True, False)

    def test_populate_file_table_delegates(self, unified_service):
        """Test populate_file_table delegates to file listing service."""
        with patch.object(unified_service._file_listing_service, "populate_file_table"):
            unified_service.populate_file_table(load_completion_counts=True)

        unified_service._file_listing_service.populate_file_table.assert_called_once_with(True)

    def test_get_file_completion_count_delegates(self, unified_service):
        """Test get_file_completion_count delegates correctly."""
        unified_service._file_listing_service.get_file_completion_count = MagicMock(return_value=(3, 10))

        result = unified_service.get_file_completion_count("test.csv")

        assert result == (3, 10)

    # === Date Navigation Tests ===

    def test_populate_date_dropdown_delegates(self, unified_service, ui_components):
        """Test populate_date_dropdown delegates correctly."""
        unified_service.set_ui_components(ui_components)

        with patch.object(unified_service._date_navigation_service, "populate_date_dropdown"):
            unified_service.populate_date_dropdown()

        unified_service._date_navigation_service.populate_date_dropdown.assert_called_once()

    def test_load_current_date_delegates(self, unified_service, ui_components):
        """Test load_current_date delegates correctly."""
        unified_service.set_ui_components(ui_components)

        with patch.object(unified_service._date_navigation_service, "load_current_date"):
            unified_service.load_current_date()

        unified_service._date_navigation_service.load_current_date.assert_called_once()

    def test_load_current_date_without_ui_components(self, unified_service):
        """Test load_current_date handles missing UI components."""
        unified_service._ui_components = None

        # Should not raise error
        unified_service.load_current_date()

    # === File Loading and View Management Tests ===

    def test_swap_activity_column_delegates(self, unified_service, ui_components):
        """Test swap_activity_column delegates correctly."""
        unified_service.set_ui_components(ui_components)

        with patch.object(unified_service._file_service, "swap_activity_column", return_value=True):
            with patch.object(unified_service._file_service, "load_nonwear_data_for_plot"):
                result = unified_service.swap_activity_column("Vector Magnitude")

        assert result is True

    def test_swap_activity_column_without_ui_components(self, unified_service):
        """Test swap_activity_column handles missing UI components."""
        unified_service._ui_components = None

        result = unified_service.swap_activity_column("Vector Magnitude")

        assert result is False

    def test_set_view_mode_delegates(self, unified_service, ui_components):
        """Test set_view_mode delegates correctly."""
        unified_service.set_ui_components(ui_components)

        with patch.object(unified_service._cache_service, "clear_all_algorithm_caches"):
            with patch.object(unified_service._file_service, "set_view_mode"):
                with patch.object(unified_service._file_service, "load_nonwear_data_for_plot"):
                    unified_service.set_view_mode(24)

        unified_service._cache_service.clear_all_algorithm_caches.assert_called_once()

    def test_filter_to_24h_view_delegates(self, unified_service):
        """Test filter_to_24h_view delegates to file service."""
        timestamps = [datetime(2024, 1, 10, i, 0) for i in range(48)]
        activity_data = [100] * 48
        target_date = datetime(2024, 1, 10)

        unified_service._file_service.filter_to_24h_view = MagicMock(return_value=(timestamps[:24], activity_data[:24]))

        result = unified_service.filter_to_24h_view(timestamps, activity_data, target_date)

        assert len(result[0]) == 24
        assert len(result[1]) == 24

    # === Cache Management Tests ===

    def test_invalidate_marker_status_cache_delegates(self, unified_service):
        """Test invalidate_marker_status_cache delegates correctly."""
        with patch.object(unified_service._cache_service, "invalidate_marker_status_cache"):
            unified_service.invalidate_marker_status_cache("test.csv")

        unified_service._cache_service.invalidate_marker_status_cache.assert_called_once_with("test.csv")

    def test_invalidate_date_ranges_cache_delegates(self, unified_service):
        """Test invalidate_date_ranges_cache delegates correctly."""
        with patch.object(unified_service._cache_service, "invalidate_date_ranges_cache"):
            unified_service.invalidate_date_ranges_cache()

        unified_service._cache_service.invalidate_date_ranges_cache.assert_called_once()

    def test_invalidate_main_data_cache_delegates(self, unified_service):
        """Test invalidate_main_data_cache delegates correctly."""
        with patch.object(unified_service._cache_service, "invalidate_main_data_cache"):
            unified_service.invalidate_main_data_cache()

        unified_service._cache_service.invalidate_main_data_cache.assert_called_once()

    def test_clear_file_cache_delegates(self, unified_service):
        """Test clear_file_cache delegates correctly."""
        with patch.object(unified_service._cache_service, "clear_file_cache"):
            unified_service.clear_file_cache("test.csv")

        unified_service._cache_service.clear_file_cache.assert_called_once_with("test.csv")

    def test_clear_diary_cache_delegates(self, unified_service):
        """Test clear_diary_cache delegates correctly."""
        with patch.object(unified_service._cache_service, "clear_diary_cache"):
            unified_service.clear_diary_cache()

        unified_service._cache_service.clear_diary_cache.assert_called_once()

    # === Diary Data Management Tests ===

    @patch("sleep_scoring_app.services.unified_data_service.extract_participant_info")
    def test_load_diary_data_for_current_file_success(self, mock_extract, unified_service, ui_components):
        """Test successful diary data loading."""
        unified_service.set_ui_components(ui_components)

        mock_participant = MagicMock()
        mock_participant.numerical_id = "1000"
        mock_participant.full_id = "P1-1000-A"
        mock_extract.return_value = mock_participant

        mock_diary_data = [{"date": "2024-01-10", "bedtime": "22:00"}]
        unified_service._diary_service.get_diary_data_for_participant = MagicMock(return_value=mock_diary_data)

        result = unified_service.load_diary_data_for_current_file()

        assert result == mock_diary_data

    def test_load_diary_data_for_current_file_no_ui_components(self, unified_service):
        """Test diary data loading without UI components."""
        unified_service._ui_components = None

        result = unified_service.load_diary_data_for_current_file()

        assert result == []

    def test_load_diary_data_for_current_file_no_selected_file(self, unified_service, ui_components):
        """Test diary data loading without selected file."""
        ui_components["selected_file"] = None
        unified_service.set_ui_components(ui_components)

        result = unified_service.load_diary_data_for_current_file()

        assert result == []

    @patch("sleep_scoring_app.services.unified_data_service.extract_participant_info")
    def test_load_diary_data_uses_cache(self, mock_extract, unified_service, ui_components):
        """Test that diary data loading uses cache."""
        unified_service.set_ui_components(ui_components)

        mock_participant = MagicMock()
        mock_participant.numerical_id = "1000"
        mock_participant.full_id = "P1-1000-A"
        mock_extract.return_value = mock_participant

        cached_data = [{"date": "2024-01-10", "bedtime": "22:00"}]
        unified_service.diary_data_cache.get = MagicMock(return_value=cached_data)

        result = unified_service.load_diary_data_for_current_file()

        assert result == cached_data
        # Should not call service if cache hit
        unified_service._diary_service.get_diary_data_for_participant.assert_not_called()

    @patch("sleep_scoring_app.services.unified_data_service.extract_participant_info")
    def test_get_diary_data_for_date_success(self, mock_extract, unified_service, ui_components):
        """Test getting diary data for specific date."""
        unified_service.set_ui_components(ui_components)

        mock_participant = MagicMock()
        mock_participant.numerical_id = "1000"
        mock_participant.full_id = "P1-1000-A"
        mock_extract.return_value = mock_participant

        mock_diary_entry = MagicMock()
        mock_diary_entry.participant_id = "P1-1000-A"
        mock_diary_entry.diary_date = "2024-01-10"
        mock_diary_entry.bedtime = "22:00"
        mock_diary_entry.wake_time = "07:00"
        mock_diary_entry.sleep_onset_time = "22:30"
        mock_diary_entry.sleep_offset_time = "06:30"
        mock_diary_entry.in_bed_time = "22:00"
        mock_diary_entry.sleep_quality = 4
        mock_diary_entry.nap_occurred = False
        mock_diary_entry.nap_onset_time = None
        mock_diary_entry.nap_offset_time = None
        mock_diary_entry.nonwear_occurred = False
        mock_diary_entry.nonwear_reason = None
        mock_diary_entry.diary_notes = None

        unified_service._diary_service.get_diary_data_for_date = MagicMock(return_value=mock_diary_entry)

        result = unified_service.get_diary_data_for_date(datetime(2024, 1, 10))

        assert result is not None
        assert result["participant_id"] == "P1-1000-A"
        assert result["bedtime"] == "22:00"

    def test_get_diary_data_for_date_no_data(self, unified_service, ui_components):
        """Test getting diary data when no data exists."""
        unified_service.set_ui_components(ui_components)

        with patch("sleep_scoring_app.services.unified_data_service.extract_participant_info"):
            unified_service._diary_service.get_diary_data_for_date = MagicMock(return_value=None)

            result = unified_service.get_diary_data_for_date(datetime(2024, 1, 10))

        assert result is None

    @patch("sleep_scoring_app.services.unified_data_service.extract_participant_info")
    def test_check_current_participant_has_diary_data(self, mock_extract, unified_service, ui_components):
        """Test checking if participant has diary data."""
        unified_service.set_ui_components(ui_components)

        mock_participant = MagicMock()
        mock_participant.numerical_id = "1000"
        mock_participant.full_id = "P1-1000-A"
        mock_extract.return_value = mock_participant

        unified_service._diary_service.check_participant_has_diary_data = MagicMock(return_value=True)

        result = unified_service.check_current_participant_has_diary_data()

        assert result is True

    def test_get_diary_stats_delegates(self, unified_service):
        """Test get_diary_stats delegates to diary service."""
        expected_stats = {
            "total_entries": 10,
            "unique_participants": 5,
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-01-10",
        }
        unified_service._diary_service.get_diary_stats = MagicMock(return_value=expected_stats)

        result = unified_service.get_diary_stats()

        assert result == expected_stats

    # === ActiLife Integration Stubs Tests ===

    def test_get_sadeh_data_source_stub(self, unified_service):
        """Test ActiLife Sadeh data source stub."""
        from sleep_scoring_app.core.constants import SadehDataSource

        result = unified_service.get_sadeh_data_source("1000")

        assert result == SadehDataSource.CALCULATED

    def test_has_actilife_sadeh_data_stub(self, unified_service):
        """Test ActiLife Sadeh data check stub."""
        result = unified_service.has_actilife_sadeh_data("1000")

        assert result is False

    def test_validate_actilife_against_calculated_stub(self, unified_service):
        """Test ActiLife validation stub."""
        result = unified_service.validate_actilife_against_calculated("1000")

        assert result["status"] == "error"

    def test_config_manager_stub(self, unified_service):
        """Test config_manager stub property."""
        result = unified_service.config_manager

        assert result is None


class TestUnifiedDataServiceFileTableMethods:
    """Tests for file table specific methods."""

    @pytest.fixture
    def service(self, mock_db_manager):
        """Create service instance."""
        return UnifiedDataService(db_manager=mock_db_manager)

    def test_update_file_table_indicators_only(self, service):
        """Test updating file table indicators."""
        with patch.object(service._file_listing_service, "update_file_table_indicators_only"):
            service.update_file_table_indicators_only()

        service._file_listing_service.update_file_table_indicators_only.assert_called_once()

    def test_handle_markers_saved(self, service):
        """Test handling markers saved event."""
        with patch.object(service._file_listing_service, "handle_markers_saved"):
            service.handle_markers_saved("test.csv")

        service._file_listing_service.handle_markers_saved.assert_called_once_with("test.csv")

    def test_restore_file_selection(self, service):
        """Test restoring file selection."""
        with patch.object(service._file_listing_service, "restore_file_selection"):
            service.restore_file_selection("test.csv", 0)

        service._file_listing_service.restore_file_selection.assert_called_once_with("test.csv", 0)
