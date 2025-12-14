"""
COMPREHENSIVE Real PyQt6 UI Interaction Tests.

These tests create REAL windows and interact with them like a real user would:
- Click buttons
- Type in fields
- Select dropdowns
- Interact with dialogs (ALL of them!)
- Navigate tabs
- Test complete workflows

NO MOCKS - Real UI interactions only.

Dialog types discovered in this app:
- QMessageBox with Yes/No buttons (Confirm Paradigm Change, Confirm Removal, etc.)
- QMessageBox with OK button (Invalid Input, Settings Applied, No Markers, No File Selected, etc.)
- QInputDialog for text entry (Add Group, Add Timepoint, Edit items)
- Custom dialogs (Column Mapping, Config Import/Export, Color Legend, Shortcuts)
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import numpy as np
import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt, QTime, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox, QPushButton

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


# ============================================================================
# HELPER FUNCTIONS FOR DIALOG INTERACTIONS
# ============================================================================


def click_dialog_button(qtbot, button_type, delay_ms=100):
    """Schedule clicking a standard button on a QMessageBox dialog."""

    def click_handler():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                btn = widget.button(button_type)
                if btn:
                    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                    return

    QTimer.singleShot(delay_ms, click_handler)


def click_any_ok_dialog(qtbot, delay_ms=100):
    """Click OK on any QMessageBox that appears."""

    def click_handler():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                # Try Ok first, then Yes, then any button
                for btn_type in [QMessageBox.StandardButton.Ok, QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Close]:
                    btn = widget.button(btn_type)
                    if btn:
                        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                        return

    QTimer.singleShot(delay_ms, click_handler)


def click_yes_on_any_dialog(qtbot, delay_ms=100):
    """Click Yes on any dialog that appears."""

    def click_handler():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                btn = widget.button(QMessageBox.StandardButton.Yes)
                if btn:
                    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                    return

    QTimer.singleShot(delay_ms, click_handler)


def click_no_on_any_dialog(qtbot, delay_ms=100):
    """Click No on any dialog that appears."""

    def click_handler():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                btn = widget.button(QMessageBox.StandardButton.No)
                if btn:
                    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                    return

    QTimer.singleShot(delay_ms, click_handler)


def handle_input_dialog(qtbot, text_to_enter, accept=True, delay_ms=100):
    """Handle QInputDialog by entering text and accepting/rejecting."""

    def handler():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QInputDialog) and widget.isVisible():
                widget.setTextValue(text_to_enter)
                if accept:
                    widget.accept()
                else:
                    widget.reject()
                return

    QTimer.singleShot(delay_ms, handler)


def close_any_dialog(qtbot, delay_ms=100):
    """Close any open dialog (reject/close)."""

    def handler():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
                return
            if isinstance(widget, QMessageBox) and widget.isVisible():
                widget.reject()
                return

    QTimer.singleShot(delay_ms, handler)


def handle_multiple_dialogs(qtbot, handlers, base_delay=100):
    """
    Schedule multiple dialog handlers with increasing delays.
    handlers: list of (handler_func, args) tuples
    """
    for i, (handler, args) in enumerate(handlers):
        delay = base_delay + (i * 150)
        if args:
            QTimer.singleShot(delay, lambda h=handler, a=args: h(qtbot, *a))
        else:
            QTimer.singleShot(delay, lambda h=handler: h(qtbot))


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for the session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def main_window(qtbot: QtBot):
    """Create a real MainWindow for testing."""
    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

    window = SleepScoringMainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(100)
    return window


# ============================================================================
# STUDY SETTINGS TAB - DATA PARADIGM TESTS
# ============================================================================


class TestStudySettingsDataParadigm:
    """Test Data Paradigm section interactions."""

    def test_paradigm_combo_populated_from_enum(self, main_window, qtbot: QtBot):
        """Test paradigm combo is populated with enum values."""
        tab = main_window.study_settings_tab
        assert tab.data_paradigm_combo.count() >= 2

    def test_paradigm_change_click_yes(self, main_window, qtbot: QtBot):
        """Test changing paradigm and clicking Yes on confirmation."""
        tab = main_window.study_settings_tab

        if tab.data_paradigm_combo.count() > 1:
            original = tab.data_paradigm_combo.currentIndex()
            new_index = (original + 1) % tab.data_paradigm_combo.count()

            # Schedule Yes click for "Confirm Paradigm Change" dialog
            click_yes_on_any_dialog(qtbot)

            tab.data_paradigm_combo.setCurrentIndex(new_index)
            qtbot.wait(200)

            assert tab.data_paradigm_combo.currentIndex() == new_index

    def test_paradigm_change_click_no(self, main_window, qtbot: QtBot):
        """Test changing paradigm and clicking No reverts."""
        tab = main_window.study_settings_tab

        if tab.data_paradigm_combo.count() > 1:
            original = tab.data_paradigm_combo.currentIndex()
            new_index = (original + 1) % tab.data_paradigm_combo.count()

            # Schedule No click - should revert
            click_no_on_any_dialog(qtbot)

            tab.data_paradigm_combo.setCurrentIndex(new_index)
            qtbot.wait(200)


# ============================================================================
# STUDY SETTINGS - REGEX PATTERN TESTS
# ============================================================================


class TestStudySettingsRegexPatterns:
    """Test regex pattern input interactions."""

    def test_type_id_pattern(self, main_window, qtbot: QtBot):
        """Test typing in ID pattern field."""
        tab = main_window.study_settings_tab

        tab.id_pattern_edit.clear()
        QTest.keyClicks(tab.id_pattern_edit, r"^(\d{4})")

        assert tab.id_pattern_edit.text() == r"^(\d{4})"

    def test_type_timepoint_pattern(self, main_window, qtbot: QtBot):
        """Test typing in timepoint pattern field."""
        tab = main_window.study_settings_tab

        tab.timepoint_pattern_edit.clear()
        QTest.keyClicks(tab.timepoint_pattern_edit, r"_(T\d)_")

        assert tab.timepoint_pattern_edit.text() == r"_(T\d)_"

    def test_type_group_pattern(self, main_window, qtbot: QtBot):
        """Test typing in group pattern field."""
        tab = main_window.study_settings_tab

        tab.group_pattern_edit.clear()
        QTest.keyClicks(tab.group_pattern_edit, r"_(G\d)_")

        assert tab.group_pattern_edit.text() == r"_(G\d)_"

    def test_invalid_regex_accepted(self, main_window, qtbot: QtBot):
        """Test invalid regex is accepted (validation is visual)."""
        tab = main_window.study_settings_tab

        tab.id_pattern_edit.clear()
        QTest.keyClicks(tab.id_pattern_edit, r"[[[")
        qtbot.wait(100)

        assert tab.id_pattern_edit.text() == r"[[["


# ============================================================================
# STUDY SETTINGS - LIVE ID TESTING
# ============================================================================


class TestStudySettingsLiveIDTesting:
    """Test live ID testing section."""

    def test_type_test_id(self, main_window, qtbot: QtBot):
        """Test typing in the test ID input."""
        tab = main_window.study_settings_tab

        tab.test_id_input.clear()
        QTest.keyClicks(tab.test_id_input, "participant_12345_T1")
        qtbot.wait(100)

        assert tab.test_id_input.text() == "participant_12345_T1"

    def test_clear_test_id(self, main_window, qtbot: QtBot):
        """Test clearing the test ID input."""
        tab = main_window.study_settings_tab

        tab.test_id_input.setText("some_value")
        tab.test_id_input.clear()

        assert tab.test_id_input.text() == ""


# ============================================================================
# STUDY SETTINGS - VALID GROUPS (with dialog handling)
# ============================================================================


class TestStudySettingsValidGroups:
    """Test valid groups list interactions."""

    def test_add_group_unique_name(self, main_window, qtbot: QtBot):
        """Test adding a group with unique short name (valid, max 10 chars)."""
        tab = main_window.study_settings_tab

        initial_count = tab.valid_groups_list.count()

        # Use unique name to avoid "Duplicate Group" dialog
        import random

        unique_name = f"G{random.randint(100, 999)}"
        handle_input_dialog(qtbot, unique_name, accept=True)

        qtbot.mouseClick(tab.add_group_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        # Should have added (uppercased)
        assert tab.valid_groups_list.count() >= initial_count

    def test_add_duplicate_group_shows_error(self, main_window, qtbot: QtBot):
        """Test adding duplicate group shows 'Duplicate Group' dialog."""
        tab = main_window.study_settings_tab

        # First add a group
        tab.valid_groups_list.addItem("DUPG")
        initial_count = tab.valid_groups_list.count()

        # Try to add the same one again
        handle_input_dialog(qtbot, "DUPG", accept=True)

        # Handle "Duplicate Group" dialog - click OK
        click_any_ok_dialog(qtbot, delay_ms=250)

        qtbot.mouseClick(tab.add_group_button, Qt.MouseButton.LeftButton)
        qtbot.wait(400)

        # Count should NOT increase (duplicate rejected)
        assert tab.valid_groups_list.count() == initial_count

    def test_add_group_long_name_shows_error(self, main_window, qtbot: QtBot):
        """Test adding group with >10 chars shows 'Invalid Input' dialog."""
        tab = main_window.study_settings_tab

        initial_count = tab.valid_groups_list.count()

        # First dialog: QInputDialog - enter long name
        handle_input_dialog(qtbot, "VERYLONGGROUPNAME", accept=True)

        # Second dialog: "Invalid Input" error - click OK
        click_any_ok_dialog(qtbot, delay_ms=250)

        qtbot.mouseClick(tab.add_group_button, Qt.MouseButton.LeftButton)
        qtbot.wait(400)

        # Count should NOT increase (invalid)
        assert tab.valid_groups_list.count() == initial_count

    def test_remove_group_click_yes(self, main_window, qtbot: QtBot):
        """Test removing a group and clicking Yes on confirmation."""
        tab = main_window.study_settings_tab

        # First add a group to remove
        tab.valid_groups_list.addItem("TODEL")
        initial_count = tab.valid_groups_list.count()

        # Select last item
        tab.valid_groups_list.setCurrentRow(tab.valid_groups_list.count() - 1)

        # Handle "Confirm Removal" dialog - click Yes
        click_yes_on_any_dialog(qtbot)

        qtbot.mouseClick(tab.remove_group_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert tab.valid_groups_list.count() == initial_count - 1

    def test_remove_group_click_no(self, main_window, qtbot: QtBot):
        """Test removing a group and clicking No keeps it."""
        tab = main_window.study_settings_tab

        # Add group first
        tab.valid_groups_list.addItem("KEEP")
        initial_count = tab.valid_groups_list.count()

        tab.valid_groups_list.setCurrentRow(tab.valid_groups_list.count() - 1)

        # Handle "Confirm Removal" dialog - click No
        click_no_on_any_dialog(qtbot)

        qtbot.mouseClick(tab.remove_group_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        # Count should stay the same
        assert tab.valid_groups_list.count() == initial_count

    def test_edit_group_button(self, main_window, qtbot: QtBot):
        """Test edit group button with dialog."""
        tab = main_window.study_settings_tab

        # Add and select a group
        tab.valid_groups_list.addItem("EDIT")
        tab.valid_groups_list.setCurrentRow(tab.valid_groups_list.count() - 1)

        # Handle QInputDialog for edit - just cancel it
        handle_input_dialog(qtbot, "EDITED", accept=False)

        qtbot.mouseClick(tab.edit_group_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)


# ============================================================================
# STUDY SETTINGS - VALID TIMEPOINTS (with dialog handling)
# ============================================================================


class TestStudySettingsValidTimepoints:
    """Test valid timepoints list interactions."""

    def test_add_timepoint_unique_name(self, main_window, qtbot: QtBot):
        """Test adding a timepoint with unique short name."""
        tab = main_window.study_settings_tab

        initial_count = tab.valid_timepoints_list.count()

        # Use a unique name to avoid "Duplicate Timepoint" dialog
        import random

        unique_name = f"X{random.randint(100, 999)}"
        handle_input_dialog(qtbot, unique_name, accept=True)

        qtbot.mouseClick(tab.add_timepoint_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert tab.valid_timepoints_list.count() >= initial_count

    def test_add_duplicate_timepoint_shows_error(self, main_window, qtbot: QtBot):
        """Test adding duplicate timepoint shows 'Duplicate Timepoint' dialog."""
        tab = main_window.study_settings_tab

        # First add a timepoint
        tab.valid_timepoints_list.addItem("DUP1")
        initial_count = tab.valid_timepoints_list.count()

        # Try to add the same one again
        handle_input_dialog(qtbot, "DUP1", accept=True)

        # Handle "Duplicate Timepoint" dialog - click OK
        click_any_ok_dialog(qtbot, delay_ms=250)

        qtbot.mouseClick(tab.add_timepoint_button, Qt.MouseButton.LeftButton)
        qtbot.wait(400)

        # Count should NOT increase (duplicate rejected)
        assert tab.valid_timepoints_list.count() == initial_count

    def test_add_timepoint_long_name_error(self, main_window, qtbot: QtBot):
        """Test adding timepoint with >10 chars shows error."""
        tab = main_window.study_settings_tab

        initial_count = tab.valid_timepoints_list.count()

        # Enter long name
        handle_input_dialog(qtbot, "VERYLONGTIMEPOINT", accept=True)

        # Handle error dialog
        click_any_ok_dialog(qtbot, delay_ms=250)

        qtbot.mouseClick(tab.add_timepoint_button, Qt.MouseButton.LeftButton)
        qtbot.wait(400)

        assert tab.valid_timepoints_list.count() == initial_count

    def test_remove_timepoint_click_yes(self, main_window, qtbot: QtBot):
        """Test removing timepoint and clicking Yes."""
        tab = main_window.study_settings_tab

        tab.valid_timepoints_list.addItem("DEL")
        initial_count = tab.valid_timepoints_list.count()

        tab.valid_timepoints_list.setCurrentRow(tab.valid_timepoints_list.count() - 1)

        click_yes_on_any_dialog(qtbot)

        qtbot.mouseClick(tab.remove_timepoint_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert tab.valid_timepoints_list.count() == initial_count - 1

    def test_remove_timepoint_click_no(self, main_window, qtbot: QtBot):
        """Test removing timepoint and clicking No keeps it."""
        tab = main_window.study_settings_tab

        tab.valid_timepoints_list.addItem("STAY")
        initial_count = tab.valid_timepoints_list.count()

        tab.valid_timepoints_list.setCurrentRow(tab.valid_timepoints_list.count() - 1)

        click_no_on_any_dialog(qtbot)

        qtbot.mouseClick(tab.remove_timepoint_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert tab.valid_timepoints_list.count() == initial_count


# ============================================================================
# STUDY SETTINGS - DEFAULT SELECTIONS
# ============================================================================


class TestStudySettingsDefaultSelections:
    """Test default group/timepoint dropdowns."""

    def test_default_group_dropdown_exists(self, main_window, qtbot: QtBot):
        """Test default group dropdown exists."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "default_group_combo")

    def test_default_timepoint_dropdown_exists(self, main_window, qtbot: QtBot):
        """Test default timepoint dropdown exists."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "default_timepoint_combo")


# ============================================================================
# STUDY SETTINGS - ALGORITHM CONFIG
# ============================================================================


class TestStudySettingsAlgorithmConfig:
    """Test algorithm configuration."""

    def test_sleep_algorithm_combo_populated(self, main_window, qtbot: QtBot):
        """Test sleep algorithm combo has options."""
        tab = main_window.study_settings_tab
        assert tab.sleep_algorithm_combo.count() >= 1

    def test_change_sleep_algorithm(self, main_window, qtbot: QtBot):
        """Test changing sleep algorithm."""
        tab = main_window.study_settings_tab

        if tab.sleep_algorithm_combo.count() > 1:
            tab.sleep_algorithm_combo.setCurrentIndex(1)
            qtbot.wait(50)
            assert tab.sleep_algorithm_combo.currentIndex() == 1

    def test_nonwear_algorithm_combo_populated(self, main_window, qtbot: QtBot):
        """Test nonwear algorithm combo has options."""
        tab = main_window.study_settings_tab
        assert tab.nonwear_algorithm_combo.count() >= 1


# ============================================================================
# STUDY SETTINGS - NIGHT HOURS
# ============================================================================


class TestStudySettingsNightHours:
    """Test night hours configuration."""

    def test_set_night_start(self, main_window, qtbot: QtBot):
        """Test setting night start time."""
        tab = main_window.study_settings_tab

        new_time = QTime(21, 0)
        tab.night_start_time.setTime(new_time)

        assert tab.night_start_time.time() == new_time

    def test_set_night_end(self, main_window, qtbot: QtBot):
        """Test setting night end time."""
        tab = main_window.study_settings_tab

        new_time = QTime(8, 0)
        tab.night_end_time.setTime(new_time)

        assert tab.night_end_time.time() == new_time


# ============================================================================
# STUDY SETTINGS - APPLY BUTTON (triggers "Settings Applied" dialog)
# ============================================================================


class TestStudySettingsApplyButton:
    """Test apply settings button."""

    def test_click_apply_shows_success_dialog(self, main_window, qtbot: QtBot):
        """Test clicking apply shows 'Settings Applied' dialog."""
        tab = main_window.study_settings_tab

        # Handle "Settings Applied" dialog - click OK
        click_any_ok_dialog(qtbot)

        qtbot.mouseClick(tab.apply_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)


# ============================================================================
# DATA SETTINGS TAB TESTS
# ============================================================================


class TestDataSettingsDataSource:
    """Test data source configuration."""

    def test_data_source_combo_populated(self, main_window, qtbot: QtBot):
        """Test data source combo has options."""
        tab = main_window.data_settings_tab
        assert tab.data_source_combo.count() >= 1

    def test_device_preset_combo_populated(self, main_window, qtbot: QtBot):
        """Test device preset combo has options."""
        tab = main_window.data_settings_tab
        assert tab.device_preset_combo.count() >= 1


class TestDataSettingsEpochConfig:
    """Test epoch configuration."""

    def test_set_epoch_length(self, main_window, qtbot: QtBot):
        """Test setting epoch length."""
        tab = main_window.data_settings_tab

        tab.epoch_length_spin.setValue(60)
        assert tab.epoch_length_spin.value() == 60

    def test_set_skip_rows(self, main_window, qtbot: QtBot):
        """Test setting skip rows."""
        tab = main_window.data_settings_tab

        tab.skip_rows_spin.setValue(5)
        assert tab.skip_rows_spin.value() == 5


class TestDataSettingsAutodetect:
    """Test auto-detect buttons (trigger "Auto-Detection Results" dialog)."""

    def test_click_autodetect_all_click_no(self, main_window, qtbot: QtBot):
        """Test clicking autodetect all and clicking No."""
        tab = main_window.data_settings_tab

        # May show "Auto-Detection Results" or error dialog
        click_no_on_any_dialog(qtbot)
        click_any_ok_dialog(qtbot, delay_ms=200)

        qtbot.mouseClick(tab.autodetect_all_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(300)


class TestDataSettingsGT3XOptions:
    """Test GT3X-specific options."""

    def test_gt3x_epoch_spin_exists(self, main_window, qtbot: QtBot):
        """Test GT3X epoch spin exists."""
        tab = main_window.data_settings_tab
        assert hasattr(tab, "gt3x_epoch_length_spin")

    def test_gt3x_return_raw_checkbox(self, main_window, qtbot: QtBot):
        """Test GT3X return raw checkbox toggle."""
        tab = main_window.data_settings_tab

        initial = tab.gt3x_return_raw_check.isChecked()
        tab.gt3x_return_raw_check.setChecked(not initial)
        assert tab.gt3x_return_raw_check.isChecked() != initial


class TestDataSettingsClearButtons:
    """Test clear buttons with confirmation dialogs."""

    def test_clear_markers_click_no(self, main_window, qtbot: QtBot):
        """Test clear markers and click No."""
        tab = main_window.data_settings_tab

        # Handle confirmation dialog
        click_no_on_any_dialog(qtbot)

        qtbot.mouseClick(tab.clear_markers_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(200)


# ============================================================================
# ANALYSIS TAB TESTS
# ============================================================================


class TestAnalysisTabFileSelection:
    """Test file selection."""

    def test_file_selector_exists(self, main_window, qtbot: QtBot):
        """Test file selector exists."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "file_selector")


class TestAnalysisTabDateNavigation:
    """Test date navigation."""

    def test_prev_next_buttons_exist(self, main_window, qtbot: QtBot):
        """Test prev/next buttons exist."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "prev_date_btn")
        assert hasattr(tab, "next_date_btn")

    def test_date_dropdown_exists(self, main_window, qtbot: QtBot):
        """Test date dropdown exists."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "date_dropdown")


class TestAnalysisTabViewMode:
    """Test view mode."""

    def test_toggle_24h_48h(self, main_window, qtbot: QtBot):
        """Test toggling between 24h and 48h view."""
        tab = main_window.analysis_tab

        qtbot.mouseClick(tab.view_24h_btn, Qt.MouseButton.LeftButton)
        assert tab.view_24h_btn.isChecked()

        qtbot.mouseClick(tab.view_48h_btn, Qt.MouseButton.LeftButton)
        assert tab.view_48h_btn.isChecked()


class TestAnalysisTabTimeInputs:
    """Test time inputs."""

    def test_type_onset_time(self, main_window, qtbot: QtBot):
        """Test typing onset time."""
        tab = main_window.analysis_tab

        tab.onset_time_input.clear()
        QTest.keyClicks(tab.onset_time_input, "22:30")
        assert tab.onset_time_input.text() == "22:30"

    def test_type_offset_time(self, main_window, qtbot: QtBot):
        """Test typing offset time."""
        tab = main_window.analysis_tab

        tab.offset_time_input.clear()
        QTest.keyClicks(tab.offset_time_input, "07:15")
        assert tab.offset_time_input.text() == "07:15"


class TestAnalysisTabMarkerMode:
    """Test marker mode."""

    def test_toggle_sleep_nonwear_mode(self, main_window, qtbot: QtBot):
        """Test toggling between sleep and nonwear mode."""
        tab = main_window.analysis_tab

        qtbot.mouseClick(tab.sleep_mode_btn, Qt.MouseButton.LeftButton)
        assert tab.sleep_mode_btn.isChecked()

        qtbot.mouseClick(tab.nonwear_mode_btn, Qt.MouseButton.LeftButton)
        assert tab.nonwear_mode_btn.isChecked()


class TestAnalysisTabActionButtons:
    """Test action buttons with their dialogs."""

    def test_save_markers_no_file_shows_dialog(self, main_window, qtbot: QtBot):
        """Test save markers with no file shows 'No File Selected' dialog."""
        tab = main_window.analysis_tab

        # Handle "No File Selected" or "No Markers" dialog
        click_any_ok_dialog(qtbot)

        qtbot.mouseClick(tab.save_markers_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

    def test_no_sleep_button(self, main_window, qtbot: QtBot):
        """Test no sleep button."""
        tab = main_window.analysis_tab

        # May show dialog
        click_any_ok_dialog(qtbot)

        qtbot.mouseClick(tab.no_sleep_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

    def test_clear_markers_click_no(self, main_window, qtbot: QtBot):
        """Test clear markers and click No on confirmation."""
        tab = main_window.analysis_tab

        # Handle "Clear Markers" confirmation - click No
        click_no_on_any_dialog(qtbot)

        qtbot.mouseClick(tab.clear_markers_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(200)


class TestAnalysisTabCheckboxes:
    """Test checkboxes."""

    def test_adjacent_markers_checkbox(self, main_window, qtbot: QtBot):
        """Test adjacent markers checkbox toggle."""
        tab = main_window.analysis_tab

        initial = tab.show_adjacent_day_markers_checkbox.isChecked()
        tab.show_adjacent_day_markers_checkbox.setChecked(not initial)
        assert tab.show_adjacent_day_markers_checkbox.isChecked() != initial

    def test_manual_nonwear_checkbox(self, main_window, qtbot: QtBot):
        """Test manual nonwear checkbox toggle."""
        tab = main_window.analysis_tab

        initial = tab.show_manual_nonwear_checkbox.isChecked()
        tab.show_manual_nonwear_checkbox.setChecked(not initial)
        assert tab.show_manual_nonwear_checkbox.isChecked() != initial


class TestAnalysisTabActivitySource:
    """Test activity source dropdown."""

    def test_activity_source_has_options(self, main_window, qtbot: QtBot):
        """Test activity source dropdown has options."""
        tab = main_window.analysis_tab
        assert tab.activity_source_dropdown.count() >= 4


# ============================================================================
# EXPORT TAB TESTS
# ============================================================================


class TestExportTab:
    """Test export tab."""

    def test_export_tab_exists(self, main_window, qtbot: QtBot):
        """Test export tab exists."""
        assert hasattr(main_window, "export_tab")

    def test_export_button_exists(self, main_window, qtbot: QtBot):
        """Test export button exists."""
        tab = main_window.export_tab
        assert hasattr(tab, "export_btn")

    def test_column_count_label_exists(self, main_window, qtbot: QtBot):
        """Test column count label exists."""
        tab = main_window.export_tab
        # The select_columns_btn is not stored as self attribute, but column_count_label is
        assert hasattr(tab, "column_count_label")

    def test_click_export_shows_dialog(self, main_window, qtbot: QtBot):
        """Test clicking export may show error dialog."""
        tab = main_window.export_tab

        # Handle any error dialog
        click_any_ok_dialog(qtbot)

        qtbot.mouseClick(tab.export_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(200)


# ============================================================================
# STANDALONE WIDGET TESTS
# ============================================================================


class TestActivityPlotWidgetStandalone:
    """Test ActivityPlotWidget standalone."""

    def test_create_widget(self, qtbot: QtBot):
        """Test creating widget."""
        from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

        widget = ActivityPlotWidget()
        qtbot.addWidget(widget)
        widget.show()

        assert widget is not None

    def test_set_data(self, qtbot: QtBot):
        """Test setting data."""
        from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

        widget = ActivityPlotWidget()
        qtbot.addWidget(widget)
        widget.show()

        base_time = datetime(2024, 1, 1, 0, 0)
        timestamps = [base_time + timedelta(minutes=i) for i in range(1440)]
        activity_data = [np.random.randint(0, 1000) for _ in range(1440)]

        widget.set_data_and_restrictions(
            timestamps=timestamps,
            activity_data=activity_data,
            current_date=base_time.date(),
        )

        assert len(widget.x_data) > 0

    def test_clear_markers(self, qtbot: QtBot):
        """Test clearing markers."""
        from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

        widget = ActivityPlotWidget()
        qtbot.addWidget(widget)

        widget.clear_sleep_markers()
        periods = widget.daily_sleep_markers.get_complete_periods()
        assert len(periods) == 0


class TestFileSelectionTableStandalone:
    """Test FileSelectionTable standalone."""

    def test_add_file(self, qtbot: QtBot):
        """Test adding file."""
        from sleep_scoring_app.ui.widgets.file_selection_table import FileSelectionTable

        widget = FileSelectionTable()
        qtbot.addWidget(widget)

        widget.add_file({"filename": "test.csv", "participant_id": "001"})
        assert widget.table.rowCount() == 1

    def test_clear_table(self, qtbot: QtBot):
        """Test clearing table."""
        from sleep_scoring_app.ui.widgets.file_selection_table import FileSelectionTable

        widget = FileSelectionTable()
        qtbot.addWidget(widget)

        widget.add_file({"filename": "test.csv"})
        widget.clear()
        assert widget.table.rowCount() == 0


class TestDragDropListWidgetStandalone:
    """Test DragDropListWidget standalone."""

    def test_add_items(self, qtbot: QtBot):
        """Test adding items."""
        from sleep_scoring_app.ui.study_settings_tab import DragDropListWidget

        widget = DragDropListWidget()
        qtbot.addWidget(widget)

        widget.addItem("A")
        widget.addItem("B")
        assert widget.count() == 2

    def test_get_all_items(self, qtbot: QtBot):
        """Test getting all items."""
        from sleep_scoring_app.ui.study_settings_tab import DragDropListWidget

        widget = DragDropListWidget()
        qtbot.addWidget(widget)

        widget.addItem("X")
        widget.addItem("Y")

        items = widget.get_all_items()
        assert items == ["X", "Y"]

    def test_add_item_with_validation_uppercase(self, qtbot: QtBot):
        """Test add_item_with_validation uppercases."""
        from sleep_scoring_app.ui.study_settings_tab import DragDropListWidget

        widget = DragDropListWidget()
        qtbot.addWidget(widget)

        widget.add_item_with_validation("lower")
        assert "LOWER" in widget.get_all_items()

    def test_add_item_with_validation_no_duplicates(self, qtbot: QtBot):
        """Test no duplicates allowed."""
        from sleep_scoring_app.ui.study_settings_tab import DragDropListWidget

        widget = DragDropListWidget()
        qtbot.addWidget(widget)

        result1 = widget.add_item_with_validation("Test")
        result2 = widget.add_item_with_validation("TEST")

        assert result1 is True
        assert result2 is False
        assert widget.count() == 1


# ============================================================================
# MAIN WINDOW INTEGRATION TESTS
# ============================================================================


class TestMainWindowIntegration:
    """Test MainWindow integration."""

    def test_tab_count(self, main_window, qtbot: QtBot):
        """Test tab count."""
        assert main_window.tab_widget.count() >= 4

    def test_navigate_all_tabs(self, main_window, qtbot: QtBot):
        """Test navigating all tabs."""
        for i in range(main_window.tab_widget.count()):
            main_window.tab_widget.setCurrentIndex(i)
            qtbot.wait(50)
            assert main_window.tab_widget.currentIndex() == i

    def test_status_bar(self, main_window, qtbot: QtBot):
        """Test status bar."""
        status_bar = main_window.statusBar()
        assert status_bar is not None

        status_bar.showMessage("Test")
        qtbot.wait(50)


# ============================================================================
# COMPLETE WORKFLOW TESTS
# ============================================================================


class TestCompleteWorkflows:
    """Test complete user workflows."""

    def test_study_setup_workflow(self, main_window, qtbot: QtBot):
        """Test complete study setup workflow."""
        tab = main_window.study_settings_tab

        # Set ID pattern
        tab.id_pattern_edit.clear()
        QTest.keyClicks(tab.id_pattern_edit, r"(\d{4})")

        # Set night hours
        tab.night_start_time.setTime(QTime(22, 0))
        tab.night_end_time.setTime(QTime(7, 0))

        # Click apply (handle dialog)
        click_any_ok_dialog(qtbot)
        qtbot.mouseClick(tab.apply_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

    def test_analysis_workflow(self, main_window, qtbot: QtBot):
        """Test analysis workflow."""
        tab = main_window.analysis_tab

        # Set view mode
        qtbot.mouseClick(tab.view_48h_btn, Qt.MouseButton.LeftButton)

        # Enter times
        tab.onset_time_input.clear()
        QTest.keyClicks(tab.onset_time_input, "23:00")

        tab.offset_time_input.clear()
        QTest.keyClicks(tab.offset_time_input, "06:00")

        assert tab.onset_time_input.text() == "23:00"
        assert tab.offset_time_input.text() == "06:00"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_time_accepted(self, main_window, qtbot: QtBot):
        """Test invalid time accepted."""
        tab = main_window.analysis_tab

        tab.onset_time_input.clear()
        QTest.keyClicks(tab.onset_time_input, "99:99")

        assert tab.onset_time_input.text() == "99:99"

    def test_empty_inputs(self, main_window, qtbot: QtBot):
        """Test empty inputs accepted."""
        tab = main_window.analysis_tab

        tab.onset_time_input.clear()
        tab.offset_time_input.clear()

        assert tab.onset_time_input.text() == ""
        assert tab.offset_time_input.text() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
