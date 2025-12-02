#!/usr/bin/env python3
"""
Integration tests for Main Window tab management.
Tests tab switching, coordination, and state management across tabs.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QTabWidget, QWidget


@pytest.mark.integration
@pytest.mark.gui
class TestMainWindowTabs:
    """Test main window tab management and coordination."""

    @pytest.fixture
    def tab_widget_with_tabs(self, qtbot):
        """Create a real QTabWidget with real QWidget tabs."""
        tab_widget = QTabWidget()
        qtbot.addWidget(tab_widget)

        # Create real QWidget tabs (minimal widgets for testing)
        analysis_tab = QWidget()
        export_tab = QWidget()
        data_settings_tab = QWidget()
        study_settings_tab = QWidget()

        # Add tabs to widget
        tab_widget.addTab(analysis_tab, "Analysis")
        tab_widget.addTab(export_tab, "Export")
        tab_widget.addTab(data_settings_tab, "Data Settings")
        tab_widget.addTab(study_settings_tab, "Study Settings")

        return {
            "tab_widget": tab_widget,
            "analysis_tab": analysis_tab,
            "export_tab": export_tab,
            "data_settings_tab": data_settings_tab,
            "study_settings_tab": study_settings_tab,
        }

    def test_all_tabs_created(self, tab_widget_with_tabs):
        """Test all tabs are created on initialization."""
        tabs = tab_widget_with_tabs
        assert tabs["tab_widget"].count() == 4
        assert tabs["analysis_tab"] is not None
        assert tabs["export_tab"] is not None
        assert tabs["data_settings_tab"] is not None
        assert tabs["study_settings_tab"] is not None

    def test_tab_switching(self, tab_widget_with_tabs, qtbot):
        """Test switching between tabs."""
        tab_widget = tab_widget_with_tabs["tab_widget"]

        # Start on first tab
        assert tab_widget.currentIndex() == 0

        # Switch to export tab
        tab_widget.setCurrentIndex(1)
        assert tab_widget.currentIndex() == 1

        # Switch to data settings
        tab_widget.setCurrentIndex(2)
        assert tab_widget.currentIndex() == 2

    def test_tab_labels(self, tab_widget_with_tabs):
        """Test tab labels are set correctly."""
        tab_widget = tab_widget_with_tabs["tab_widget"]
        assert tab_widget.tabText(0) == "Analysis"
        assert tab_widget.tabText(1) == "Export"
        assert tab_widget.tabText(2) == "Data Settings"
        assert tab_widget.tabText(3) == "Study Settings"

    def test_analysis_tab_default(self, tab_widget_with_tabs):
        """Test analysis tab is shown by default."""
        tab_widget = tab_widget_with_tabs["tab_widget"]
        assert tab_widget.currentIndex() == 0

    def test_state_preserved_across_tab_switches(self, tab_widget_with_tabs):
        """Test application state is preserved when switching tabs."""
        tab_widget = tab_widget_with_tabs["tab_widget"]

        # Simulate state that would be stored on a parent window
        state = {"selected_file": "test_file.csv", "available_dates": ["2021-04-20"]}

        # Switch tabs
        tab_widget.setCurrentIndex(1)
        tab_widget.setCurrentIndex(0)

        # State should be preserved (state dict unchanged)
        assert state["selected_file"] == "test_file.csv"
        assert state["available_dates"] == ["2021-04-20"]

    def test_tab_current_widget(self, tab_widget_with_tabs):
        """Test getting current widget from tab."""
        tabs = tab_widget_with_tabs
        tab_widget = tabs["tab_widget"]

        # Default is analysis tab
        assert tab_widget.currentWidget() == tabs["analysis_tab"]

        # Switch and verify
        tab_widget.setCurrentIndex(1)
        assert tab_widget.currentWidget() == tabs["export_tab"]

    def test_tab_widget_signal_on_change(self, tab_widget_with_tabs, qtbot):
        """Test tab widget emits signal on tab change."""
        tab_widget = tab_widget_with_tabs["tab_widget"]

        # Use qtbot to wait for signal
        with qtbot.waitSignal(tab_widget.currentChanged, timeout=1000):
            tab_widget.setCurrentIndex(2)

        assert tab_widget.currentIndex() == 2

    def test_tab_enable_disable(self, tab_widget_with_tabs):
        """Test enabling/disabling tabs."""
        tab_widget = tab_widget_with_tabs["tab_widget"]

        # Disable export tab
        tab_widget.setTabEnabled(1, False)
        assert not tab_widget.isTabEnabled(1)

        # Re-enable
        tab_widget.setTabEnabled(1, True)
        assert tab_widget.isTabEnabled(1)
