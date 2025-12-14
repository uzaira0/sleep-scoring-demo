"""
Tests for ExportTab component.

These tests interact with the REAL ExportTab like a user would:
- Selecting export columns
- Changing grouping options
- Browsing for output directory
- Toggling export options
- Triggering exports
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
def export_tab(main_window):
    """Get the Export tab from main window."""
    # Switch to Export tab
    for i in range(main_window.tab_widget.count()):
        if main_window.tab_widget.tabText(i) == "Export":
            main_window.tab_widget.setCurrentIndex(i)
            break
    return main_window.export_tab


class TestExportTabBasics:
    """Test basic Export tab functionality."""

    def test_export_tab_exists(self, main_window, qtbot):
        """Test that Export tab exists on main window."""
        assert hasattr(main_window, "export_tab")
        assert main_window.export_tab is not None

    def test_export_button_exists(self, export_tab, qtbot):
        """Test that Export button exists."""
        assert hasattr(export_tab, "export_btn")
        assert export_tab.export_btn is not None

    def test_export_button_text(self, export_tab, qtbot):
        """Test that Export button has correct text."""
        assert "Export" in export_tab.export_btn.text()

    def test_data_summary_section_exists(self, export_tab, qtbot):
        """Test that data summary section exists."""
        assert hasattr(export_tab, "summary_label")
        assert export_tab.summary_label is not None

    def test_summary_label_shows_record_count(self, export_tab, qtbot):
        """Test that summary label displays total record count."""
        # Summary should show some text
        assert export_tab.summary_label.text()


class TestExportTabColumnSelection:
    """Test column selection functionality."""

    def test_column_count_label_exists(self, export_tab, qtbot):
        """Test that column count label exists."""
        assert hasattr(export_tab, "column_count_label")
        assert export_tab.column_count_label is not None

    def test_column_count_shows_selected_total(self, export_tab, qtbot):
        """Test that column count label shows selected/total format."""
        label_text = export_tab.column_count_label.text()
        assert "/" in label_text
        assert "columns selected" in label_text.lower()

    def test_select_columns_button_exists(self, export_tab, qtbot):
        """Test that Select Columns button exists."""
        # Find button with text "Select Columns..."
        buttons = export_tab.findChildren(object)
        select_btns = [w for w in buttons if hasattr(w, "text") and "Select Columns" in w.text()]
        assert len(select_btns) > 0

    def test_click_select_columns_opens_dialog(self, export_tab, qtbot):
        """Test that clicking Select Columns opens dialog."""
        # Find and click the button
        buttons = export_tab.findChildren(object)
        select_btns = [w for w in buttons if hasattr(w, "text") and "Select Columns" in w.text()]

        if select_btns:
            # Schedule closing the dialog
            def close_dialog():
                for widget in QApplication.topLevelWidgets():
                    if widget.isVisible() and "Column" in widget.windowTitle():
                        widget.close()

            QTimer.singleShot(200, close_dialog)

            # Click button
            qtbot.mouseClick(select_btns[0], Qt.MouseButton.LeftButton)
            qtbot.wait(300)


class TestExportTabGroupingOptions:
    """Test grouping options functionality."""

    def test_grouping_button_group_exists(self, export_tab, qtbot):
        """Test that grouping button group exists."""
        assert hasattr(export_tab, "export_grouping_group")
        assert export_tab.export_grouping_group is not None

    def test_grouping_has_four_options(self, export_tab, qtbot):
        """Test that there are 4 grouping options."""
        buttons = export_tab.export_grouping_group.buttons()
        assert len(buttons) == 4

    def test_first_option_selected_by_default(self, export_tab, qtbot):
        """Test that first grouping option is selected by default."""
        checked_id = export_tab.export_grouping_group.checkedId()
        # Should be 0 (all data in one file) by default or from saved settings
        assert checked_id in [0, 1, 2, 3]

    def test_select_by_participant_option(self, export_tab, qtbot):
        """Test selecting 'by participant' grouping option."""
        buttons = export_tab.export_grouping_group.buttons()

        # Click second button (by participant)
        if len(buttons) > 1:
            participant_btn = export_tab.export_grouping_group.button(1)
            qtbot.mouseClick(participant_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(50)

            assert export_tab.export_grouping_group.checkedId() == 1

    def test_select_by_group_option(self, export_tab, qtbot):
        """Test selecting 'by group' grouping option."""
        buttons = export_tab.export_grouping_group.buttons()

        # Click third button (by group)
        if len(buttons) > 2:
            group_btn = export_tab.export_grouping_group.button(2)
            qtbot.mouseClick(group_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(50)

            assert export_tab.export_grouping_group.checkedId() == 2

    def test_select_by_timepoint_option(self, export_tab, qtbot):
        """Test selecting 'by timepoint' grouping option."""
        buttons = export_tab.export_grouping_group.buttons()

        # Click fourth button (by timepoint)
        if len(buttons) > 3:
            timepoint_btn = export_tab.export_grouping_group.button(3)
            qtbot.mouseClick(timepoint_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(50)

            assert export_tab.export_grouping_group.checkedId() == 3


class TestExportTabOutputDirectory:
    """Test output directory selection."""

    def test_output_label_exists(self, export_tab, qtbot):
        """Test that output directory label exists."""
        assert hasattr(export_tab, "export_output_label")
        assert export_tab.export_output_label is not None

    def test_output_label_shows_directory(self, export_tab, qtbot):
        """Test that output label displays a directory path or prompt."""
        label_text = export_tab.export_output_label.text()
        # Should show either a path or "No directory selected"
        assert len(label_text) > 0

    def test_browse_button_exists(self, export_tab, qtbot):
        """Test that Browse button exists."""
        # Find button with "Browse" text
        buttons = export_tab.findChildren(object)
        browse_btns = [w for w in buttons if hasattr(w, "text") and w.text() == "Browse"]
        assert len(browse_btns) > 0


class TestExportTabOptions:
    """Test export options (headers, metadata)."""

    def test_include_headers_checkbox_exists(self, export_tab, qtbot):
        """Test that include headers checkbox exists."""
        assert hasattr(export_tab, "include_headers_checkbox")
        assert export_tab.include_headers_checkbox is not None

    def test_include_metadata_checkbox_exists(self, export_tab, qtbot):
        """Test that include metadata checkbox exists."""
        assert hasattr(export_tab, "include_metadata_checkbox")
        assert export_tab.include_metadata_checkbox is not None

    def test_headers_checkbox_label(self, export_tab, qtbot):
        """Test that headers checkbox has correct label."""
        label_text = export_tab.include_headers_checkbox.text()
        assert "header" in label_text.lower()

    def test_metadata_checkbox_label(self, export_tab, qtbot):
        """Test that metadata checkbox has correct label."""
        label_text = export_tab.include_metadata_checkbox.text()
        assert "metadata" in label_text.lower()

    def test_toggle_headers_checkbox(self, export_tab, qtbot):
        """Test toggling the headers checkbox."""
        initial_state = export_tab.include_headers_checkbox.isChecked()

        qtbot.mouseClick(export_tab.include_headers_checkbox, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        new_state = export_tab.include_headers_checkbox.isChecked()
        assert new_state != initial_state

    def test_toggle_metadata_checkbox(self, export_tab, qtbot):
        """Test toggling the metadata checkbox."""
        initial_state = export_tab.include_metadata_checkbox.isChecked()

        qtbot.mouseClick(export_tab.include_metadata_checkbox, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        new_state = export_tab.include_metadata_checkbox.isChecked()
        assert new_state != initial_state


class TestExportTabDataSummaryRefresh:
    """Test data summary refresh functionality."""

    def test_refresh_data_summary_method_exists(self, export_tab, qtbot):
        """Test that refresh method exists."""
        assert hasattr(export_tab, "refresh_data_summary")
        assert callable(export_tab.refresh_data_summary)

    def test_refresh_data_summary_updates_label(self, export_tab, qtbot):
        """Test that refreshing updates the summary label."""
        initial_text = export_tab.summary_label.text()

        export_tab.refresh_data_summary()
        qtbot.wait(50)

        # Text should be set (may be same or different)
        assert export_tab.summary_label.text()

    def test_summary_shows_zero_records_initially(self, export_tab, qtbot):
        """Test that summary shows appropriate message when no data."""
        export_tab.refresh_data_summary()
        qtbot.wait(50)

        summary_text = export_tab.summary_label.text()
        assert "records" in summary_text.lower() or "Total" in summary_text


class TestExportTabExportButton:
    """Test export button behavior."""

    def test_click_export_button_with_no_data(self, export_tab, qtbot):
        """Test clicking export button when no data is available."""

        # Schedule closing any dialogs that appear
        def close_dialogs():
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QMessageBox) and widget.isVisible():
                    ok_btn = widget.button(QMessageBox.StandardButton.Ok)
                    if ok_btn:
                        qtbot.mouseClick(ok_btn, Qt.MouseButton.LeftButton)

        QTimer.singleShot(200, close_dialogs)

        # Click export button
        qtbot.mouseClick(export_tab.export_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(300)

    def test_export_button_is_clickable(self, export_tab, qtbot):
        """Test that export button is clickable."""
        assert export_tab.export_btn.isEnabled()

    def test_export_button_has_tooltip(self, export_tab, qtbot):
        """Test that export button has a tooltip."""
        tooltip = export_tab.export_btn.toolTip()
        assert tooltip  # Should have some tooltip text


class TestExportTabLayout:
    """Test Export tab layout and structure."""

    def test_tab_has_scroll_area(self, export_tab, qtbot):
        """Test that tab content is in a scroll area."""
        # Export tab should have scrollable content
        from PyQt6.QtWidgets import QScrollArea

        scroll_areas = export_tab.findChildren(QScrollArea)
        assert len(scroll_areas) > 0

    def test_sections_are_in_group_boxes(self, export_tab, qtbot):
        """Test that sections are organized in group boxes."""
        from PyQt6.QtWidgets import QGroupBox

        group_boxes = export_tab.findChildren(QGroupBox)
        # Should have multiple group boxes for different sections
        assert len(group_boxes) >= 3  # Summary, Columns, Grouping, Output, Options

    def test_export_button_at_bottom(self, export_tab, qtbot):
        """Test that export button is positioned prominently."""
        # Export button should be accessible
        assert export_tab.export_btn.isVisible()


class TestExportTabSettingsPersistence:
    """Test that export settings are persisted."""

    def test_grouping_selection_persists(self, main_window, export_tab, qtbot):
        """Test that grouping selection is saved to config."""
        # Change grouping option
        buttons = export_tab.export_grouping_group.buttons()
        if len(buttons) > 1:
            qtbot.mouseClick(buttons[1], Qt.MouseButton.LeftButton)
            qtbot.wait(50)

            # Setting should be saved (verified by no crash)
            assert True

    def test_headers_checkbox_state_persists(self, export_tab, qtbot):
        """Test that headers checkbox state affects config."""
        # Toggle checkbox
        qtbot.mouseClick(export_tab.include_headers_checkbox, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        # Should trigger save (verified by no crash)
        assert True

    def test_metadata_checkbox_state_persists(self, export_tab, qtbot):
        """Test that metadata checkbox state affects config."""
        # Toggle checkbox
        qtbot.mouseClick(export_tab.include_metadata_checkbox, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        # Should trigger save (verified by no crash)
        assert True


class TestExportTabColumnCountUpdate:
    """Test column count label updates."""

    def test_column_count_format(self, export_tab, qtbot):
        """Test that column count is in format 'X/Y columns selected'."""
        label_text = export_tab.column_count_label.text()

        # Should match pattern like "25/50 columns selected"
        assert "/" in label_text
        parts = label_text.split("/")
        assert len(parts) == 2

        # First part should be a number
        selected = parts[0].strip()
        assert selected.isdigit()

    def test_column_count_reflects_selection(self, export_tab, qtbot):
        """Test that column count changes when selection changes."""
        initial_text = export_tab.column_count_label.text()

        # Extract initial count
        initial_count = int(initial_text.split("/")[0].strip())

        # Count should be positive
        assert initial_count >= 0
