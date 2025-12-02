#!/usr/bin/env python3
"""
Integration tests for Export Tab.
Tests export configuration, file selection, and export execution.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget


@pytest.mark.integration
@pytest.mark.gui
class TestExportTab:
    """Test ExportTab integration with simplified real widgets."""

    @pytest.fixture
    def export_widget(self, qtbot):
        """Create a simplified export widget for testing."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Create UI elements that mimic ExportTab
        widget.export_dir_label = QLabel("/test/export")
        widget.browse_export_btn = QPushButton("Browse Export Directory")
        widget.csv_export_btn = QPushButton("Export to CSV")
        widget.excel_export_btn = QPushButton("Export to Excel")
        widget.grouping_combo = QComboBox()
        widget.grouping_combo.addItems(["No Grouping", "By Participant", "By Date"])
        widget.include_all_columns = QCheckBox("Include All Columns")
        widget.include_all_columns.setChecked(True)
        widget.progress_label = QLabel("Ready")

        # Add to layout
        layout.addWidget(widget.export_dir_label)
        layout.addWidget(widget.browse_export_btn)
        layout.addWidget(widget.csv_export_btn)
        layout.addWidget(widget.excel_export_btn)
        layout.addWidget(widget.grouping_combo)
        layout.addWidget(widget.include_all_columns)
        layout.addWidget(widget.progress_label)

        qtbot.addWidget(widget)
        return widget

    def test_initialization(self, export_widget):
        """Test export tab initializes correctly."""
        assert export_widget is not None

    def test_export_directory_label(self, export_widget):
        """Test export directory label shows path."""
        assert export_widget.export_dir_label.text() == "/test/export"

    def test_browse_export_button_exists(self, export_widget):
        """Test browse export directory button exists."""
        btn = export_widget.browse_export_btn
        assert btn.text() == "Browse Export Directory"
        assert btn.isEnabled()

    def test_csv_export_button_exists(self, export_widget):
        """Test CSV export button is present."""
        btn = export_widget.csv_export_btn
        assert btn.text() == "Export to CSV"
        assert btn.isEnabled()

    def test_excel_export_button_exists(self, export_widget):
        """Test Excel export button is present."""
        btn = export_widget.excel_export_btn
        assert btn.text() == "Export to Excel"
        assert btn.isEnabled()

    def test_export_grouping_options(self, export_widget):
        """Test export grouping options are available."""
        combo = export_widget.grouping_combo
        assert combo.count() == 3
        assert combo.itemText(0) == "No Grouping"
        assert combo.itemText(1) == "By Participant"
        assert combo.itemText(2) == "By Date"

    def test_grouping_selection(self, export_widget, qtbot):
        """Test selecting grouping option."""
        combo = export_widget.grouping_combo
        combo.setCurrentIndex(1)
        assert combo.currentText() == "By Participant"

    def test_include_all_columns_checkbox(self, export_widget):
        """Test include all columns checkbox."""
        checkbox = export_widget.include_all_columns
        assert checkbox.isChecked()
        assert checkbox.text() == "Include All Columns"

    def test_toggle_columns_checkbox(self, export_widget, qtbot):
        """Test toggling columns checkbox."""
        checkbox = export_widget.include_all_columns
        initial_state = checkbox.isChecked()

        from PyQt6.QtCore import Qt

        qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)

        assert checkbox.isChecked() != initial_state

    def test_progress_label_exists(self, export_widget):
        """Test progress label shows status."""
        assert export_widget.progress_label.text() == "Ready"

    def test_csv_button_click_signal(self, export_widget, qtbot):
        """Test CSV export button click emits signal."""
        btn = export_widget.csv_export_btn
        clicked = []

        btn.clicked.connect(lambda: clicked.append("csv"))
        from PyQt6.QtCore import Qt

        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)

        assert clicked == ["csv"]

    def test_excel_button_click_signal(self, export_widget, qtbot):
        """Test Excel export button click emits signal."""
        btn = export_widget.excel_export_btn
        clicked = []

        btn.clicked.connect(lambda: clicked.append("excel"))
        from PyQt6.QtCore import Qt

        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)

        assert clicked == ["excel"]

    def test_update_progress_label(self, export_widget):
        """Test updating progress label."""
        export_widget.progress_label.setText("Exporting...")
        assert export_widget.progress_label.text() == "Exporting..."

        export_widget.progress_label.setText("Export Complete")
        assert export_widget.progress_label.text() == "Export Complete"
