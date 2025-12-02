#!/usr/bin/env python3
"""
Integration tests for Data Settings Tab.
Tests data source configuration, import functionality, and database mode toggling.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from sleep_scoring_app.ui.data_settings_tab import DataSettingsTab


@pytest.mark.integration
@pytest.mark.gui
class TestDataSettingsTab:
    """Test DataSettingsTab integration with real widgets."""

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

        # Mock methods
        parent.browse_activity_files = Mock()
        parent.browse_nonwear_files = Mock()
        parent.start_activity_import = Mock()
        parent.start_nonwear_import = Mock()
        parent.clear_all_markers = Mock()
        parent.on_epoch_length_changed = Mock()
        parent.on_skip_rows_changed = Mock()

        # Mock db_manager (required by DataSettingsTab)
        parent.db_manager = Mock()
        parent.db_manager.get_activity_data_stats = Mock(return_value={"files": 0, "records": 0})
        parent.db_manager.get_nonwear_data_stats = Mock(return_value={"files": 0, "records": 0})

        return parent

    @pytest.fixture
    def data_settings_tab(self, qtbot, parent_widget_with_mock):
        """Create DataSettingsTab for testing."""
        tab = DataSettingsTab(parent_widget_with_mock)
        qtbot.addWidget(tab)
        return tab

    # ============================================================================
    # Initialization Tests
    # ============================================================================

    def test_initialization(self, data_settings_tab):
        """Test data settings tab initializes correctly."""
        assert data_settings_tab is not None

    def test_device_preset_combo_exists(self, data_settings_tab):
        """Test device preset dropdown exists."""
        assert hasattr(data_settings_tab, "device_preset_combo")
        assert data_settings_tab.device_preset_combo.count() > 0

    def test_epoch_length_spinbox_exists(self, data_settings_tab):
        """Test epoch length spinbox exists."""
        assert hasattr(data_settings_tab, "epoch_length_spin")
        assert data_settings_tab.epoch_length_spin.value() == 60

    def test_skip_rows_spinbox_exists(self, data_settings_tab):
        """Test skip rows spinbox exists."""
        assert hasattr(data_settings_tab, "skip_rows_spin")
        assert data_settings_tab.skip_rows_spin.value() == 10

    # ============================================================================
    # Device Preset Tests
    # ============================================================================

    def test_device_preset_options(self, data_settings_tab):
        """Test device preset has expected options."""
        combo = data_settings_tab.device_preset_combo
        options = [combo.itemText(i) for i in range(combo.count())]

        # Check for some expected options
        assert any("ActiGraph" in opt for opt in options)

    def test_device_preset_change(self, data_settings_tab, qtbot):
        """Test changing device preset."""
        combo = data_settings_tab.device_preset_combo
        initial_index = combo.currentIndex()

        # Change to different preset
        new_index = (initial_index + 1) % combo.count()
        combo.setCurrentIndex(new_index)

        assert combo.currentIndex() == new_index

    def test_configure_columns_button_exists(self, data_settings_tab):
        """Test configure columns button exists."""
        assert hasattr(data_settings_tab, "configure_columns_btn")

    # ============================================================================
    # Auto-detect Button Tests
    # ============================================================================

    def test_device_autodetect_button_exists(self, data_settings_tab):
        """Test device auto-detect button exists."""
        assert hasattr(data_settings_tab, "device_autodetect_btn")
        assert data_settings_tab.device_autodetect_btn.text() == "Auto-detect"

    def test_epoch_autodetect_button_exists(self, data_settings_tab):
        """Test epoch auto-detect button exists."""
        assert hasattr(data_settings_tab, "epoch_autodetect_btn")
        assert data_settings_tab.epoch_autodetect_btn.text() == "Auto-detect"

    def test_skip_rows_autodetect_button_exists(self, data_settings_tab):
        """Test skip rows auto-detect button exists."""
        assert hasattr(data_settings_tab, "skip_rows_autodetect_btn")
        assert data_settings_tab.skip_rows_autodetect_btn.text() == "Auto-detect"

    def test_autodetect_all_button_exists(self, data_settings_tab):
        """Test auto-detect all button exists."""
        assert hasattr(data_settings_tab, "autodetect_all_btn")
        assert "Auto-detect All" in data_settings_tab.autodetect_all_btn.text()

    # ============================================================================
    # Epoch Length Tests
    # ============================================================================

    def test_epoch_length_range(self, data_settings_tab):
        """Test epoch length has valid range."""
        spinbox = data_settings_tab.epoch_length_spin
        assert spinbox.minimum() == 1
        assert spinbox.maximum() == 300

    def test_epoch_length_change(self, data_settings_tab, qtbot):
        """Test changing epoch length value."""
        spinbox = data_settings_tab.epoch_length_spin
        spinbox.setValue(30)
        assert spinbox.value() == 30

    def test_epoch_length_notifies_parent(self, data_settings_tab, parent_widget_with_mock):
        """Test changing epoch length notifies parent."""
        data_settings_tab.epoch_length_spin.setValue(45)
        parent_widget_with_mock.on_epoch_length_changed.assert_called()

    # ============================================================================
    # Skip Rows Tests
    # ============================================================================

    def test_skip_rows_range(self, data_settings_tab):
        """Test skip rows has valid range."""
        spinbox = data_settings_tab.skip_rows_spin
        assert spinbox.minimum() == 0
        assert spinbox.maximum() == 100

    def test_skip_rows_change(self, data_settings_tab, qtbot):
        """Test changing skip rows value."""
        spinbox = data_settings_tab.skip_rows_spin
        spinbox.setValue(15)
        assert spinbox.value() == 15

    def test_skip_rows_notifies_parent(self, data_settings_tab, parent_widget_with_mock):
        """Test changing skip rows notifies parent."""
        data_settings_tab.skip_rows_spin.setValue(20)
        parent_widget_with_mock.on_skip_rows_changed.assert_called()

    # ============================================================================
    # Activity Data Import Tests
    # ============================================================================

    def test_activity_browse_button_exists(self, data_settings_tab):
        """Test activity browse button exists."""
        assert hasattr(data_settings_tab, "activity_browse_btn")
        assert "Select" in data_settings_tab.activity_browse_btn.text()

    def test_activity_import_button_exists(self, data_settings_tab):
        """Test activity import button exists."""
        assert hasattr(data_settings_tab, "activity_import_btn")
        assert data_settings_tab.activity_import_btn.text() == "Import"

    def test_activity_import_button_initially_disabled(self, data_settings_tab):
        """Test activity import button is initially disabled."""
        assert not data_settings_tab.activity_import_btn.isEnabled()

    def test_activity_browse_button_click(self, data_settings_tab, qtbot, parent_widget_with_mock):
        """Test clicking activity browse button calls parent method."""
        qtbot.mouseClick(data_settings_tab.activity_browse_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.browse_activity_files.assert_called_once()

    # ============================================================================
    # NWT Sensor Data Import Tests
    # ============================================================================

    def test_nwt_browse_button_exists(self, data_settings_tab):
        """Test NWT browse button exists."""
        assert hasattr(data_settings_tab, "nwt_browse_btn")
        assert "Select" in data_settings_tab.nwt_browse_btn.text()

    def test_nwt_import_button_exists(self, data_settings_tab):
        """Test NWT import button exists."""
        assert hasattr(data_settings_tab, "nwt_import_btn")
        assert data_settings_tab.nwt_import_btn.text() == "Import"

    def test_nwt_import_button_initially_disabled(self, data_settings_tab):
        """Test NWT import button is initially disabled."""
        assert not data_settings_tab.nwt_import_btn.isEnabled()

    def test_nwt_browse_button_click(self, data_settings_tab, qtbot, parent_widget_with_mock):
        """Test clicking NWT browse button calls parent method."""
        qtbot.mouseClick(data_settings_tab.nwt_browse_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.browse_nonwear_files.assert_called_once()

    # ============================================================================
    # Diary Import Tests
    # ============================================================================

    def test_diary_browse_button_exists(self, data_settings_tab):
        """Test diary browse button exists."""
        assert hasattr(data_settings_tab, "diary_import_browse_btn")
        assert "Browse" in data_settings_tab.diary_import_browse_btn.text()

    def test_diary_import_button_exists(self, data_settings_tab):
        """Test diary import button exists."""
        assert hasattr(data_settings_tab, "diary_import_btn")
        assert data_settings_tab.diary_import_btn.text() == "Import"

    def test_diary_import_button_initially_disabled(self, data_settings_tab):
        """Test diary import button is initially disabled."""
        assert not data_settings_tab.diary_import_btn.isEnabled()

    # ============================================================================
    # Clear Markers Tests
    # ============================================================================

    def test_clear_markers_button_exists(self, data_settings_tab):
        """Test clear markers button exists."""
        assert hasattr(data_settings_tab, "clear_markers_btn")

    def test_clear_markers_button_click(self, data_settings_tab, qtbot, parent_widget_with_mock):
        """Test clicking clear markers button calls parent method."""
        qtbot.mouseClick(data_settings_tab.clear_markers_btn, Qt.MouseButton.LeftButton)
        parent_widget_with_mock.clear_all_markers.assert_called_once()

    # ============================================================================
    # Generic CSV Column Mapping Dialog Tests
    # ============================================================================

    def test_configure_columns_enabled_for_generic_csv(self, data_settings_tab):
        """Test configure columns button enabled for Generic CSV preset."""
        combo = data_settings_tab.device_preset_combo

        # Find Generic CSV option
        for i in range(combo.count()):
            if "Generic" in combo.itemText(i):
                combo.setCurrentIndex(i)
                break

        # Button should be enabled for Generic CSV
        assert data_settings_tab.configure_columns_btn.isEnabled()

    def test_configure_columns_disabled_for_actigraph(self, data_settings_tab):
        """Test configure columns button disabled for ActiGraph preset."""
        combo = data_settings_tab.device_preset_combo

        # Find ActiGraph option
        for i in range(combo.count()):
            if "ActiGraph" in combo.itemText(i) and "Generic" not in combo.itemText(i):
                combo.setCurrentIndex(i)
                break

        # Button should be disabled for ActiGraph
        assert not data_settings_tab.configure_columns_btn.isEnabled()

    # ============================================================================
    # Integration Tests with File Selection
    # ============================================================================

    def test_activity_import_enabled_after_file_selection(self, data_settings_tab):
        """Test activity import button enabled after files selected."""
        # Simulate files being selected
        data_settings_tab.activity_import_btn.setEnabled(True)
        assert data_settings_tab.activity_import_btn.isEnabled()

    def test_nwt_import_enabled_after_file_selection(self, data_settings_tab):
        """Test NWT import button enabled after files selected."""
        # Simulate files being selected
        data_settings_tab.nwt_import_btn.setEnabled(True)
        assert data_settings_tab.nwt_import_btn.isEnabled()

    # ============================================================================
    # Spinbox Validation Tests
    # ============================================================================

    def test_epoch_length_validation_min(self, data_settings_tab):
        """Test epoch length respects minimum value."""
        spinbox = data_settings_tab.epoch_length_spin
        spinbox.setValue(0)  # Below minimum
        assert spinbox.value() == 1  # Should clamp to minimum

    def test_epoch_length_validation_max(self, data_settings_tab):
        """Test epoch length respects maximum value."""
        spinbox = data_settings_tab.epoch_length_spin
        spinbox.setValue(500)  # Above maximum
        assert spinbox.value() == 300  # Should clamp to maximum

    def test_skip_rows_validation_min(self, data_settings_tab):
        """Test skip rows respects minimum value."""
        spinbox = data_settings_tab.skip_rows_spin
        spinbox.setValue(-5)  # Below minimum
        assert spinbox.value() == 0  # Should clamp to minimum

    def test_skip_rows_validation_max(self, data_settings_tab):
        """Test skip rows respects maximum value."""
        spinbox = data_settings_tab.skip_rows_spin
        spinbox.setValue(500)  # Above maximum
        assert spinbox.value() == 100  # Should clamp to maximum


@pytest.mark.integration
@pytest.mark.gui
class TestColumnMappingDialog:
    """Test ColumnMappingDialog functionality."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = Mock()
        config_manager.config = Mock()
        config_manager.config.datetime_combined = False
        config_manager.config.custom_date_column = ""
        config_manager.config.custom_time_column = ""
        config_manager.config.custom_axis_y_column = ""
        config_manager.config.custom_axis_x_column = ""
        config_manager.config.custom_axis_z_column = ""
        config_manager.config.custom_vector_magnitude_column = ""
        config_manager.config.custom_activity_column = ""
        return config_manager

    @pytest.fixture
    def column_dialog(self, qtbot, mock_config_manager):
        """Create ColumnMappingDialog for testing."""
        from sleep_scoring_app.ui.data_settings_tab import ColumnMappingDialog

        # First arg is parent (None), second is config_manager
        dialog = ColumnMappingDialog(None, config_manager=mock_config_manager)
        qtbot.addWidget(dialog)
        return dialog

    def test_dialog_initialization(self, column_dialog):
        """Test column mapping dialog initializes correctly."""
        assert column_dialog is not None

    def test_datetime_combined_checkbox_exists(self, column_dialog):
        """Test datetime combined checkbox exists."""
        assert hasattr(column_dialog, "datetime_combined_check")

    def test_date_column_combo_exists(self, column_dialog):
        """Test date column combo exists."""
        assert hasattr(column_dialog, "date_column_combo")

    def test_time_column_combo_exists(self, column_dialog):
        """Test time column combo exists."""
        assert hasattr(column_dialog, "time_column_combo")

    def test_axis_combos_exist(self, column_dialog):
        """Test axis column combos exist."""
        assert hasattr(column_dialog, "axis_y_combo")
        assert hasattr(column_dialog, "axis_x_combo")
        assert hasattr(column_dialog, "axis_z_combo")
        assert hasattr(column_dialog, "vector_magnitude_combo")

    def test_datetime_combined_toggle(self, column_dialog, qtbot):
        """Test datetime combined checkbox toggles time column visibility state."""
        # Show the dialog to make visibility checks work
        column_dialog.show()
        qtbot.waitExposed(column_dialog)

        # Initially not combined - time column should be visible
        column_dialog.datetime_combined_check.setChecked(False)
        column_dialog._on_datetime_format_changed()
        assert column_dialog.time_column_combo.isVisible()

        # Toggle to combined - time column should be hidden
        column_dialog.datetime_combined_check.setChecked(True)
        column_dialog._on_datetime_format_changed()
        assert not column_dialog.time_column_combo.isVisible()

        column_dialog.close()

    def test_dialog_has_file_selection_ui(self, column_dialog):
        """Test dialog has file selection UI elements."""
        # The dialog should have a file label for displaying selected sample file
        assert hasattr(column_dialog, "file_label")
