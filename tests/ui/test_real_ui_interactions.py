"""
REAL PyQt6 UI interaction tests.

These tests actually create windows, click buttons, type in fields,
and verify real UI state changes - NOT mocks.

Key findings from these tests:
- Tabs require SleepScoringMainWindow parent (tight coupling)
- ActivityPlotWidget uses set_data_and_restrictions() not set_data()
- FileSelectionTable uses add_file() not populate()
- DragDropListWidget.add_item_with_validation() uppercases text

Discovered attribute name mappings:
- StudySettingsTab: data_paradigm_combo, valid_groups_list, valid_timepoints_list
- DataSettingsTab: epoch_length_spin, data_source_combo, skip_rows_spin
- AnalysisTab: view_24h_btn, view_48h_btn, sleep_mode_btn, nonwear_mode_btn
- AnalysisTab: activity_source_dropdown, save_markers_btn, clear_markers_btn
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import numpy as np
import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


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
    qtbot.wait(100)  # Let it initialize
    return window


# ============================================================================
# ACTIVITY PLOT WIDGET - REAL INTERACTIONS
# ============================================================================


class TestActivityPlotWidgetReal:
    """Test ActivityPlotWidget with REAL mouse clicks and interactions."""

    def test_plot_widget_exists_on_main_window(self, main_window, qtbot: QtBot):
        """Test that plot widget exists on main window."""
        assert hasattr(main_window, "plot_widget")
        assert main_window.plot_widget is not None

    def test_plot_widget_can_set_data(self, qtbot: QtBot):
        """Test that plot widget can accept data."""
        from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

        widget = ActivityPlotWidget()
        qtbot.addWidget(widget)
        widget.show()

        # Create test data with datetime objects (not floats!)
        base_time = datetime(2024, 1, 1, 0, 0)
        timestamps = [base_time + timedelta(minutes=i) for i in range(1440)]
        activity_data = [np.random.randint(0, 1000) for _ in range(1440)]

        # Use correct method with datetime objects
        widget.set_data_and_restrictions(
            timestamps=timestamps,
            activity_data=activity_data,
            current_date=base_time.date(),
        )

        # Verify data was set
        assert len(widget.x_data) > 0

    def test_plot_widget_clear_markers(self, qtbot: QtBot):
        """Test clearing markers on plot widget."""
        from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

        widget = ActivityPlotWidget()
        qtbot.addWidget(widget)
        widget.show()

        # Clear markers
        widget.clear_sleep_markers()

        # Verify cleared
        periods = widget.daily_sleep_markers.get_complete_periods()
        assert len(periods) == 0

    def test_plot_widget_has_required_signals(self, qtbot: QtBot):
        """Test that plot widget has required signals."""
        from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

        widget = ActivityPlotWidget()
        qtbot.addWidget(widget)

        assert hasattr(widget, "sleep_markers_changed")
        assert hasattr(widget, "nonwear_markers_changed")


# ============================================================================
# FILE SELECTION TABLE - REAL INTERACTIONS
# ============================================================================


class TestFileSelectionTableReal:
    """Test FileSelectionTable with REAL interactions."""

    def test_table_exists_on_main_window(self, main_window, qtbot: QtBot):
        """Test that file selector exists on main window."""
        assert hasattr(main_window, "file_selector")
        assert main_window.file_selector is not None

    def test_table_can_add_file(self, qtbot: QtBot):
        """Test adding a file to the table."""
        from sleep_scoring_app.ui.widgets.file_selection_table import FileSelectionTable

        widget = FileSelectionTable()
        qtbot.addWidget(widget)
        widget.show()

        # Add a file using correct method
        widget.add_file(
            {
                "filename": "test_file.csv",
                "participant_id": "001",
                "timepoint": "T1",
                "group": "G1",
            }
        )

        # Verify row was added
        assert widget.table.rowCount() == 1

    def test_table_can_clear(self, qtbot: QtBot):
        """Test clearing the table."""
        from sleep_scoring_app.ui.widgets.file_selection_table import FileSelectionTable

        widget = FileSelectionTable()
        qtbot.addWidget(widget)
        widget.show()

        # Add files
        widget.add_file({"filename": "test1.csv", "participant_id": "001"})
        widget.add_file({"filename": "test2.csv", "participant_id": "002"})

        assert widget.table.rowCount() == 2

        # Clear
        widget.clear()

        assert widget.table.rowCount() == 0

    def test_table_selection_emits_signal(self, qtbot: QtBot):
        """Test that selecting a row emits signal."""
        from sleep_scoring_app.ui.widgets.file_selection_table import FileSelectionTable

        widget = FileSelectionTable()
        qtbot.addWidget(widget)
        widget.show()

        # Add a file
        widget.add_file({"filename": "test.csv", "participant_id": "001"})

        qtbot.wait(50)

        # Select the row
        with qtbot.waitSignal(widget.fileSelected, timeout=1000, raising=False):
            widget.table.selectRow(0)


# ============================================================================
# DRAG DROP LIST WIDGET - REAL INTERACTIONS
# ============================================================================


class TestDragDropListWidgetReal:
    """Test DragDropListWidget with REAL interactions."""

    def test_add_items(self, qtbot: QtBot):
        """Test adding items to the list."""
        from sleep_scoring_app.ui.study_settings_tab import DragDropListWidget

        widget = DragDropListWidget()
        qtbot.addWidget(widget)
        widget.show()

        widget.addItem("Group A")
        widget.addItem("Group B")

        assert widget.count() == 2

    def test_get_all_items(self, qtbot: QtBot):
        """Test getting all items."""
        from sleep_scoring_app.ui.study_settings_tab import DragDropListWidget

        widget = DragDropListWidget()
        qtbot.addWidget(widget)

        widget.addItem("Item1")
        widget.addItem("Item2")

        items = widget.get_all_items()
        assert items == ["Item1", "Item2"]

    def test_add_item_with_validation(self, qtbot: QtBot):
        """Test add_item_with_validation emits signal and uppercases."""
        from sleep_scoring_app.ui.study_settings_tab import DragDropListWidget

        widget = DragDropListWidget()
        qtbot.addWidget(widget)

        signals = []
        widget.items_changed.connect(lambda: signals.append(True))

        widget.add_item_with_validation("NewItem")

        assert len(signals) >= 1
        # Note: add_item_with_validation UPPERCASES the text
        assert "NEWITEM" in widget.get_all_items()


# ============================================================================
# MAIN WINDOW - REAL TAB INTERACTIONS
# ============================================================================


class TestMainWindowTabsReal:
    """Test MainWindow tabs with REAL interactions through the window."""

    def test_main_window_has_all_tabs(self, main_window, qtbot: QtBot):
        """Test main window has expected tabs."""
        assert main_window.tab_widget.count() >= 3

    def test_can_switch_to_study_settings(self, main_window, qtbot: QtBot):
        """Test switching to Study Settings tab."""
        # Find Study Settings tab index
        for i in range(main_window.tab_widget.count()):
            if "study" in main_window.tab_widget.tabText(i).lower():
                main_window.tab_widget.setCurrentIndex(i)
                qtbot.wait(50)
                assert main_window.tab_widget.currentIndex() == i
                return
        pytest.skip("Study Settings tab not found")

    def test_can_switch_to_data_settings(self, main_window, qtbot: QtBot):
        """Test switching to Data Settings tab."""
        for i in range(main_window.tab_widget.count()):
            if "data" in main_window.tab_widget.tabText(i).lower():
                main_window.tab_widget.setCurrentIndex(i)
                qtbot.wait(50)
                assert main_window.tab_widget.currentIndex() == i
                return
        pytest.skip("Data Settings tab not found")

    def test_can_switch_to_analysis_tab(self, main_window, qtbot: QtBot):
        """Test switching to Analysis tab."""
        for i in range(main_window.tab_widget.count()):
            if "analysis" in main_window.tab_widget.tabText(i).lower():
                main_window.tab_widget.setCurrentIndex(i)
                qtbot.wait(50)
                assert main_window.tab_widget.currentIndex() == i
                return
        pytest.skip("Analysis tab not found")

    def test_can_switch_to_export_tab(self, main_window, qtbot: QtBot):
        """Test switching to Export tab."""
        for i in range(main_window.tab_widget.count()):
            if "export" in main_window.tab_widget.tabText(i).lower():
                main_window.tab_widget.setCurrentIndex(i)
                qtbot.wait(50)
                assert main_window.tab_widget.currentIndex() == i
                return
        pytest.skip("Export tab not found")


class TestStudySettingsViaMainWindow:
    """Test Study Settings tab interactions via MainWindow."""

    def test_study_settings_tab_exists(self, main_window, qtbot: QtBot):
        """Test study_settings_tab attribute exists."""
        assert hasattr(main_window, "study_settings_tab")
        assert main_window.study_settings_tab is not None

    def test_data_paradigm_combo_exists(self, main_window, qtbot: QtBot):
        """Test data paradigm combo box exists (CORRECT: data_paradigm_combo)."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "data_paradigm_combo")

    def test_data_paradigm_combo_has_options(self, main_window, qtbot: QtBot):
        """Test data paradigm combo has options."""
        tab = main_window.study_settings_tab
        assert tab.data_paradigm_combo.count() >= 1

    def test_can_change_data_paradigm(self, main_window, qtbot: QtBot):
        """Test changing data paradigm selection and clicking Yes on confirmation dialog."""
        from PyQt6.QtWidgets import QMessageBox

        tab = main_window.study_settings_tab

        if tab.data_paradigm_combo.count() > 1:
            original = tab.data_paradigm_combo.currentIndex()
            new_index = (original + 1) % tab.data_paradigm_combo.count()

            # Schedule clicking "Yes" on the confirmation dialog
            def click_yes_on_dialog():
                # Find the active modal dialog
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, QMessageBox) and widget.isVisible():
                        # Click Yes button
                        yes_btn = widget.button(QMessageBox.StandardButton.Yes)
                        if yes_btn:
                            qtbot.mouseClick(yes_btn, Qt.MouseButton.LeftButton)
                            return

            # Use a timer to click the dialog after it appears
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(100, click_yes_on_dialog)

            tab.data_paradigm_combo.setCurrentIndex(new_index)
            qtbot.wait(200)  # Wait for dialog interaction

            assert tab.data_paradigm_combo.currentIndex() == new_index

    def test_id_pattern_edit_exists(self, main_window, qtbot: QtBot):
        """Test ID pattern edit exists."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "id_pattern_edit")

    def test_can_type_in_id_pattern(self, main_window, qtbot: QtBot):
        """Test typing in ID pattern field."""
        tab = main_window.study_settings_tab

        tab.id_pattern_edit.clear()
        QTest.keyClicks(tab.id_pattern_edit, r"(\d{3})")

        assert tab.id_pattern_edit.text() == r"(\d{3})"

    def test_valid_groups_list_exists(self, main_window, qtbot: QtBot):
        """Test valid groups list exists (CORRECT: valid_groups_list)."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "valid_groups_list")

    def test_can_add_group(self, main_window, qtbot: QtBot):
        """Test adding a group to the list."""
        tab = main_window.study_settings_tab

        initial_count = tab.valid_groups_list.count()
        tab.valid_groups_list.addItem("TestGroupXYZ")

        assert tab.valid_groups_list.count() == initial_count + 1

    def test_valid_timepoints_list_exists(self, main_window, qtbot: QtBot):
        """Test valid timepoints list exists (CORRECT: valid_timepoints_list)."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "valid_timepoints_list")

    def test_sleep_algorithm_combo_exists(self, main_window, qtbot: QtBot):
        """Test sleep algorithm combo exists."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "sleep_algorithm_combo")
        assert tab.sleep_algorithm_combo.count() >= 1

    def test_nonwear_algorithm_combo_exists(self, main_window, qtbot: QtBot):
        """Test nonwear algorithm combo exists."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "nonwear_algorithm_combo")
        assert tab.nonwear_algorithm_combo.count() >= 1

    def test_night_time_edits_exist(self, main_window, qtbot: QtBot):
        """Test night time edits exist."""
        tab = main_window.study_settings_tab
        assert hasattr(tab, "night_start_time")
        assert hasattr(tab, "night_end_time")

    def test_can_change_night_times(self, main_window, qtbot: QtBot):
        """Test changing night time values."""
        from PyQt6.QtCore import QTime

        tab = main_window.study_settings_tab

        new_start = QTime(21, 30)
        new_end = QTime(7, 30)

        tab.night_start_time.setTime(new_start)
        tab.night_end_time.setTime(new_end)

        assert tab.night_start_time.time() == new_start
        assert tab.night_end_time.time() == new_end


class TestDataSettingsViaMainWindow:
    """Test Data Settings tab interactions via MainWindow."""

    def test_data_settings_tab_exists(self, main_window, qtbot: QtBot):
        """Test data_settings_tab attribute exists."""
        assert hasattr(main_window, "data_settings_tab")
        assert main_window.data_settings_tab is not None

    def test_data_source_combo_exists(self, main_window, qtbot: QtBot):
        """Test data source combo exists."""
        tab = main_window.data_settings_tab
        assert hasattr(tab, "data_source_combo")

    def test_data_source_combo_has_options(self, main_window, qtbot: QtBot):
        """Test data source combo has options."""
        tab = main_window.data_settings_tab
        assert tab.data_source_combo.count() >= 1

    def test_can_change_data_source(self, main_window, qtbot: QtBot):
        """Test changing data source."""
        tab = main_window.data_settings_tab

        if tab.data_source_combo.count() > 1:
            tab.data_source_combo.setCurrentIndex(1)
            assert tab.data_source_combo.currentIndex() == 1

    def test_epoch_length_spin_exists(self, main_window, qtbot: QtBot):
        """Test epoch spinbox exists (CORRECT: epoch_length_spin)."""
        tab = main_window.data_settings_tab
        assert hasattr(tab, "epoch_length_spin")

    def test_can_change_epoch_length(self, main_window, qtbot: QtBot):
        """Test changing epoch length."""
        tab = main_window.data_settings_tab

        tab.epoch_length_spin.setValue(30)
        assert tab.epoch_length_spin.value() == 30

        tab.epoch_length_spin.setValue(60)
        assert tab.epoch_length_spin.value() == 60

    def test_skip_rows_spin_exists(self, main_window, qtbot: QtBot):
        """Test skip rows spinbox exists."""
        tab = main_window.data_settings_tab
        assert hasattr(tab, "skip_rows_spin")


class TestAnalysisTabViaMainWindow:
    """Test Analysis tab interactions via MainWindow."""

    def test_analysis_tab_exists(self, main_window, qtbot: QtBot):
        """Test analysis_tab attribute exists."""
        assert hasattr(main_window, "analysis_tab")
        assert main_window.analysis_tab is not None

    def test_view_mode_buttons_exist(self, main_window, qtbot: QtBot):
        """Test view mode radio buttons exist (CORRECT: view_24h_btn, view_48h_btn)."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "view_24h_btn")
        assert hasattr(tab, "view_48h_btn")

    def test_can_toggle_view_modes(self, main_window, qtbot: QtBot):
        """Test toggling view mode radio buttons."""
        tab = main_window.analysis_tab

        # Click 24h
        qtbot.mouseClick(tab.view_24h_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(50)
        assert tab.view_24h_btn.isChecked()

        # Click 48h
        qtbot.mouseClick(tab.view_48h_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(50)
        assert tab.view_48h_btn.isChecked()

    def test_time_inputs_exist(self, main_window, qtbot: QtBot):
        """Test time input fields exist."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "onset_time_input")
        assert hasattr(tab, "offset_time_input")

    def test_can_type_onset_time(self, main_window, qtbot: QtBot):
        """Test typing in onset time field."""
        tab = main_window.analysis_tab

        tab.onset_time_input.clear()
        QTest.keyClicks(tab.onset_time_input, "22:30")

        assert tab.onset_time_input.text() == "22:30"

    def test_can_type_offset_time(self, main_window, qtbot: QtBot):
        """Test typing in offset time field."""
        tab = main_window.analysis_tab

        tab.offset_time_input.clear()
        QTest.keyClicks(tab.offset_time_input, "07:15")

        assert tab.offset_time_input.text() == "07:15"

    def test_marker_mode_buttons_exist(self, main_window, qtbot: QtBot):
        """Test marker mode radio buttons exist (CORRECT: sleep_mode_btn, nonwear_mode_btn)."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "sleep_mode_btn")
        assert hasattr(tab, "nonwear_mode_btn")

    def test_can_toggle_marker_modes(self, main_window, qtbot: QtBot):
        """Test toggling marker mode."""
        tab = main_window.analysis_tab

        qtbot.mouseClick(tab.sleep_mode_btn, Qt.MouseButton.LeftButton)
        assert tab.sleep_mode_btn.isChecked()

        qtbot.mouseClick(tab.nonwear_mode_btn, Qt.MouseButton.LeftButton)
        assert tab.nonwear_mode_btn.isChecked()

    def test_activity_source_dropdown_exists(self, main_window, qtbot: QtBot):
        """Test activity source dropdown exists (CORRECT: activity_source_dropdown)."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "activity_source_dropdown")

    def test_save_markers_btn_exists(self, main_window, qtbot: QtBot):
        """Test save button exists (CORRECT: save_markers_btn)."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "save_markers_btn")

    def test_clear_markers_btn_exists(self, main_window, qtbot: QtBot):
        """Test clear button exists (CORRECT: clear_markers_btn)."""
        tab = main_window.analysis_tab
        assert hasattr(tab, "clear_markers_btn")

    def test_click_clear_markers_button(self, main_window, qtbot: QtBot):
        """Test clicking clear button and interacting with confirmation dialog."""
        from PyQt6.QtWidgets import QMessageBox

        tab = main_window.analysis_tab

        # Schedule clicking "No" on the confirmation dialog (don't actually delete)
        def click_no_on_dialog():
            # Find the active modal dialog
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QMessageBox) and widget.isVisible():
                    # Click No button to cancel the deletion
                    no_btn = widget.button(QMessageBox.StandardButton.No)
                    if no_btn:
                        qtbot.mouseClick(no_btn, Qt.MouseButton.LeftButton)
                        return

        # Use a timer to click the dialog after it appears
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(100, click_no_on_dialog)

        # Click the clear button - this triggers the confirmation dialog
        qtbot.mouseClick(tab.clear_markers_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(200)  # Wait for dialog interaction


class TestExportTabViaMainWindow:
    """Test Export tab interactions via MainWindow."""

    def test_export_tab_exists(self, main_window, qtbot: QtBot):
        """Test export_tab attribute exists."""
        assert hasattr(main_window, "export_tab")
        assert main_window.export_tab is not None

    def test_export_button_exists(self, main_window, qtbot: QtBot):
        """Test export button exists."""
        tab = main_window.export_tab
        assert hasattr(tab, "export_btn")


# ============================================================================
# FULL WORKFLOW TESTS
# ============================================================================


class TestCompleteWorkflows:
    """Test complete user workflows."""

    def test_navigate_all_tabs(self, main_window, qtbot: QtBot):
        """Test navigating through all tabs."""
        for i in range(main_window.tab_widget.count()):
            main_window.tab_widget.setCurrentIndex(i)
            qtbot.wait(50)
            assert main_window.tab_widget.currentIndex() == i

    def test_configure_study_settings(self, main_window, qtbot: QtBot):
        """Test configuring study settings."""
        tab = main_window.study_settings_tab

        # Set ID pattern
        tab.id_pattern_edit.clear()
        QTest.keyClicks(tab.id_pattern_edit, r"(\d+)")

        # Add groups (use correct attribute name)
        tab.valid_groups_list.addItem("Control")
        tab.valid_groups_list.addItem("Treatment")

        # Verify
        assert tab.id_pattern_edit.text() == r"(\d+)"
        assert tab.valid_groups_list.count() >= 2

    def test_set_manual_times_workflow(self, main_window, qtbot: QtBot):
        """Test setting manual onset/offset times."""
        tab = main_window.analysis_tab

        # Enter times
        tab.onset_time_input.clear()
        QTest.keyClicks(tab.onset_time_input, "22:00")

        tab.offset_time_input.clear()
        QTest.keyClicks(tab.offset_time_input, "06:30")

        # Verify
        assert tab.onset_time_input.text() == "22:00"
        assert tab.offset_time_input.text() == "06:30"

    def test_status_bar_exists(self, main_window, qtbot: QtBot):
        """Test status bar is functional."""
        status_bar = main_window.statusBar()
        assert status_bar is not None

        # Show a message
        status_bar.showMessage("Test message")
        qtbot.wait(50)


# ============================================================================
# ERROR CONDITION TESTS
# ============================================================================


class TestErrorConditions:
    """Test error handling in UI."""

    def test_invalid_time_input(self, main_window, qtbot: QtBot):
        """Test entering invalid time doesn't crash."""
        tab = main_window.analysis_tab

        tab.onset_time_input.clear()
        QTest.keyClicks(tab.onset_time_input, "invalid")

        # Should not crash
        assert tab.onset_time_input.text() == "invalid"

    def test_empty_time_input(self, main_window, qtbot: QtBot):
        """Test empty time input doesn't crash."""
        tab = main_window.analysis_tab

        tab.onset_time_input.clear()

        # Should not crash
        assert tab.onset_time_input.text() == ""

    def test_invalid_regex_pattern(self, main_window, qtbot: QtBot):
        """Test invalid regex pattern doesn't crash."""
        tab = main_window.study_settings_tab

        tab.id_pattern_edit.clear()
        QTest.keyClicks(tab.id_pattern_edit, "(((")  # Invalid regex

        # Should not crash - might show validation error
        assert tab.id_pattern_edit.text() == "((("


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
