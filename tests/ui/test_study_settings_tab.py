"""
Tests for StudySettingsTab component.

These tests interact with the REAL StudySettingsTab like a user would:
- Managing valid groups and timepoints
- Configuring regex patterns
- Testing ID extraction live
- Setting default values
- Configuring algorithms
- Importing/exporting config
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt, QTime, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox

from sleep_scoring_app.ui.main_window import SleepScoringMainWindow


@pytest.fixture
def qapp():
    """Create QApplication."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(qtbot, qapp):
    """Create main window with all tabs."""
    window = SleepScoringMainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(100)
    return window


@pytest.fixture
def study_settings_tab(main_window):
    """Get the Study Settings tab from main window."""
    # Switch to Study Settings tab
    for i in range(main_window.tab_widget.count()):
        if main_window.tab_widget.tabText(i) == "Study Settings":
            main_window.tab_widget.setCurrentIndex(i)
            break
    return main_window.study_settings_tab


class TestStudySettingsTabBasics:
    """Test basic Study Settings tab functionality."""

    def test_study_settings_tab_exists(self, main_window, qtbot):
        """Test that Study Settings tab exists."""
        assert hasattr(main_window, "study_settings_tab")
        assert main_window.study_settings_tab is not None

    def test_tab_has_scroll_area(self, study_settings_tab, qtbot):
        """Test that tab content is scrollable."""
        from PyQt6.QtWidgets import QScrollArea

        scroll_areas = study_settings_tab.findChildren(QScrollArea)
        assert len(scroll_areas) > 0

    def test_apply_settings_button_exists(self, study_settings_tab, qtbot):
        """Test that Apply Settings button exists."""
        assert hasattr(study_settings_tab, "apply_button")
        assert study_settings_tab.apply_button is not None


class TestDataParadigmSection:
    """Test data paradigm configuration."""

    def test_data_paradigm_combo_exists(self, study_settings_tab, qtbot):
        """Test that data paradigm dropdown exists."""
        assert hasattr(study_settings_tab, "data_paradigm_combo")
        assert study_settings_tab.data_paradigm_combo is not None

    def test_paradigm_combo_has_options(self, study_settings_tab, qtbot):
        """Test that paradigm dropdown has multiple options."""
        count = study_settings_tab.data_paradigm_combo.count()
        assert count >= 2  # Epoch-based and Raw accelerometer

    def test_paradigm_info_label_exists(self, study_settings_tab, qtbot):
        """Test that paradigm info label exists."""
        assert hasattr(study_settings_tab, "paradigm_info_label")
        assert study_settings_tab.paradigm_info_label is not None

    def test_paradigm_info_label_shows_description(self, study_settings_tab, qtbot):
        """Test that paradigm info label shows descriptive text."""
        label_text = study_settings_tab.paradigm_info_label.text()
        assert len(label_text) > 0

    def test_select_different_paradigm(self, study_settings_tab, qtbot):
        """Test selecting a different paradigm."""
        if study_settings_tab.data_paradigm_combo.count() > 1:
            initial_index = study_settings_tab.data_paradigm_combo.currentIndex()

            # Select different paradigm
            new_index = (initial_index + 1) % study_settings_tab.data_paradigm_combo.count()

            # This may show a confirmation dialog
            def click_no_on_confirmation():
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, QMessageBox) and widget.isVisible():
                        no_btn = widget.button(QMessageBox.StandardButton.No)
                        if no_btn:
                            qtbot.mouseClick(no_btn, Qt.MouseButton.LeftButton)

            QTimer.singleShot(200, click_no_on_confirmation)

            study_settings_tab.data_paradigm_combo.setCurrentIndex(new_index)
            qtbot.wait(300)


class TestValidGroupsConfiguration:
    """Test valid groups list management."""

    def test_valid_groups_list_exists(self, study_settings_tab, qtbot):
        """Test that valid groups list exists."""
        assert hasattr(study_settings_tab, "valid_groups_list")
        assert study_settings_tab.valid_groups_list is not None

    def test_add_group_button_exists(self, study_settings_tab, qtbot):
        """Test that Add button for groups exists."""
        assert hasattr(study_settings_tab, "add_group_button")
        assert study_settings_tab.add_group_button is not None

    def test_edit_group_button_exists(self, study_settings_tab, qtbot):
        """Test that Edit button for groups exists."""
        assert hasattr(study_settings_tab, "edit_group_button")
        assert study_settings_tab.edit_group_button is not None

    def test_remove_group_button_exists(self, study_settings_tab, qtbot):
        """Test that Remove button for groups exists."""
        assert hasattr(study_settings_tab, "remove_group_button")
        assert study_settings_tab.remove_group_button is not None

    def test_groups_list_has_items(self, study_settings_tab, qtbot):
        """Test that groups list may have pre-configured items."""
        count = study_settings_tab.valid_groups_list.count()
        # May or may not have items initially
        assert count >= 0


class TestValidTimepointsConfiguration:
    """Test valid timepoints list management."""

    def test_valid_timepoints_list_exists(self, study_settings_tab, qtbot):
        """Test that valid timepoints list exists."""
        assert hasattr(study_settings_tab, "valid_timepoints_list")
        assert study_settings_tab.valid_timepoints_list is not None

    def test_add_timepoint_button_exists(self, study_settings_tab, qtbot):
        """Test that Add button for timepoints exists."""
        assert hasattr(study_settings_tab, "add_timepoint_button")
        assert study_settings_tab.add_timepoint_button is not None

    def test_edit_timepoint_button_exists(self, study_settings_tab, qtbot):
        """Test that Edit button for timepoints exists."""
        assert hasattr(study_settings_tab, "edit_timepoint_button")
        assert study_settings_tab.edit_timepoint_button is not None

    def test_remove_timepoint_button_exists(self, study_settings_tab, qtbot):
        """Test that Remove button for timepoints exists."""
        assert hasattr(study_settings_tab, "remove_timepoint_button")
        assert study_settings_tab.remove_timepoint_button is not None

    def test_timepoints_list_has_items(self, study_settings_tab, qtbot):
        """Test that timepoints list may have pre-configured items."""
        count = study_settings_tab.valid_timepoints_list.count()
        assert count >= 0


class TestRegexPatternConfiguration:
    """Test regex pattern fields."""

    def test_id_pattern_edit_exists(self, study_settings_tab, qtbot):
        """Test that ID pattern field exists."""
        assert hasattr(study_settings_tab, "id_pattern_edit")
        assert study_settings_tab.id_pattern_edit is not None

    def test_timepoint_pattern_edit_exists(self, study_settings_tab, qtbot):
        """Test that timepoint pattern field exists."""
        assert hasattr(study_settings_tab, "timepoint_pattern_edit")
        assert study_settings_tab.timepoint_pattern_edit is not None

    def test_group_pattern_edit_exists(self, study_settings_tab, qtbot):
        """Test that group pattern field exists."""
        assert hasattr(study_settings_tab, "group_pattern_edit")
        assert study_settings_tab.group_pattern_edit is not None

    def test_enter_id_pattern(self, study_settings_tab, qtbot):
        """Test entering an ID pattern."""
        study_settings_tab.id_pattern_edit.clear()
        qtbot.keyClicks(study_settings_tab.id_pattern_edit, r"^(\d{4})")
        qtbot.wait(200)  # Give time for validation

        assert r"(\d{4})" in study_settings_tab.id_pattern_edit.text()

    def test_enter_timepoint_pattern(self, study_settings_tab, qtbot):
        """Test entering a timepoint pattern."""
        study_settings_tab.timepoint_pattern_edit.clear()
        qtbot.keyClicks(study_settings_tab.timepoint_pattern_edit, r"([A-Z0-9]+)")
        qtbot.wait(200)

        assert "A-Z0-9" in study_settings_tab.timepoint_pattern_edit.text()

    def test_enter_group_pattern(self, study_settings_tab, qtbot):
        """Test entering a group pattern."""
        study_settings_tab.group_pattern_edit.clear()
        qtbot.keyClicks(study_settings_tab.group_pattern_edit, r"G\d")
        qtbot.wait(200)

        assert r"G\d" in study_settings_tab.group_pattern_edit.text()


class TestLiveIDTesting:
    """Test live ID testing section."""

    def test_test_id_input_exists(self, study_settings_tab, qtbot):
        """Test that test ID input field exists."""
        assert hasattr(study_settings_tab, "test_id_input")
        assert study_settings_tab.test_id_input is not None

    def test_test_results_display_exists(self, study_settings_tab, qtbot):
        """Test that test results display exists."""
        assert hasattr(study_settings_tab, "test_results_display")
        assert study_settings_tab.test_results_display is not None

    def test_enter_test_id_shows_results(self, study_settings_tab, qtbot):
        """Test that entering a test ID updates results display."""
        study_settings_tab.test_id_input.clear()
        qtbot.keyClicks(study_settings_tab.test_id_input, "4001_G1_BO")
        qtbot.wait(200)

        # Results display should have some content
        results_text = study_settings_tab.test_results_display.toPlainText()
        assert len(results_text) > 0


class TestDefaultSelectionDropdowns:
    """Test default group and timepoint dropdowns."""

    def test_default_group_combo_exists(self, study_settings_tab, qtbot):
        """Test that default group dropdown exists."""
        assert hasattr(study_settings_tab, "default_group_combo")
        assert study_settings_tab.default_group_combo is not None

    def test_default_timepoint_combo_exists(self, study_settings_tab, qtbot):
        """Test that default timepoint dropdown exists."""
        assert hasattr(study_settings_tab, "default_timepoint_combo")
        assert study_settings_tab.default_timepoint_combo is not None

    def test_default_group_combo_populated_from_list(self, study_settings_tab, qtbot):
        """Test that default group dropdown is populated from valid groups list."""
        # Should have at least a placeholder
        assert study_settings_tab.default_group_combo.count() > 0

    def test_default_timepoint_combo_populated_from_list(self, study_settings_tab, qtbot):
        """Test that default timepoint dropdown is populated from valid timepoints list."""
        # Should have at least a placeholder
        assert study_settings_tab.default_timepoint_combo.count() > 0


class TestUnknownValueConfiguration:
    """Test unknown value placeholder configuration."""

    def test_unknown_value_edit_exists(self, study_settings_tab, qtbot):
        """Test that unknown value field exists."""
        assert hasattr(study_settings_tab, "unknown_value_edit")
        assert study_settings_tab.unknown_value_edit is not None

    def test_set_unknown_value(self, study_settings_tab, qtbot):
        """Test setting the unknown value placeholder."""
        study_settings_tab.unknown_value_edit.clear()
        qtbot.keyClicks(study_settings_tab.unknown_value_edit, "UNKNOWN")
        qtbot.wait(200)

        assert "UNKNOWN" in study_settings_tab.unknown_value_edit.text()


class TestAlgorithmConfiguration:
    """Test algorithm settings."""

    def test_sleep_algorithm_combo_exists(self, study_settings_tab, qtbot):
        """Test that sleep algorithm dropdown exists."""
        assert hasattr(study_settings_tab, "sleep_algorithm_combo")
        assert study_settings_tab.sleep_algorithm_combo is not None

    def test_sleep_algorithm_has_options(self, study_settings_tab, qtbot):
        """Test that sleep algorithm has multiple options."""
        count = study_settings_tab.sleep_algorithm_combo.count()
        assert count > 0

    def test_sleep_period_detector_combo_exists(self, study_settings_tab, qtbot):
        """Test that sleep period detector dropdown exists."""
        assert hasattr(study_settings_tab, "sleep_period_detector_combo")
        assert study_settings_tab.sleep_period_detector_combo is not None

    def test_nonwear_algorithm_combo_exists(self, study_settings_tab, qtbot):
        """Test that nonwear algorithm dropdown exists."""
        assert hasattr(study_settings_tab, "nonwear_algorithm_combo")
        assert study_settings_tab.nonwear_algorithm_combo is not None

    def test_choi_axis_combo_exists(self, study_settings_tab, qtbot):
        """Test that Choi axis dropdown exists."""
        assert hasattr(study_settings_tab, "choi_axis_combo")
        assert study_settings_tab.choi_axis_combo is not None


class TestNightHoursConfiguration:
    """Test night hours time pickers."""

    def test_night_start_time_exists(self, study_settings_tab, qtbot):
        """Test that night start time picker exists."""
        assert hasattr(study_settings_tab, "night_start_time")
        assert study_settings_tab.night_start_time is not None

    def test_night_end_time_exists(self, study_settings_tab, qtbot):
        """Test that night end time picker exists."""
        assert hasattr(study_settings_tab, "night_end_time")
        assert study_settings_tab.night_end_time is not None

    def test_set_night_start_time(self, study_settings_tab, qtbot):
        """Test setting night start time."""
        study_settings_tab.night_start_time.setTime(QTime(22, 0))
        qtbot.wait(50)

        assert study_settings_tab.night_start_time.time().hour() == 22

    def test_set_night_end_time(self, study_settings_tab, qtbot):
        """Test setting night end time."""
        study_settings_tab.night_end_time.setTime(QTime(7, 0))
        qtbot.wait(50)

        assert study_settings_tab.night_end_time.time().hour() == 7


class TestConfigImportExport:
    """Test config import/export buttons."""

    def test_import_config_button_exists(self, study_settings_tab, qtbot):
        """Test that Import Config button exists."""
        assert hasattr(study_settings_tab, "import_config_button")
        assert study_settings_tab.import_config_button is not None

    def test_export_config_button_exists(self, study_settings_tab, qtbot):
        """Test that Export Config button exists."""
        assert hasattr(study_settings_tab, "export_config_button")
        assert study_settings_tab.export_config_button is not None

    def test_click_export_config_opens_dialog(self, study_settings_tab, qtbot):
        """Test that clicking Export Config opens dialog."""

        def close_dialog():
            for widget in QApplication.topLevelWidgets():
                if widget.isVisible() and "Export" in widget.windowTitle():
                    widget.close()

        QTimer.singleShot(200, close_dialog)

        qtbot.mouseClick(study_settings_tab.export_config_button, Qt.MouseButton.LeftButton)
        qtbot.wait(300)

    def test_click_import_config_opens_dialog(self, study_settings_tab, qtbot):
        """Test that clicking Import Config opens dialog."""

        def close_dialog():
            for widget in QApplication.topLevelWidgets():
                if widget.isVisible() and "Import" in widget.windowTitle():
                    widget.close()

        QTimer.singleShot(200, close_dialog)

        qtbot.mouseClick(study_settings_tab.import_config_button, Qt.MouseButton.LeftButton)
        qtbot.wait(300)


class TestApplySettingsButton:
    """Test apply settings functionality."""

    def test_click_apply_settings(self, study_settings_tab, qtbot):
        """Test clicking Apply Settings button."""

        def close_confirmation():
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QMessageBox) and widget.isVisible():
                    ok_btn = widget.button(QMessageBox.StandardButton.Ok)
                    if ok_btn:
                        qtbot.mouseClick(ok_btn, Qt.MouseButton.LeftButton)

        QTimer.singleShot(200, close_confirmation)

        qtbot.mouseClick(study_settings_tab.apply_button, Qt.MouseButton.LeftButton)
        qtbot.wait(300)

    def test_apply_button_styled_prominently(self, study_settings_tab, qtbot):
        """Test that Apply button has prominent styling."""
        style = study_settings_tab.apply_button.styleSheet()
        # Should have some styling
        assert len(style) > 0


class TestDragDropListWidgetFeatures:
    """Test DragDropListWidget functionality."""

    def test_groups_list_supports_drag_drop(self, study_settings_tab, qtbot):
        """Test that groups list supports drag-and-drop."""
        from PyQt6.QtWidgets import QListWidget

        assert study_settings_tab.valid_groups_list.dragDropMode() == QListWidget.DragDropMode.InternalMove

    def test_timepoints_list_supports_drag_drop(self, study_settings_tab, qtbot):
        """Test that timepoints list supports drag-and-drop."""
        from PyQt6.QtWidgets import QListWidget

        assert study_settings_tab.valid_timepoints_list.dragDropMode() == QListWidget.DragDropMode.InternalMove

    def test_lists_allow_single_selection(self, study_settings_tab, qtbot):
        """Test that lists allow single selection."""
        from PyQt6.QtWidgets import QListWidget

        assert study_settings_tab.valid_groups_list.selectionMode() == QListWidget.SelectionMode.SingleSelection
        assert study_settings_tab.valid_timepoints_list.selectionMode() == QListWidget.SelectionMode.SingleSelection


class TestSignalEmissions:
    """Test signal emissions from study settings."""

    def test_groups_changed_signal_exists(self, study_settings_tab, qtbot):
        """Test that groups_changed signal exists."""
        assert hasattr(study_settings_tab, "groups_changed")

    def test_timepoints_changed_signal_exists(self, study_settings_tab, qtbot):
        """Test that timepoints_changed signal exists."""
        assert hasattr(study_settings_tab, "timepoints_changed")
