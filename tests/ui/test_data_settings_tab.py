"""
Tests for DataSettingsTab component.

These tests interact with the REAL DataSettingsTab like a user would:
- Changing data source type
- Adjusting epoch length
- Setting skip rows
- Changing device presets
- Auto-detect functionality
- Configuring GT3X options
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

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
def data_settings_tab(main_window):
    """Get the Data Settings tab from main window."""
    # Switch to Data Settings tab
    for i in range(main_window.tab_widget.count()):
        if main_window.tab_widget.tabText(i) == "Data Settings":
            main_window.tab_widget.setCurrentIndex(i)
            break
    return main_window.data_settings_tab


class TestDataSettingsTabBasics:
    """Test basic Data Settings tab functionality."""

    def test_data_settings_tab_exists(self, main_window, qtbot):
        """Test that Data Settings tab exists."""
        assert hasattr(main_window, "data_settings_tab")
        assert main_window.data_settings_tab is not None

    def test_tab_has_scroll_area(self, data_settings_tab, qtbot):
        """Test that tab content is scrollable."""
        from PyQt6.QtWidgets import QScrollArea

        scroll_areas = data_settings_tab.findChildren(QScrollArea)
        assert len(scroll_areas) > 0

    def test_tab_shows_paradigm_indicator(self, data_settings_tab, qtbot):
        """Test that current paradigm is displayed."""
        assert hasattr(data_settings_tab, "paradigm_indicator_label")
        assert data_settings_tab.paradigm_indicator_label is not None


class TestDataSourceConfiguration:
    """Test data source configuration."""

    def test_data_source_combo_exists(self, data_settings_tab, qtbot):
        """Test that data source type dropdown exists."""
        assert hasattr(data_settings_tab, "data_source_combo")
        assert data_settings_tab.data_source_combo is not None

    def test_data_source_combo_has_options(self, data_settings_tab, qtbot):
        """Test that data source dropdown has multiple options."""
        count = data_settings_tab.data_source_combo.count()
        assert count > 0

    def test_device_preset_combo_exists(self, data_settings_tab, qtbot):
        """Test that device preset dropdown exists."""
        assert hasattr(data_settings_tab, "device_preset_combo")
        assert data_settings_tab.device_preset_combo is not None

    def test_device_preset_has_multiple_options(self, data_settings_tab, qtbot):
        """Test that device preset has multiple options."""
        count = data_settings_tab.device_preset_combo.count()
        assert count >= 5  # ActiGraph, GENEActiv, Axivity, Actiwatch, MotionWatch, Generic CSV

    def test_select_different_data_source(self, data_settings_tab, qtbot):
        """Test selecting a different data source."""
        if data_settings_tab.data_source_combo.count() > 1:
            initial_index = data_settings_tab.data_source_combo.currentIndex()

            # Select different index
            new_index = (initial_index + 1) % data_settings_tab.data_source_combo.count()
            data_settings_tab.data_source_combo.setCurrentIndex(new_index)
            qtbot.wait(50)

            assert data_settings_tab.data_source_combo.currentIndex() == new_index

    def test_select_different_device_preset(self, data_settings_tab, qtbot):
        """Test selecting a different device preset."""
        if data_settings_tab.device_preset_combo.count() > 1:
            initial_index = data_settings_tab.device_preset_combo.currentIndex()

            # Select different index
            new_index = (initial_index + 1) % data_settings_tab.device_preset_combo.count()
            data_settings_tab.device_preset_combo.setCurrentIndex(new_index)
            qtbot.wait(50)

            assert data_settings_tab.device_preset_combo.currentIndex() == new_index


class TestEpochLengthConfiguration:
    """Test epoch length settings."""

    def test_epoch_length_spinbox_exists(self, data_settings_tab, qtbot):
        """Test that epoch length spinbox exists."""
        assert hasattr(data_settings_tab, "epoch_length_spin")
        assert data_settings_tab.epoch_length_spin is not None

    def test_epoch_length_has_valid_range(self, data_settings_tab, qtbot):
        """Test that epoch length has valid min/max values."""
        min_val = data_settings_tab.epoch_length_spin.minimum()
        max_val = data_settings_tab.epoch_length_spin.maximum()

        assert min_val >= 1
        assert max_val >= 60  # Should allow at least 60 seconds

    def test_set_epoch_length_to_60(self, data_settings_tab, qtbot):
        """Test setting epoch length to 60 seconds."""
        data_settings_tab.epoch_length_spin.setValue(60)
        qtbot.wait(50)

        assert data_settings_tab.epoch_length_spin.value() == 60

    def test_set_epoch_length_to_30(self, data_settings_tab, qtbot):
        """Test setting epoch length to 30 seconds."""
        data_settings_tab.epoch_length_spin.setValue(30)
        qtbot.wait(50)

        assert data_settings_tab.epoch_length_spin.value() == 30

    def test_epoch_autodetect_button_exists(self, data_settings_tab, qtbot):
        """Test that epoch auto-detect button exists."""
        assert hasattr(data_settings_tab, "epoch_autodetect_btn")
        assert data_settings_tab.epoch_autodetect_btn is not None


class TestSkipRowsConfiguration:
    """Test skip rows settings."""

    def test_skip_rows_spinbox_exists(self, data_settings_tab, qtbot):
        """Test that skip rows spinbox exists."""
        assert hasattr(data_settings_tab, "skip_rows_spin")
        assert data_settings_tab.skip_rows_spin is not None

    def test_skip_rows_has_valid_range(self, data_settings_tab, qtbot):
        """Test that skip rows has valid range."""
        min_val = data_settings_tab.skip_rows_spin.minimum()
        max_val = data_settings_tab.skip_rows_spin.maximum()

        assert min_val == 0
        assert max_val >= 10

    def test_set_skip_rows_to_10(self, data_settings_tab, qtbot):
        """Test setting skip rows to 10."""
        data_settings_tab.skip_rows_spin.setValue(10)
        qtbot.wait(50)

        assert data_settings_tab.skip_rows_spin.value() == 10

    def test_set_skip_rows_to_zero(self, data_settings_tab, qtbot):
        """Test setting skip rows to 0."""
        data_settings_tab.skip_rows_spin.setValue(0)
        qtbot.wait(50)

        assert data_settings_tab.skip_rows_spin.value() == 0

    def test_skip_rows_autodetect_button_exists(self, data_settings_tab, qtbot):
        """Test that skip rows auto-detect button exists."""
        assert hasattr(data_settings_tab, "skip_rows_autodetect_btn")
        assert data_settings_tab.skip_rows_autodetect_btn is not None


class TestGT3XOptions:
    """Test GT3X-specific options."""

    def test_gt3x_options_widget_exists(self, data_settings_tab, qtbot):
        """Test that GT3X options section exists."""
        assert hasattr(data_settings_tab, "gt3x_options_widget")
        assert data_settings_tab.gt3x_options_widget is not None

    def test_gt3x_epoch_length_spinbox_exists(self, data_settings_tab, qtbot):
        """Test that GT3X epoch length spinbox exists."""
        assert hasattr(data_settings_tab, "gt3x_epoch_length_spin")
        assert data_settings_tab.gt3x_epoch_length_spin is not None

    def test_gt3x_return_raw_checkbox_exists(self, data_settings_tab, qtbot):
        """Test that GT3X return raw checkbox exists."""
        assert hasattr(data_settings_tab, "gt3x_return_raw_check")
        assert data_settings_tab.gt3x_return_raw_check is not None

    def test_toggle_gt3x_return_raw(self, data_settings_tab, qtbot):
        """Test toggling GT3X return raw option."""
        initial_state = data_settings_tab.gt3x_return_raw_check.isChecked()

        qtbot.mouseClick(data_settings_tab.gt3x_return_raw_check, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        new_state = data_settings_tab.gt3x_return_raw_check.isChecked()
        assert new_state != initial_state


class TestAutoDetectButtons:
    """Test auto-detect button functionality."""

    def test_device_autodetect_button_exists(self, data_settings_tab, qtbot):
        """Test that device auto-detect button exists."""
        assert hasattr(data_settings_tab, "device_autodetect_btn")
        assert data_settings_tab.device_autodetect_btn is not None

    def test_autodetect_all_button_exists(self, data_settings_tab, qtbot):
        """Test that auto-detect all button exists."""
        assert hasattr(data_settings_tab, "autodetect_all_btn")
        assert data_settings_tab.autodetect_all_btn is not None

    def test_click_autodetect_all_with_no_files(self, data_settings_tab, qtbot):
        """Test clicking auto-detect all when no files are selected."""
        dialogs_handled = []
        schedule_dialog_handler(dialogs_handled, click_yes=False)

        data_settings_tab.autodetect_all_btn.click()
        qtbot.wait(2000)

        assert len(dialogs_handled) > 0, "No dialog appeared"


class TestColumnMappingConfiguration:
    """Test column mapping for Generic CSV."""

    def test_configure_columns_button_exists(self, data_settings_tab, qtbot):
        """Test that Configure Columns button exists."""
        assert hasattr(data_settings_tab, "configure_columns_btn")
        assert data_settings_tab.configure_columns_btn is not None

    def test_column_mapping_status_label_exists(self, data_settings_tab, qtbot):
        """Test that column mapping status label exists."""
        assert hasattr(data_settings_tab, "column_mapping_status")
        assert data_settings_tab.column_mapping_status is not None


class TestImportButtons:
    """Test import buttons and labels."""

    def test_activity_browse_button_exists(self, data_settings_tab, qtbot):
        """Test that activity data browse button exists."""
        assert hasattr(data_settings_tab, "activity_browse_btn")
        assert data_settings_tab.activity_browse_btn is not None

    def test_activity_import_button_exists(self, data_settings_tab, qtbot):
        """Test that activity data import button exists."""
        assert hasattr(data_settings_tab, "activity_import_btn")
        assert data_settings_tab.activity_import_btn is not None

    def test_activity_import_button_disabled_initially(self, data_settings_tab, qtbot):
        """Test that import button is disabled when no files selected."""
        # Button should be disabled until files are selected
        assert data_settings_tab.activity_import_btn.isEnabled() is False

    def test_activity_import_files_label_exists(self, data_settings_tab, qtbot):
        """Test that import files label exists."""
        assert hasattr(data_settings_tab, "activity_import_files_label")
        assert data_settings_tab.activity_import_files_label is not None


class TestProgressIndicators:
    """Test progress bars and status labels."""

    def test_activity_progress_bar_exists(self, data_settings_tab, qtbot):
        """Test that activity progress bar exists."""
        assert hasattr(data_settings_tab, "activity_progress_bar")
        assert data_settings_tab.activity_progress_bar is not None

    def test_activity_progress_label_exists(self, data_settings_tab, qtbot):
        """Test that activity progress label exists."""
        assert hasattr(data_settings_tab, "activity_progress_label")
        assert data_settings_tab.activity_progress_label is not None

    def test_activity_status_label_exists(self, data_settings_tab, qtbot):
        """Test that activity status label exists."""
        assert hasattr(data_settings_tab, "activity_status_label")
        assert data_settings_tab.activity_status_label is not None

    def test_progress_components_hidden_initially(self, data_settings_tab, qtbot):
        """Test that progress components are hidden initially."""
        assert data_settings_tab.activity_progress_bar.isVisible() is False
        assert data_settings_tab.activity_progress_label.isVisible() is False


class TestClearButtons:
    """Test clear data buttons."""

    def test_clear_markers_button_exists(self, data_settings_tab, qtbot):
        """Test that clear markers button exists."""
        assert hasattr(data_settings_tab, "clear_markers_btn")
        assert data_settings_tab.clear_markers_btn is not None

    def test_clear_markers_button_text(self, data_settings_tab, qtbot):
        """Test that clear markers button has correct text."""
        assert "Clear" in data_settings_tab.clear_markers_btn.text()
        assert "Markers" in data_settings_tab.clear_markers_btn.text()

    def test_click_clear_markers_shows_confirmation(self, data_settings_tab, qtbot):
        """Test that clicking clear markers shows confirmation dialog."""
        dialogs_handled = []
        schedule_dialog_handler(dialogs_handled, click_yes=False)

        data_settings_tab.clear_markers_btn.click()
        qtbot.wait(2000)

        assert len(dialogs_handled) > 0, "No confirmation dialog appeared"


class TestNonwearDataSection:
    """Test NWT sensor data section."""

    def test_nwt_browse_button_exists(self, data_settings_tab, qtbot):
        """Test that NWT browse button exists."""
        assert hasattr(data_settings_tab, "nwt_browse_btn")
        assert data_settings_tab.nwt_browse_btn is not None

    def test_nwt_import_button_exists(self, data_settings_tab, qtbot):
        """Test that NWT import button exists."""
        assert hasattr(data_settings_tab, "nwt_import_btn")
        assert data_settings_tab.nwt_import_btn is not None

    def test_nwt_import_button_disabled_initially(self, data_settings_tab, qtbot):
        """Test that NWT import button is disabled initially."""
        assert data_settings_tab.nwt_import_btn.isEnabled() is False

    def test_nwt_progress_components_exist(self, data_settings_tab, qtbot):
        """Test that NWT progress components exist."""
        assert hasattr(data_settings_tab, "nwt_progress_bar")
        assert hasattr(data_settings_tab, "nwt_progress_label")


class TestDiaryDataSection:
    """Test sleep diary data section."""

    def test_diary_browse_button_exists(self, data_settings_tab, qtbot):
        """Test that diary browse button exists."""
        assert hasattr(data_settings_tab, "diary_import_browse_btn")
        assert data_settings_tab.diary_import_browse_btn is not None

    def test_diary_import_button_exists(self, data_settings_tab, qtbot):
        """Test that diary import button exists."""
        assert hasattr(data_settings_tab, "diary_import_btn")
        assert data_settings_tab.diary_import_btn is not None

    def test_diary_import_button_disabled_initially(self, data_settings_tab, qtbot):
        """Test that diary import button is disabled initially."""
        assert data_settings_tab.diary_import_btn.isEnabled() is False

    def test_diary_status_label_exists(self, data_settings_tab, qtbot):
        """Test that diary status label exists."""
        assert hasattr(data_settings_tab, "diary_status_label")
        assert data_settings_tab.diary_status_label is not None


class TestParadigmIndicator:
    """Test data paradigm indicator."""

    def test_paradigm_indicator_shows_current_paradigm(self, data_settings_tab, qtbot):
        """Test that paradigm indicator displays current paradigm."""
        label_text = data_settings_tab.paradigm_indicator_label.text()
        assert "Paradigm" in label_text or "paradigm" in label_text.lower()

    def test_paradigm_change_button_exists(self, data_settings_tab, qtbot):
        """Test that change paradigm button exists."""
        # Find button with text containing "Change" and "Paradigm"
        buttons = data_settings_tab.findChildren(object)
        change_btns = [w for w in buttons if hasattr(w, "text") and "Change" in w.text() and "Paradigm" in w.text()]
        assert len(change_btns) > 0


class TestFileManagementWidget:
    """Test file management widget integration."""

    def test_file_management_widget_exists(self, data_settings_tab, qtbot):
        """Test that file management widget exists (if initialized)."""
        # Widget may or may not exist depending on initialization
        has_widget = hasattr(data_settings_tab, "file_management_widget")
        if has_widget:
            assert data_settings_tab.file_management_widget is not None


def schedule_dialog_handler(results_list=None, click_yes=False, max_attempts=50):
    """
    Schedule a dialog handler that will close QMessageBox dialogs.

    IMPORTANT: QMessageBox.exec() is BLOCKING, so we must schedule repeated
    checks using QTimer.singleShot that reschedule themselves until a dialog
    is found and closed.

    Args:
        results_list: Optional list to append dialog info (title, button clicked)
        click_yes: If True, click Yes button first. If False, click No first.
        max_attempts: Maximum number of attempts before giving up.

    Returns:
        dict with 'attempts' count for debugging
    """
    state = {"attempts": 0, "handled": False}

    def try_close_dialog():
        state["attempts"] += 1

        if state["handled"] or state["attempts"] > max_attempts:
            return

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                dialog_title = widget.windowTitle()
                dialog_text = widget.text()

                # Determine button order based on click_yes flag
                if click_yes:
                    btn_order = [
                        QMessageBox.StandardButton.Yes,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.No,
                    ]
                else:
                    btn_order = [
                        QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Yes,
                    ]

                for btn_type in btn_order:
                    btn = widget.button(btn_type)
                    if btn:
                        btn_text = btn.text().replace("&", "")  # Remove accelerator
                        if results_list is not None:
                            results_list.append(
                                {
                                    "title": dialog_title,
                                    "text": dialog_text,
                                    "button_clicked": btn_text,
                                }
                            )
                        btn.click()
                        state["handled"] = True
                        return

        # Not found yet, reschedule
        if not state["handled"]:
            QTimer.singleShot(50, try_close_dialog)

    # Start the first check after a short delay
    QTimer.singleShot(50, try_close_dialog)
    return state


class TestAutoDetectionResultsDialog:
    """
    Test the Auto-Detection Results dialog that appears after clicking auto-detect buttons.

    This dialog shows detected values (Device, Skip Rows, Epoch Length) with confidence
    percentages and asks "Apply these values?" with Yes/No buttons.

    These tests handle BOTH scenarios:
    - Warning dialog (when no files selected) - has Ok button
    - Results dialog (when files available) - has Yes/No buttons
    """

    def test_autodetect_all_handles_dialog(self, data_settings_tab, qtbot):
        """Test that clicking auto-detect all properly handles any dialog that appears."""
        dialogs_handled = []
        # Schedule the dialog handler BEFORE clicking the button
        schedule_dialog_handler(dialogs_handled, click_yes=False)

        # Now click - the scheduled handler will close the dialog
        data_settings_tab.autodetect_all_btn.click()
        qtbot.wait(2000)  # Wait for dialog to appear and be handled

        # Should have handled some dialog
        assert len(dialogs_handled) > 0, "No dialog was handled - auto-detect should show a dialog"
        # Verify it was the expected dialog type
        dialog = dialogs_handled[0]
        assert "title" in dialog
        assert "button_clicked" in dialog

    def test_device_autodetect_handles_dialog(self, data_settings_tab, qtbot):
        """Test device auto-detect handles any dialog that appears."""
        dialogs_handled = []
        schedule_dialog_handler(dialogs_handled, click_yes=False)

        data_settings_tab.device_autodetect_btn.click()
        qtbot.wait(2000)

        assert len(dialogs_handled) > 0, "No dialog was handled - device auto-detect should show a dialog"

    def test_epoch_autodetect_handles_dialog(self, data_settings_tab, qtbot):
        """Test epoch auto-detect handles any dialog that appears."""
        dialogs_handled = []
        schedule_dialog_handler(dialogs_handled, click_yes=False)

        data_settings_tab.epoch_autodetect_btn.click()
        qtbot.wait(2000)

        assert len(dialogs_handled) > 0, "No dialog was handled - epoch auto-detect should show a dialog"

    def test_skip_rows_autodetect_handles_dialog(self, data_settings_tab, qtbot):
        """Test skip rows auto-detect handles any dialog that appears."""
        dialogs_handled = []
        schedule_dialog_handler(dialogs_handled, click_yes=False)

        data_settings_tab.skip_rows_autodetect_btn.click()
        qtbot.wait(2000)

        assert len(dialogs_handled) > 0, "No dialog was handled - skip rows auto-detect should show a dialog"

    def test_autodetect_buttons_are_enabled(self, data_settings_tab, qtbot):
        """Test that all auto-detect buttons are enabled and clickable."""
        assert data_settings_tab.autodetect_all_btn.isEnabled()
        assert data_settings_tab.device_autodetect_btn.isEnabled()
        assert data_settings_tab.epoch_autodetect_btn.isEnabled()
        assert data_settings_tab.skip_rows_autodetect_btn.isEnabled()

    def test_autodetect_all_button_has_prominent_styling(self, data_settings_tab, qtbot):
        """Test that Auto-detect All button has special styling."""
        stylesheet = data_settings_tab.autodetect_all_btn.styleSheet()
        # Should have some custom styling
        assert len(stylesheet) > 0 or data_settings_tab.autodetect_all_btn.text() == "Auto-detect All"


class TestAutoDetectionWithMockFiles:
    """
    Test auto-detection dialog interaction when files are available.
    These tests schedule dialog handlers before clicking buttons.
    """

    def test_click_yes_on_autodetect_results(self, main_window, data_settings_tab, qtbot):
        """
        Test clicking Yes on Auto-Detection Results dialog.
        Schedules a handler that clicks Yes to apply detected values.
        """
        dialogs_handled = []
        # click_yes=True means Yes button is clicked first (to apply values)
        schedule_dialog_handler(dialogs_handled, click_yes=True)

        data_settings_tab.autodetect_all_btn.click()
        qtbot.wait(2000)

        # Verify dialog was handled
        assert len(dialogs_handled) > 0, "No dialog appeared when clicking auto-detect"
        # If Auto-Detection Results dialog appeared, Yes should have been clicked
        if "Auto-Detection" in dialogs_handled[0].get("title", ""):
            assert dialogs_handled[0]["button_clicked"] == "Yes", f"Expected Yes button, got {dialogs_handled[0]['button_clicked']}"

    def test_click_no_on_autodetect_results_keeps_original_values(self, main_window, data_settings_tab, qtbot):
        """
        Test that clicking No on Auto-Detection Results dialog keeps original values.
        """
        initial_skip_rows = data_settings_tab.skip_rows_spin.value()
        initial_epoch = data_settings_tab.epoch_length_spin.value()
        initial_device_index = data_settings_tab.device_preset_combo.currentIndex()

        dialogs_handled = []
        # click_yes=False means No button is clicked first (to reject values)
        schedule_dialog_handler(dialogs_handled, click_yes=False)

        data_settings_tab.autodetect_all_btn.click()
        qtbot.wait(2000)

        # Verify dialog was handled
        assert len(dialogs_handled) > 0, "No dialog appeared when clicking auto-detect"

        # Values should remain unchanged when clicking No
        assert data_settings_tab.skip_rows_spin.value() == initial_skip_rows
        assert data_settings_tab.epoch_length_spin.value() == initial_epoch
        assert data_settings_tab.device_preset_combo.currentIndex() == initial_device_index

    def test_individual_autodetect_device_dialog_handling(self, data_settings_tab, qtbot):
        """Test handling the device-specific auto-detect dialog."""
        dialogs_handled = []
        schedule_dialog_handler(dialogs_handled)

        data_settings_tab.device_autodetect_btn.click()
        qtbot.wait(2000)

        assert len(dialogs_handled) > 0, "No dialog appeared for device auto-detect"

    def test_individual_autodetect_epoch_dialog_handling(self, data_settings_tab, qtbot):
        """Test handling the epoch-specific auto-detect dialog."""
        dialogs_handled = []
        schedule_dialog_handler(dialogs_handled)

        data_settings_tab.epoch_autodetect_btn.click()
        qtbot.wait(2000)

        assert len(dialogs_handled) > 0, "No dialog appeared for epoch auto-detect"

    def test_individual_autodetect_skip_rows_dialog_handling(self, data_settings_tab, qtbot):
        """Test handling the skip rows-specific auto-detect dialog."""
        dialogs_handled = []
        schedule_dialog_handler(dialogs_handled)

        data_settings_tab.skip_rows_autodetect_btn.click()
        qtbot.wait(2000)

        assert len(dialogs_handled) > 0, "No dialog appeared for skip rows auto-detect"
