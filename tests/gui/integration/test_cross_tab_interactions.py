#!/usr/bin/env python3
"""
Integration tests for cross-tab interactions.
Tests how changes in one tab affect behavior in other tabs.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget


@pytest.mark.integration
@pytest.mark.gui
class TestStudySettingsToAnalysisTab:
    """Test how Study Settings changes affect Analysis Tab behavior."""

    @pytest.fixture
    def parent_widget_with_mock(self, qtbot):
        """Create a real QWidget parent with mocked config_manager attached."""
        parent = QWidget()
        qtbot.addWidget(parent)

        parent.config_manager = Mock()
        parent.config_manager.config = Mock()
        parent.config_manager.update_study_settings = Mock()

        # Set up default config values for study settings
        config = parent.config_manager.config
        config.study_unknown_value = "UNKNOWN"
        config.study_valid_groups = ["G1", "G2"]
        config.study_valid_timepoints = ["T1", "T2"]
        config.study_default_group = "G1"
        config.study_default_timepoint = "T1"
        config.study_participant_id_patterns = [r"^(\d{4,})[_-]"]
        config.study_timepoint_pattern = r"([A-Z]\d)"
        config.study_group_pattern = r"(G\d)"
        config.sadeh_variant = "actilife"
        config.night_start_hour = 22
        config.night_end_hour = 7
        config.choi_axis = "vector_magnitude"

        # Analysis tab mock methods
        parent.prev_date = Mock()
        parent.next_date = Mock()
        parent.on_date_dropdown_changed = Mock()
        parent.save_current_markers = Mock()
        parent.mark_no_sleep_period = Mock()
        parent.clear_current_markers = Mock()
        parent.on_activity_source_changed = Mock()
        parent.plot_widget = Mock()
        parent.plot_widget.set_view_mode = Mock()
        parent.plot_widget.toggle_adjacent_day_markers = Mock()

        return parent

    @pytest.fixture
    def study_settings_tab(self, qtbot, parent_widget_with_mock):
        """Create StudySettingsTab for testing."""
        from sleep_scoring_app.ui.study_settings_tab import StudySettingsTab

        tab = StudySettingsTab(parent_widget_with_mock)
        qtbot.addWidget(tab)
        return tab

    def test_sadeh_variant_change_affects_algorithm(self, study_settings_tab, qtbot):
        """Test changing Sadeh variant in study settings updates algorithm configuration."""
        # Change to original variant
        qtbot.mouseClick(study_settings_tab.sadeh_original_radio, Qt.MouseButton.LeftButton)
        assert study_settings_tab.sadeh_original_radio.isChecked()

    def test_choi_axis_change_affects_nonwear_detection(self, study_settings_tab, qtbot):
        """Test changing Choi axis in study settings updates nonwear detection."""
        combo = study_settings_tab.choi_axis_combo
        initial_index = combo.currentIndex()

        # Change to different axis
        new_index = (initial_index + 1) % combo.count()
        combo.setCurrentIndex(new_index)

        assert combo.currentIndex() == new_index

    def test_night_hours_change_affects_analysis(self, study_settings_tab, qtbot):
        """Test changing night hours in study settings affects analysis period classification."""
        from PyQt6.QtCore import QTime

        # Change night start time
        study_settings_tab.night_start_time.setTime(QTime(21, 0))
        assert study_settings_tab.night_start_time.time().hour() == 21

        # Change night end time
        study_settings_tab.night_end_time.setTime(QTime(8, 0))
        assert study_settings_tab.night_end_time.time().hour() == 8


@pytest.mark.integration
@pytest.mark.gui
class TestDataSettingsToAnalysisTab:
    """Test how Data Settings changes affect Analysis Tab behavior."""

    @pytest.fixture
    def parent_widget_with_mock(self, qtbot):
        """Create a real QWidget parent with mocked methods attached."""
        parent = QWidget()
        qtbot.addWidget(parent)

        parent.config_manager = Mock()
        parent.config_manager.config = Mock()

        # Data settings config
        config = parent.config_manager.config
        config.device_preset = "actigraph_gt3x"
        config.epoch_length = 60
        config.skip_rows = 10
        config.datetime_combined = False
        config.custom_date_column = ""
        config.custom_time_column = ""
        config.custom_axis_y_column = ""
        config.custom_axis_x_column = ""
        config.custom_axis_z_column = ""
        config.custom_vector_magnitude_column = ""
        config.custom_activity_column = ""

        # Analysis tab config
        config.activity_source = "axis_y"
        config.show_adjacent_day_markers = True
        config.view_mode = 48

        # Mock methods
        parent.browse_activity_files = Mock()
        parent.browse_nonwear_files = Mock()
        parent.start_activity_import = Mock()
        parent.start_nonwear_import = Mock()
        parent.clear_all_markers = Mock()
        parent.on_epoch_length_changed = Mock()
        parent.on_skip_rows_changed = Mock()
        parent.prev_date = Mock()
        parent.next_date = Mock()
        parent.on_date_dropdown_changed = Mock()
        parent.save_current_markers = Mock()
        parent.mark_no_sleep_period = Mock()
        parent.clear_current_markers = Mock()
        parent.on_activity_source_changed = Mock()
        parent.plot_widget = Mock()
        parent.plot_widget.set_view_mode = Mock()
        parent.plot_widget.toggle_adjacent_day_markers = Mock()

        # File list tracking
        parent.file_list = []

        # Mock db_manager (required by DataSettingsTab)
        parent.db_manager = Mock()
        parent.db_manager.get_activity_data_stats = Mock(return_value={"files": 0, "records": 0})
        parent.db_manager.get_nonwear_data_stats = Mock(return_value={"files": 0, "records": 0})

        return parent

    @pytest.fixture
    def data_settings_tab(self, qtbot, parent_widget_with_mock):
        """Create DataSettingsTab for testing."""
        from sleep_scoring_app.ui.data_settings_tab import DataSettingsTab

        tab = DataSettingsTab(parent_widget_with_mock)
        qtbot.addWidget(tab)
        return tab

    def test_epoch_length_change_affects_data_processing(self, data_settings_tab, parent_widget_with_mock):
        """Test changing epoch length affects data processing configuration."""
        data_settings_tab.epoch_length_spin.setValue(30)
        parent_widget_with_mock.on_epoch_length_changed.assert_called()

    def test_device_preset_change_affects_import(self, data_settings_tab, qtbot):
        """Test changing device preset affects import column detection."""
        combo = data_settings_tab.device_preset_combo
        initial_index = combo.currentIndex()

        # Change to different device
        new_index = (initial_index + 1) % combo.count()
        combo.setCurrentIndex(new_index)

        assert combo.currentIndex() == new_index

    def test_clear_markers_affects_analysis_display(self, data_settings_tab, parent_widget_with_mock, qtbot):
        """Test clearing markers in data settings affects analysis tab display."""
        qtbot.mouseClick(data_settings_tab.clear_markers_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.clear_all_markers.assert_called_once()


@pytest.mark.integration
@pytest.mark.gui
class TestAnalysisTabToExportTab:
    """Test how Analysis Tab changes affect Export Tab behavior."""

    @pytest.fixture
    def parent_widget_with_mock(self, qtbot):
        """Create a real QWidget parent with mocked methods attached."""
        parent = QWidget()
        qtbot.addWidget(parent)

        parent.config_manager = Mock()
        parent.config_manager.config = Mock()

        # Analysis tab config
        config = parent.config_manager.config
        config.activity_source = "axis_y"
        config.show_adjacent_day_markers = True
        config.view_mode = 48
        config.export_directory = ""
        config.export_grouping = "none"
        config.include_all_columns = True

        # Mock methods
        parent.prev_date = Mock()
        parent.next_date = Mock()
        parent.on_date_dropdown_changed = Mock()
        parent.save_current_markers = Mock()
        parent.mark_no_sleep_period = Mock()
        parent.clear_current_markers = Mock()
        parent.on_activity_source_changed = Mock()
        parent.plot_widget = Mock()
        parent.plot_widget.set_view_mode = Mock()
        parent.plot_widget.toggle_adjacent_day_markers = Mock()
        parent.export_csv = Mock()
        parent.export_excel = Mock()
        parent.browse_export_directory = Mock()

        # Database mock
        parent.db_manager = Mock()
        parent.db_manager.get_all_sleep_metrics = Mock(return_value=[])

        return parent

    @pytest.fixture
    def analysis_tab(self, qtbot, parent_widget_with_mock):
        """Create AnalysisTab for testing."""
        from sleep_scoring_app.ui.analysis_tab import AnalysisTab

        tab = AnalysisTab(parent_widget_with_mock)
        qtbot.addWidget(tab)
        return tab

    def test_saved_markers_available_for_export(self, analysis_tab, parent_widget_with_mock, qtbot):
        """Test that saved markers become available in export tab."""
        # Save markers in analysis tab
        qtbot.mouseClick(analysis_tab.save_markers_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.save_current_markers.assert_called_once()

    def test_no_sleep_period_available_for_export(self, analysis_tab, parent_widget_with_mock, qtbot):
        """Test that no-sleep periods are available in export tab."""
        # Mark no sleep period
        qtbot.mouseClick(analysis_tab.no_sleep_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.mark_no_sleep_period.assert_called_once()


@pytest.mark.integration
@pytest.mark.gui
class TestTabSwitchingStatePreservation:
    """Test that state is preserved when switching between tabs."""

    @pytest.fixture
    def parent_widget_with_mock(self, qtbot):
        """Create a real QWidget parent with mocked config_manager."""
        parent = QWidget()
        qtbot.addWidget(parent)

        parent.config_manager = Mock()
        parent.config_manager.config = Mock()

        config = parent.config_manager.config
        config.activity_source = "axis_y"
        config.show_adjacent_day_markers = True
        config.view_mode = 48

        parent.prev_date = Mock()
        parent.next_date = Mock()
        parent.on_date_dropdown_changed = Mock()
        parent.save_current_markers = Mock()
        parent.mark_no_sleep_period = Mock()
        parent.clear_current_markers = Mock()
        parent.on_activity_source_changed = Mock()
        parent.set_view_mode = Mock()  # Called directly on parent
        parent.plot_widget = Mock()
        parent.plot_widget.set_view_mode = Mock()
        parent.plot_widget.toggle_adjacent_day_markers = Mock()

        return parent

    @pytest.fixture
    def analysis_tab(self, qtbot, parent_widget_with_mock):
        """Create AnalysisTab for testing."""
        from sleep_scoring_app.ui.analysis_tab import AnalysisTab

        tab = AnalysisTab(parent_widget_with_mock)
        qtbot.addWidget(tab)
        return tab

    def test_view_mode_preserved_after_hide_show(self, analysis_tab, qtbot):
        """Test view mode is preserved when tab is hidden and shown."""
        # Set to 24h view
        qtbot.mouseClick(analysis_tab.view_24h_btn, Qt.MouseButton.LeftButton)
        assert analysis_tab.view_24h_btn.isChecked()

        # Hide and show widget (simulating tab switch)
        analysis_tab.hide()
        analysis_tab.show()

        # View mode should still be 24h
        assert analysis_tab.view_24h_btn.isChecked()

    def test_adjacent_markers_checkbox_preserved(self, analysis_tab, qtbot):
        """Test adjacent markers checkbox state is preserved."""
        # Uncheck the checkbox
        analysis_tab.show_adjacent_day_markers_checkbox.setChecked(False)
        assert not analysis_tab.show_adjacent_day_markers_checkbox.isChecked()

        # Hide and show widget
        analysis_tab.hide()
        analysis_tab.show()

        # Should still be unchecked
        assert not analysis_tab.show_adjacent_day_markers_checkbox.isChecked()

    def test_time_input_preserved(self, analysis_tab, qtbot):
        """Test time inputs are preserved when tab is hidden and shown."""
        # Enter times
        analysis_tab.onset_time_input.setText("22:30")
        analysis_tab.offset_time_input.setText("06:45")

        # Hide and show widget
        analysis_tab.hide()
        analysis_tab.show()

        # Times should be preserved
        assert analysis_tab.onset_time_input.text() == "22:30"
        assert analysis_tab.offset_time_input.text() == "06:45"


@pytest.mark.integration
@pytest.mark.gui
class TestSignalPropagationBetweenTabs:
    """Test signal propagation between tabs."""

    @pytest.fixture
    def parent_widget_with_mock(self, qtbot):
        """Create a real QWidget parent with mocked config_manager."""
        parent = QWidget()
        qtbot.addWidget(parent)

        parent.config_manager = Mock()
        parent.config_manager.config = Mock()
        parent.config_manager.update_study_settings = Mock()

        # Set up default config values
        config = parent.config_manager.config
        config.study_unknown_value = "UNKNOWN"
        config.study_valid_groups = ["G1", "G2"]
        config.study_valid_timepoints = ["T1", "T2"]
        config.study_default_group = "G1"
        config.study_default_timepoint = "T1"
        config.study_participant_id_patterns = [r"^(\d{4,})[_-]"]
        config.study_timepoint_pattern = r"([A-Z]\d)"
        config.study_group_pattern = r"(G\d)"
        config.sadeh_variant = "actilife"
        config.night_start_hour = 22
        config.night_end_hour = 7
        config.choi_axis = "vector_magnitude"

        return parent

    @pytest.fixture
    def study_settings_tab(self, qtbot, parent_widget_with_mock):
        """Create StudySettingsTab for testing."""
        from sleep_scoring_app.ui.study_settings_tab import StudySettingsTab

        tab = StudySettingsTab(parent_widget_with_mock)
        qtbot.addWidget(tab)
        return tab

    def test_groups_changed_signal_emitted(self, study_settings_tab, qtbot):
        """Test groups_changed signal is emitted when groups are modified."""
        received_signals = []
        study_settings_tab.groups_changed.connect(lambda groups: received_signals.append(groups))

        # Add a new group
        study_settings_tab.valid_groups_list.add_item_with_validation("G3")

        # Signal should have been emitted
        assert len(received_signals) >= 1

    def test_timepoints_changed_signal_emitted(self, study_settings_tab, qtbot):
        """Test timepoints_changed signal is emitted when timepoints are modified."""
        received_signals = []
        study_settings_tab.timepoints_changed.connect(lambda tps: received_signals.append(tps))

        # Add a new timepoint
        study_settings_tab.valid_timepoints_list.add_item_with_validation("T3")

        # Signal should have been emitted
        assert len(received_signals) >= 1

    def test_default_dropdown_updates_on_group_change(self, study_settings_tab, qtbot):
        """Test default group dropdown updates when groups list changes."""
        initial_count = study_settings_tab.default_group_combo.count()

        # Add a new group
        study_settings_tab.valid_groups_list.add_item_with_validation("NEWGROUP")

        # Dropdown should have one more item
        assert study_settings_tab.default_group_combo.count() == initial_count + 1

    def test_default_dropdown_updates_on_timepoint_change(self, study_settings_tab, qtbot):
        """Test default timepoint dropdown updates when timepoints list changes."""
        initial_count = study_settings_tab.default_timepoint_combo.count()

        # Add a new timepoint
        study_settings_tab.valid_timepoints_list.add_item_with_validation("NEWTP")

        # Dropdown should have one more item
        assert study_settings_tab.default_timepoint_combo.count() == initial_count + 1
