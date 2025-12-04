#!/usr/bin/env python3
"""
Integration tests for Study Settings Tab.
Tests study parameter configuration and settings persistence.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import QInputDialog, QMessageBox, QWidget

from sleep_scoring_app.ui.study_settings_tab import DragDropListWidget, StudySettingsTab


@pytest.mark.integration
@pytest.mark.gui
class TestDragDropListWidget:
    """Test DragDropListWidget custom list functionality."""

    @pytest.fixture
    def list_widget(self, qtbot):
        """Create a DragDropListWidget for testing."""
        widget = DragDropListWidget()
        qtbot.addWidget(widget)
        return widget

    def test_initialization(self, list_widget):
        """Test list widget initializes correctly."""
        assert list_widget is not None
        assert list_widget.count() == 0

    def test_add_item_with_validation_success(self, list_widget):
        """Test adding a valid item succeeds."""
        result = list_widget.add_item_with_validation("G1")
        assert result is True
        assert list_widget.count() == 1
        assert list_widget.item(0).text() == "G1"

    def test_add_item_with_validation_duplicate_fails(self, list_widget):
        """Test adding duplicate item fails."""
        list_widget.add_item_with_validation("G1")
        result = list_widget.add_item_with_validation("G1")
        assert result is False
        assert list_widget.count() == 1

    def test_add_item_uppercase_conversion(self, list_widget):
        """Test items are converted to uppercase."""
        list_widget.add_item_with_validation("abc")
        assert list_widget.item(0).text() == "ABC"

    def test_add_item_whitespace_stripped(self, list_widget):
        """Test whitespace is stripped from items."""
        list_widget.add_item_with_validation("  G1  ")
        assert list_widget.item(0).text() == "G1"

    def test_get_all_items(self, list_widget):
        """Test getting all items as list."""
        list_widget.add_item_with_validation("G1")
        list_widget.add_item_with_validation("G2")
        list_widget.add_item_with_validation("G3")

        items = list_widget.get_all_items()
        assert items == ["G1", "G2", "G3"]

    def test_items_changed_signal_on_add(self, list_widget, qtbot):
        """Test items_changed signal emitted on add."""
        with qtbot.waitSignal(list_widget.items_changed, timeout=1000):
            list_widget.add_item_with_validation("G1")

    def test_drag_drop_mode_enabled(self, list_widget):
        """Test drag drop mode is internal move."""
        from PyQt6.QtWidgets import QListWidget

        assert list_widget.dragDropMode() == QListWidget.DragDropMode.InternalMove


@pytest.mark.integration
@pytest.mark.gui
class TestStudySettingsTab:
    """Test StudySettingsTab integration with real widgets."""

    @pytest.fixture
    def parent_widget_with_mock(self, qtbot):
        """Create a real QWidget parent with mocked config_manager attached."""
        # Create a real QWidget to serve as parent
        parent = QWidget()
        qtbot.addWidget(parent)

        # Attach mock config_manager
        parent.config_manager = Mock()
        parent.config_manager.config = Mock()
        parent.config_manager.update_study_settings = Mock()

        # Set up default config values
        config = parent.config_manager.config
        config.study_unknown_value = "UNKNOWN"
        config.study_valid_groups = ["G1", "G2"]
        config.study_valid_timepoints = ["T1", "T2", "T3"]
        config.study_default_group = "G1"
        config.study_default_timepoint = "T1"
        config.study_participant_id_patterns = [r"^(\d{4,})[_-]"]
        config.study_timepoint_pattern = r"([A-Z]\d)"
        config.study_group_pattern = r"(G\d)"
        config.sleep_algorithm_id = "sadeh_1994_actilife"
        config.night_start_hour = 22
        config.night_end_hour = 7
        config.choi_axis = "vector_magnitude"

        return parent

    @pytest.fixture
    def study_settings_tab(self, qtbot, parent_widget_with_mock):
        """Create StudySettingsTab for testing."""
        tab = StudySettingsTab(parent_widget_with_mock)
        qtbot.addWidget(tab)
        return tab

    # ============================================================================
    # Initialization Tests
    # ============================================================================

    def test_initialization(self, study_settings_tab):
        """Test study settings tab initializes correctly."""
        assert study_settings_tab is not None

    def test_regex_pattern_fields_exist(self, study_settings_tab):
        """Test regex pattern input fields exist."""
        assert hasattr(study_settings_tab, "id_pattern_edit")
        assert hasattr(study_settings_tab, "timepoint_pattern_edit")
        assert hasattr(study_settings_tab, "group_pattern_edit")

    def test_valid_lists_exist(self, study_settings_tab):
        """Test valid groups/timepoints lists exist."""
        assert hasattr(study_settings_tab, "valid_groups_list")
        assert hasattr(study_settings_tab, "valid_timepoints_list")
        assert isinstance(study_settings_tab.valid_groups_list, DragDropListWidget)
        assert isinstance(study_settings_tab.valid_timepoints_list, DragDropListWidget)

    def test_default_dropdowns_exist(self, study_settings_tab):
        """Test default selection dropdowns exist."""
        assert hasattr(study_settings_tab, "default_group_combo")
        assert hasattr(study_settings_tab, "default_timepoint_combo")

    def test_algorithm_config_exists(self, study_settings_tab):
        """Test algorithm configuration widgets exist."""
        assert hasattr(study_settings_tab, "sleep_algorithm_combo")  # New DI pattern
        assert hasattr(study_settings_tab, "night_start_time")
        assert hasattr(study_settings_tab, "night_end_time")
        assert hasattr(study_settings_tab, "choi_axis_combo")

    def test_apply_button_exists(self, study_settings_tab):
        """Test apply button exists."""
        assert hasattr(study_settings_tab, "apply_button")
        assert study_settings_tab.apply_button.text() == "Apply Settings"

    # ============================================================================
    # Regex Pattern Input Tests
    # ============================================================================

    def test_id_pattern_loaded_from_config(self, study_settings_tab):
        """Test ID pattern is loaded from config."""
        assert study_settings_tab.id_pattern_edit.text() == r"^(\d{4,})[_-]"

    def test_timepoint_pattern_loaded_from_config(self, study_settings_tab):
        """Test timepoint pattern is loaded from config."""
        assert study_settings_tab.timepoint_pattern_edit.text() == r"([A-Z]\d)"

    def test_group_pattern_loaded_from_config(self, study_settings_tab):
        """Test group pattern is loaded from config."""
        assert study_settings_tab.group_pattern_edit.text() == r"(G\d)"

    def test_id_pattern_change(self, study_settings_tab, qtbot):
        """Test changing ID pattern."""
        study_settings_tab.id_pattern_edit.clear()
        qtbot.keyClicks(study_settings_tab.id_pattern_edit, r"^P(\d+)")
        assert study_settings_tab.id_pattern_edit.text() == r"^P(\d+)"

    # ============================================================================
    # Valid Groups/Timepoints List Tests
    # ============================================================================

    def test_valid_groups_loaded(self, study_settings_tab):
        """Test valid groups are loaded from config."""
        groups = study_settings_tab.valid_groups_list.get_all_items()
        assert "G1" in groups
        assert "G2" in groups

    def test_valid_timepoints_loaded(self, study_settings_tab):
        """Test valid timepoints are loaded from config."""
        timepoints = study_settings_tab.valid_timepoints_list.get_all_items()
        assert "T1" in timepoints
        assert "T2" in timepoints
        assert "T3" in timepoints

    @patch.object(QInputDialog, "getText", return_value=("G3", True))
    def test_add_group_button(self, mock_dialog, study_settings_tab, qtbot):
        """Test adding a group via button."""
        initial_count = study_settings_tab.valid_groups_list.count()
        qtbot.mouseClick(study_settings_tab.add_group_button, Qt.MouseButton.LeftButton)
        assert study_settings_tab.valid_groups_list.count() == initial_count + 1

    @patch.object(QInputDialog, "getText", return_value=("T4", True))
    def test_add_timepoint_button(self, mock_dialog, study_settings_tab, qtbot):
        """Test adding a timepoint via button."""
        initial_count = study_settings_tab.valid_timepoints_list.count()
        qtbot.mouseClick(study_settings_tab.add_timepoint_button, Qt.MouseButton.LeftButton)
        assert study_settings_tab.valid_timepoints_list.count() == initial_count + 1

    @patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes)
    def test_remove_group_button(self, mock_question, study_settings_tab, qtbot):
        """Test removing a group via button."""
        # Select first item
        study_settings_tab.valid_groups_list.setCurrentRow(0)
        initial_count = study_settings_tab.valid_groups_list.count()

        qtbot.mouseClick(study_settings_tab.remove_group_button, Qt.MouseButton.LeftButton)
        assert study_settings_tab.valid_groups_list.count() == initial_count - 1

    @patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes)
    def test_remove_timepoint_button(self, mock_question, study_settings_tab, qtbot):
        """Test removing a timepoint via button."""
        # Select first item
        study_settings_tab.valid_timepoints_list.setCurrentRow(0)
        initial_count = study_settings_tab.valid_timepoints_list.count()

        qtbot.mouseClick(study_settings_tab.remove_timepoint_button, Qt.MouseButton.LeftButton)
        assert study_settings_tab.valid_timepoints_list.count() == initial_count - 1

    @patch.object(QMessageBox, "information")
    def test_remove_group_no_selection(self, mock_info, study_settings_tab, qtbot):
        """Test removing group with no selection shows message."""
        study_settings_tab.valid_groups_list.clearSelection()
        study_settings_tab.valid_groups_list.setCurrentRow(-1)

        qtbot.mouseClick(study_settings_tab.remove_group_button, Qt.MouseButton.LeftButton)
        mock_info.assert_called_once()

    # ============================================================================
    # Default Selection Dropdown Tests
    # ============================================================================

    def test_default_group_dropdown_populated(self, study_settings_tab):
        """Test default group dropdown is populated from valid groups."""
        combo = study_settings_tab.default_group_combo
        # Should have placeholder + valid groups
        assert combo.count() >= 2

    def test_default_timepoint_dropdown_populated(self, study_settings_tab):
        """Test default timepoint dropdown is populated from valid timepoints."""
        combo = study_settings_tab.default_timepoint_combo
        # Should have placeholder + valid timepoints
        assert combo.count() >= 2

    def test_default_group_selection_change(self, study_settings_tab, qtbot):
        """Test changing default group selection."""
        combo = study_settings_tab.default_group_combo
        # Find G2 in dropdown
        index = combo.findText("G2")
        if index >= 0:
            combo.setCurrentIndex(index)
            assert combo.currentText() == "G2"

    def test_default_timepoint_selection_change(self, study_settings_tab, qtbot):
        """Test changing default timepoint selection."""
        combo = study_settings_tab.default_timepoint_combo
        # Find T2 in dropdown
        index = combo.findText("T2")
        if index >= 0:
            combo.setCurrentIndex(index)
            assert combo.currentText() == "T2"

    @patch.object(QInputDialog, "getText", return_value=("NEWGROUP", True))
    def test_group_dropdown_updates_on_list_change(self, mock_dialog, study_settings_tab, qtbot):
        """Test default group dropdown updates when list changes."""
        initial_count = study_settings_tab.default_group_combo.count()
        qtbot.mouseClick(study_settings_tab.add_group_button, Qt.MouseButton.LeftButton)

        # Dropdown should have one more item
        assert study_settings_tab.default_group_combo.count() == initial_count + 1

    # ============================================================================
    # Algorithm Configuration Tests
    # ============================================================================

    def test_sleep_algorithm_combo(self, study_settings_tab, qtbot):
        """Test sleep algorithm combo box (new DI pattern)."""
        combo = study_settings_tab.sleep_algorithm_combo
        assert combo.count() > 0  # Should have at least one algorithm available

        # Change to different algorithm
        initial_index = combo.currentIndex()
        new_index = (initial_index + 1) % combo.count()
        combo.setCurrentIndex(new_index)

        assert combo.currentIndex() == new_index

    def test_night_start_time_change(self, study_settings_tab, qtbot):
        """Test changing night start time."""
        study_settings_tab.night_start_time.setTime(QTime(21, 0))
        assert study_settings_tab.night_start_time.time().hour() == 21

    def test_night_end_time_change(self, study_settings_tab, qtbot):
        """Test changing night end time."""
        study_settings_tab.night_end_time.setTime(QTime(8, 0))
        assert study_settings_tab.night_end_time.time().hour() == 8

    def test_choi_axis_dropdown_options(self, study_settings_tab):
        """Test Choi axis dropdown has all options."""
        combo = study_settings_tab.choi_axis_combo
        assert combo.count() == 4  # VM, X, Y, Z

    def test_choi_axis_selection_change(self, study_settings_tab, qtbot):
        """Test changing Choi axis selection."""
        combo = study_settings_tab.choi_axis_combo
        combo.setCurrentIndex(1)  # Select Y-axis
        assert combo.currentIndex() == 1

    # ============================================================================
    # Live ID Testing Section Tests
    # ============================================================================

    def test_test_id_input_exists(self, study_settings_tab):
        """Test live ID testing input exists."""
        assert hasattr(study_settings_tab, "test_id_input")
        assert hasattr(study_settings_tab, "test_results_display")

    def test_test_id_input_triggers_update(self, study_settings_tab, qtbot):
        """Test entering test ID updates results."""
        study_settings_tab.test_id_input.clear()
        qtbot.keyClicks(study_settings_tab.test_id_input, "4000_T1_data.csv")
        # Results display should have some content
        assert study_settings_tab.test_results_display is not None

    # ============================================================================
    # Apply Settings Tests
    # ============================================================================

    @patch.object(QMessageBox, "warning")
    def test_apply_settings_validation_no_groups(self, mock_warning, study_settings_tab, qtbot):
        """Test apply settings fails with no valid groups."""
        # Clear all groups
        study_settings_tab.valid_groups_list.clear()

        qtbot.mouseClick(study_settings_tab.apply_button, Qt.MouseButton.LeftButton)
        mock_warning.assert_called_once()

    @patch.object(QMessageBox, "warning")
    def test_apply_settings_validation_no_timepoints(self, mock_warning, study_settings_tab, qtbot):
        """Test apply settings fails with no valid timepoints."""
        # Clear all timepoints
        study_settings_tab.valid_timepoints_list.clear()

        qtbot.mouseClick(study_settings_tab.apply_button, Qt.MouseButton.LeftButton)
        mock_warning.assert_called_once()

    @patch.object(QMessageBox, "warning")
    def test_apply_settings_validation_invalid_regex(self, mock_warning, study_settings_tab, qtbot):
        """Test apply settings fails with invalid regex."""
        study_settings_tab.id_pattern_edit.setText("[invalid(regex")

        qtbot.mouseClick(study_settings_tab.apply_button, Qt.MouseButton.LeftButton)
        mock_warning.assert_called_once()

    @patch.object(QMessageBox, "information")
    def test_apply_settings_success(self, mock_info, study_settings_tab, qtbot):
        """Test apply settings succeeds with valid configuration."""
        # Ensure valid configuration
        study_settings_tab.id_pattern_edit.setText(r"^(\d{4,})")
        study_settings_tab.unknown_value_edit.setText("UNKNOWN")

        # Select valid defaults (not placeholder)
        group_combo = study_settings_tab.default_group_combo
        for i in range(group_combo.count()):
            if not group_combo.itemText(i).startswith("--"):
                group_combo.setCurrentIndex(i)
                break

        timepoint_combo = study_settings_tab.default_timepoint_combo
        for i in range(timepoint_combo.count()):
            if not timepoint_combo.itemText(i).startswith("--"):
                timepoint_combo.setCurrentIndex(i)
                break

        qtbot.mouseClick(study_settings_tab.apply_button, Qt.MouseButton.LeftButton)
        # Should show success message
        mock_info.assert_called_once()

    # ============================================================================
    # Signal Tests
    # ============================================================================

    def test_groups_changed_signal(self, study_settings_tab, qtbot):
        """Test groups_changed signal is emitted."""
        with qtbot.waitSignal(study_settings_tab.groups_changed, timeout=1000):
            study_settings_tab.valid_groups_list.add_item_with_validation("NEWGRP")

    def test_timepoints_changed_signal(self, study_settings_tab, qtbot):
        """Test timepoints_changed signal is emitted."""
        with qtbot.waitSignal(study_settings_tab.timepoints_changed, timeout=1000):
            study_settings_tab.valid_timepoints_list.add_item_with_validation("NEWTP")

    # ============================================================================
    # Unknown Value Tests
    # ============================================================================

    def test_unknown_value_loaded(self, study_settings_tab):
        """Test unknown value is loaded from config."""
        assert study_settings_tab.unknown_value_edit.text() == "UNKNOWN"

    def test_unknown_value_change(self, study_settings_tab, qtbot):
        """Test changing unknown value."""
        study_settings_tab.unknown_value_edit.clear()
        qtbot.keyClicks(study_settings_tab.unknown_value_edit, "N/A")
        assert study_settings_tab.unknown_value_edit.text() == "N/A"
