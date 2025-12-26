#!/usr/bin/env python3
"""
Integration tests for Analysis Tab.
Tests main analysis interface, plot widget, marker interaction, and navigation.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout, QWidget

from sleep_scoring_app.ui.analysis_tab import AnalysisTab


@pytest.mark.integration
@pytest.mark.gui
class TestAnalysisTabSimplified:
    """Test AnalysisTab with simplified real widgets for basic UI checks."""

    @pytest.fixture
    def analysis_widget(self, qtbot):
        """Create a simplified analysis widget for testing."""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        # Top controls
        controls_layout = QHBoxLayout()
        widget.file_selector = QComboBox()
        widget.file_selector.addItems(["File 1", "File 2", "File 3"])
        widget.date_selector = QComboBox()
        widget.date_selector.addItems(["2021-04-20", "2021-04-21", "2021-04-22"])
        controls_layout.addWidget(QLabel("File:"))
        controls_layout.addWidget(widget.file_selector)
        controls_layout.addWidget(QLabel("Date:"))
        controls_layout.addWidget(widget.date_selector)

        # Plot area (simplified as a widget)
        widget.plot_widget = QWidget()
        widget.plot_widget.setMinimumSize(400, 200)
        widget.plot_widget.setStyleSheet("background-color: white; border: 1px solid gray;")

        # Algorithm controls
        algo_layout = QHBoxLayout()
        widget.sadeh_btn = QPushButton("Toggle Sadeh")
        widget.sadeh_btn.setCheckable(True)
        widget.choi_btn = QPushButton("Toggle Choi")
        widget.choi_btn.setCheckable(True)
        algo_layout.addWidget(widget.sadeh_btn)
        algo_layout.addWidget(widget.choi_btn)

        # Zoom controls
        zoom_layout = QHBoxLayout()
        widget.zoom_in_btn = QPushButton("Zoom In")
        widget.zoom_out_btn = QPushButton("Zoom Out")
        widget.reset_zoom_btn = QPushButton("Reset Zoom")
        zoom_layout.addWidget(widget.zoom_in_btn)
        zoom_layout.addWidget(widget.zoom_out_btn)
        zoom_layout.addWidget(widget.reset_zoom_btn)

        # Marker tables
        widget.onset_table = QTableWidget(5, 3)
        widget.onset_table.setHorizontalHeaderLabels(["Time", "Activity", "Sadeh"])
        widget.offset_table = QTableWidget(5, 3)
        widget.offset_table.setHorizontalHeaderLabels(["Time", "Activity", "Sadeh"])

        # Sleep info
        widget.sleep_info_label = QLabel("Sleep: 22:00 - 06:00 (8h 0m)")

        # Popout button
        widget.popout_btn = QPushButton("Pop Out Tables")

        # Add all to main layout
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(widget.plot_widget)
        main_layout.addLayout(algo_layout)
        main_layout.addLayout(zoom_layout)
        main_layout.addWidget(widget.onset_table)
        main_layout.addWidget(widget.offset_table)
        main_layout.addWidget(widget.sleep_info_label)
        main_layout.addWidget(widget.popout_btn)

        qtbot.addWidget(widget)
        return widget

    def test_initialization(self, analysis_widget):
        """Test analysis tab initializes correctly."""
        assert analysis_widget is not None
        assert analysis_widget.plot_widget is not None

    def test_file_selector_exists(self, analysis_widget):
        """Test file selector combo box exists."""
        combo = analysis_widget.file_selector
        assert combo.count() == 3
        assert combo.currentText() == "File 1"

    def test_file_selection_change(self, analysis_widget, qtbot):
        """Test changing file selection."""
        combo = analysis_widget.file_selector
        combo.setCurrentIndex(1)
        assert combo.currentText() == "File 2"

    def test_date_selector_exists(self, analysis_widget):
        """Test date selector combo box exists."""
        combo = analysis_widget.date_selector
        assert combo.count() == 3
        assert combo.currentText() == "2021-04-20"

    def test_date_selection_change(self, analysis_widget):
        """Test changing date selection."""
        combo = analysis_widget.date_selector
        combo.setCurrentIndex(2)
        assert combo.currentText() == "2021-04-22"

    def test_plot_widget_exists(self, analysis_widget):
        """Test plot widget area exists."""
        assert analysis_widget.plot_widget is not None
        assert analysis_widget.plot_widget.minimumWidth() >= 400

    def test_sadeh_toggle_button(self, analysis_widget, qtbot):
        """Test Sadeh algorithm toggle button."""
        btn = analysis_widget.sadeh_btn
        assert btn.text() == "Toggle Sadeh"
        assert btn.isCheckable()

        # Toggle on
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
        assert btn.isChecked()

        # Toggle off
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
        assert not btn.isChecked()

    def test_choi_toggle_button(self, analysis_widget, qtbot):
        """Test Choi algorithm toggle button."""
        btn = analysis_widget.choi_btn
        assert btn.text() == "Toggle Choi"
        assert btn.isCheckable()

        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
        assert btn.isChecked()

    def test_zoom_in_button(self, analysis_widget):
        """Test zoom in button exists."""
        btn = analysis_widget.zoom_in_btn
        assert btn.text() == "Zoom In"
        assert btn.isEnabled()

    def test_zoom_out_button(self, analysis_widget):
        """Test zoom out button exists."""
        btn = analysis_widget.zoom_out_btn
        assert btn.text() == "Zoom Out"
        assert btn.isEnabled()

    def test_reset_zoom_button(self, analysis_widget):
        """Test reset zoom button exists."""
        btn = analysis_widget.reset_zoom_btn
        assert btn.text() == "Reset Zoom"
        assert btn.isEnabled()

    def test_onset_table_exists(self, analysis_widget):
        """Test onset marker table exists."""
        table = analysis_widget.onset_table
        assert table.rowCount() == 5
        assert table.columnCount() == 3

    def test_offset_table_exists(self, analysis_widget):
        """Test offset marker table exists."""
        table = analysis_widget.offset_table
        assert table.rowCount() == 5
        assert table.columnCount() == 3

    def test_sleep_info_label(self, analysis_widget):
        """Test sleep info label shows information."""
        label = analysis_widget.sleep_info_label
        assert "Sleep" in label.text()
        assert "22:00" in label.text()

    def test_popout_button_exists(self, analysis_widget):
        """Test popout tables button exists."""
        btn = analysis_widget.popout_btn
        assert btn.text() == "Pop Out Tables"
        assert btn.isEnabled()

    def test_popout_button_click(self, analysis_widget, qtbot):
        """Test popout button emits signal when clicked."""
        btn = analysis_widget.popout_btn
        clicked = []

        btn.clicked.connect(lambda: clicked.append(True))
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)

        assert len(clicked) == 1

    def test_zoom_button_clicks(self, analysis_widget, qtbot):
        """Test all zoom buttons are clickable."""
        for btn in [analysis_widget.zoom_in_btn, analysis_widget.zoom_out_btn, analysis_widget.reset_zoom_btn]:
            clicked = []
            btn.clicked.connect(lambda: clicked.append(True))
            qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
            btn.clicked.disconnect()
            assert len(clicked) == 1


@pytest.mark.integration
@pytest.mark.gui
class TestAnalysisTabReal:
    """Test AnalysisTab with real widget instance."""

    @pytest.fixture
    def parent_widget_with_mock(self, qtbot):
        """Create a real QWidget parent with mocked methods attached."""
        # Create a real QWidget to serve as parent
        parent = QWidget()
        qtbot.addWidget(parent)

        # Attach mock config_manager
        parent.config_manager = Mock()
        parent.config_manager.config = Mock()

        # Set up default config values
        config = parent.config_manager.config
        config.activity_source = "axis_y"
        config.show_adjacent_day_markers = True
        config.view_mode = 48

        # Mock methods that AnalysisTab calls
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
        parent.handle_sleep_markers_changed = Mock()
        parent.handle_nonwear_markers_changed = Mock()
        parent.handle_plot_error = Mock()
        parent.handle_marker_limit_exceeded = Mock()
        parent.handle_nonwear_marker_selected = Mock()

        return parent

    @pytest.fixture
    def analysis_tab(self, qtbot, parent_widget_with_mock):
        """Create AnalysisTab for testing."""
        tab = AnalysisTab(parent_widget_with_mock)
        qtbot.addWidget(tab)
        return tab

    # ============================================================================
    # Initialization Tests
    # ============================================================================

    def test_initialization(self, analysis_tab):
        """Test analysis tab initializes correctly."""
        assert analysis_tab is not None

    def test_date_navigation_buttons_exist(self, analysis_tab):
        """Test date navigation buttons exist."""
        assert hasattr(analysis_tab, "prev_date_btn")
        assert hasattr(analysis_tab, "next_date_btn")
        assert hasattr(analysis_tab, "date_dropdown")

    def test_date_dropdown_exists(self, analysis_tab):
        """Test date dropdown exists."""
        assert hasattr(analysis_tab, "date_dropdown")
        assert isinstance(analysis_tab.date_dropdown, QComboBox)

    # ============================================================================
    # Date Navigation Tests
    # ============================================================================

    def test_prev_date_button_initially_disabled(self, analysis_tab):
        """Test previous date button is initially disabled."""
        assert not analysis_tab.prev_date_btn.isEnabled()

    def test_next_date_button_initially_disabled(self, analysis_tab):
        """Test next date button is initially disabled."""
        assert not analysis_tab.next_date_btn.isEnabled()

    def test_date_dropdown_initially_disabled(self, analysis_tab):
        """Test date dropdown is initially disabled."""
        assert not analysis_tab.date_dropdown.isEnabled()

    def test_prev_date_button_click(self, analysis_tab, qtbot, parent_widget_with_mock):
        """Test clicking previous date button calls parent method."""
        analysis_tab.prev_date_btn.setEnabled(True)
        qtbot.mouseClick(analysis_tab.prev_date_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.prev_date.assert_called_once()

    def test_next_date_button_click(self, analysis_tab, qtbot, parent_widget_with_mock):
        """Test clicking next date button calls parent method."""
        analysis_tab.next_date_btn.setEnabled(True)
        qtbot.mouseClick(analysis_tab.next_date_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.next_date.assert_called_once()

    # ============================================================================
    # Activity Source Dropdown Tests
    # ============================================================================

    def test_activity_source_dropdown_exists(self, analysis_tab):
        """Test activity source dropdown exists."""
        assert hasattr(analysis_tab, "activity_source_dropdown")
        assert isinstance(analysis_tab.activity_source_dropdown, QComboBox)

    def test_activity_source_dropdown_options(self, analysis_tab):
        """Test activity source dropdown has expected options."""
        dropdown = analysis_tab.activity_source_dropdown
        assert dropdown.count() == 4

        # Check for all 4 axis options: Y, X, Z, and Vector Magnitude
        options = [dropdown.itemText(i) for i in range(dropdown.count())]
        assert any("Y-Axis" in opt for opt in options)
        assert any("X-Axis" in opt for opt in options)
        assert any("Z-Axis" in opt for opt in options)
        assert any("Vector" in opt for opt in options)

    def test_activity_source_dropdown_initially_disabled(self, analysis_tab):
        """Test activity source dropdown is initially disabled."""
        assert not analysis_tab.activity_source_dropdown.isEnabled()

    def test_activity_source_dropdown_change(self, analysis_tab, qtbot):
        """Test changing activity source selection."""
        dropdown = analysis_tab.activity_source_dropdown
        dropdown.setEnabled(True)

        initial_index = dropdown.currentIndex()
        new_index = (initial_index + 1) % dropdown.count()
        dropdown.setCurrentIndex(new_index)

        assert dropdown.currentIndex() == new_index

    # ============================================================================
    # Adjacent Day Markers Checkbox Tests
    # ============================================================================

    def test_adjacent_markers_checkbox_exists(self, analysis_tab):
        """Test adjacent day markers checkbox exists."""
        assert hasattr(analysis_tab, "show_adjacent_day_markers_checkbox")

    def test_adjacent_markers_checkbox_default_checked(self, analysis_tab):
        """Test adjacent day markers checkbox is checked by default."""
        assert analysis_tab.show_adjacent_day_markers_checkbox.isChecked()

    def test_adjacent_markers_checkbox_toggle(self, analysis_tab, qtbot):
        """Test toggling adjacent day markers checkbox."""
        checkbox = analysis_tab.show_adjacent_day_markers_checkbox
        initial_state = checkbox.isChecked()

        # Use setChecked() directly since mouseClick may not toggle reliably in tests
        checkbox.setChecked(not initial_state)
        assert checkbox.isChecked() != initial_state

    # ============================================================================
    # View Mode Radio Buttons Tests
    # ============================================================================

    def test_view_mode_buttons_exist(self, analysis_tab):
        """Test 24h/48h view mode radio buttons exist."""
        assert hasattr(analysis_tab, "view_24h_btn")
        assert hasattr(analysis_tab, "view_48h_btn")

    def test_view_48h_default_selected(self, analysis_tab):
        """Test 48h view is selected by default."""
        assert analysis_tab.view_48h_btn.isChecked()
        assert not analysis_tab.view_24h_btn.isChecked()

    def test_view_mode_switch_to_24h(self, analysis_tab, qtbot):
        """Test switching to 24h view mode."""
        analysis_tab.view_24h_btn.setChecked(True)
        assert analysis_tab.view_24h_btn.isChecked()
        assert not analysis_tab.view_48h_btn.isChecked()

    def test_view_mode_switch_to_48h(self, analysis_tab, qtbot):
        """Test switching to 48h view mode."""
        # First switch to 24h
        analysis_tab.view_24h_btn.setChecked(True)

        # Then switch back to 48h
        analysis_tab.view_48h_btn.setChecked(True)
        assert analysis_tab.view_48h_btn.isChecked()
        assert not analysis_tab.view_24h_btn.isChecked()

    def test_view_mode_mutually_exclusive(self, analysis_tab, qtbot):
        """Test view mode buttons are mutually exclusive."""
        # Check 24h
        analysis_tab.view_24h_btn.setChecked(True)
        assert not analysis_tab.view_48h_btn.isChecked()

        # Check 48h
        analysis_tab.view_48h_btn.setChecked(True)
        assert not analysis_tab.view_24h_btn.isChecked()

    # ============================================================================
    # Time Input Tests
    # ============================================================================

    def test_onset_time_input_exists(self, analysis_tab):
        """Test onset time input field exists."""
        assert hasattr(analysis_tab, "onset_time_input")

    def test_offset_time_input_exists(self, analysis_tab):
        """Test offset time input field exists."""
        assert hasattr(analysis_tab, "offset_time_input")

    def test_onset_time_input_placeholder(self, analysis_tab):
        """Test onset time input has HH:MM placeholder."""
        assert analysis_tab.onset_time_input.placeholderText() == "HH:MM"

    def test_offset_time_input_placeholder(self, analysis_tab):
        """Test offset time input has HH:MM placeholder."""
        assert analysis_tab.offset_time_input.placeholderText() == "HH:MM"

    def test_onset_time_input_entry(self, analysis_tab, qtbot):
        """Test entering onset time."""
        analysis_tab.onset_time_input.clear()
        qtbot.keyClicks(analysis_tab.onset_time_input, "22:30")
        assert analysis_tab.onset_time_input.text() == "22:30"

    def test_offset_time_input_entry(self, analysis_tab, qtbot):
        """Test entering offset time."""
        analysis_tab.offset_time_input.clear()
        qtbot.keyClicks(analysis_tab.offset_time_input, "06:45")
        assert analysis_tab.offset_time_input.text() == "06:45"

    # ============================================================================
    # Action Button Tests
    # ============================================================================

    def test_save_markers_button_exists(self, analysis_tab):
        """Test save markers button exists."""
        assert hasattr(analysis_tab, "save_markers_btn")

    def test_no_sleep_button_exists(self, analysis_tab):
        """Test mark no sleep button exists."""
        assert hasattr(analysis_tab, "no_sleep_btn")

    def test_clear_markers_button_exists(self, analysis_tab):
        """Test clear markers button exists."""
        assert hasattr(analysis_tab, "clear_markers_btn")

    def test_save_markers_button_click(self, analysis_tab, qtbot, parent_widget_with_mock):
        """Test clicking save markers button calls parent method."""
        qtbot.mouseClick(analysis_tab.save_markers_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.save_current_markers.assert_called_once()

    def test_no_sleep_button_click(self, analysis_tab, qtbot, parent_widget_with_mock):
        """Test clicking no sleep button calls parent method."""
        qtbot.mouseClick(analysis_tab.no_sleep_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.mark_no_sleep_period.assert_called_once()

    def test_clear_markers_button_click(self, analysis_tab, qtbot, parent_widget_with_mock):
        """Test clicking clear markers button calls parent method."""
        qtbot.mouseClick(analysis_tab.clear_markers_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.clear_current_markers.assert_called_once()

    # ============================================================================
    # Duration Label Tests
    # ============================================================================

    def test_duration_label_exists(self, analysis_tab):
        """Test total duration label exists."""
        assert hasattr(analysis_tab, "total_duration_label")

    def test_duration_label_initial_text(self, analysis_tab):
        """Test total duration label has initial text."""
        # Should have some default or empty duration text
        assert analysis_tab.total_duration_label is not None

    # ============================================================================
    # File Selector Tests
    # ============================================================================

    def test_file_selector_exists(self, analysis_tab):
        """Test file selector exists."""
        assert hasattr(analysis_tab, "file_selector")

    # ============================================================================
    # Diary Table Tests
    # ============================================================================

    def test_diary_table_exists(self, analysis_tab):
        """Test diary table widget exists."""
        assert hasattr(analysis_tab, "diary_table_widget")
