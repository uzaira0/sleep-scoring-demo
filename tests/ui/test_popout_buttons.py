"""
Tests for popout button functionality in AnalysisTab.

These tests verify that clicking the onset and offset popout buttons
actually creates and shows the popout windows.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import numpy as np
import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for the session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def main_window(qtbot):
    """Create a real MainWindow for testing."""
    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

    window = SleepScoringMainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(200)  # Let it initialize
    return window


@pytest.fixture
def analysis_tab(main_window):
    """Get the analysis tab from the main window."""
    return main_window.analysis_tab


class TestPopoutButtonsExist:
    """Test that popout buttons exist and are properly configured."""

    def test_onset_popout_button_exists(self, analysis_tab, qtbot):
        """Test that onset popout button exists as instance variable."""
        assert hasattr(analysis_tab, "onset_popout_button"), "onset_popout_button should be an instance variable"
        assert isinstance(analysis_tab.onset_popout_button, QPushButton)

    def test_offset_popout_button_exists(self, analysis_tab, qtbot):
        """Test that offset popout button exists as instance variable."""
        assert hasattr(analysis_tab, "offset_popout_button"), "offset_popout_button should be an instance variable"
        assert isinstance(analysis_tab.offset_popout_button, QPushButton)

    def test_onset_popout_button_is_visible(self, analysis_tab, qtbot):
        """Test that onset popout button is visible."""
        assert analysis_tab.onset_popout_button.isVisible()

    def test_offset_popout_button_is_visible(self, analysis_tab, qtbot):
        """Test that offset popout button is visible."""
        assert analysis_tab.offset_popout_button.isVisible()

    def test_onset_popout_button_is_enabled(self, analysis_tab, qtbot):
        """Test that onset popout button is enabled."""
        assert analysis_tab.onset_popout_button.isEnabled()

    def test_offset_popout_button_is_enabled(self, analysis_tab, qtbot):
        """Test that offset popout button is enabled."""
        assert analysis_tab.offset_popout_button.isEnabled()

    def test_onset_popout_button_has_text(self, analysis_tab, qtbot):
        """Test that onset popout button has correct text."""
        assert "Pop Out" in analysis_tab.onset_popout_button.text()

    def test_offset_popout_button_has_text(self, analysis_tab, qtbot):
        """Test that offset popout button has correct text."""
        assert "Pop Out" in analysis_tab.offset_popout_button.text()


class TestPopoutButtonConnections:
    """Test that popout buttons are properly connected to slots."""

    def test_onset_button_has_connections(self, analysis_tab, qtbot):
        """Test that onset button has signal connections."""
        # Check that clicking signal is connected
        receivers = analysis_tab.onset_popout_button.receivers(analysis_tab.onset_popout_button.clicked)
        assert receivers > 0, "onset_popout_button.clicked should have at least one receiver"

    def test_offset_button_has_connections(self, analysis_tab, qtbot):
        """Test that offset button has signal connections."""
        # Check that clicking signal is connected
        receivers = analysis_tab.offset_popout_button.receivers(analysis_tab.offset_popout_button.clicked)
        assert receivers > 0, "offset_popout_button.clicked should have at least one receiver"


class TestPopoutButtonClicks:
    """Test that clicking popout buttons creates windows."""

    def test_click_onset_popout_button_creates_window(self, analysis_tab, qtbot):
        """Test that clicking onset popout button creates a window."""
        # Initially no window
        assert analysis_tab.onset_popout_window is None

        # Click the button
        qtbot.mouseClick(analysis_tab.onset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        # Window should now exist
        assert analysis_tab.onset_popout_window is not None, "onset_popout_window should be created after clicking button"

        # Clean up
        if analysis_tab.onset_popout_window:
            analysis_tab.onset_popout_window.close()
            analysis_tab.onset_popout_window = None

    def test_click_offset_popout_button_creates_window(self, analysis_tab, qtbot):
        """Test that clicking offset popout button creates a window."""
        # Initially no window
        assert analysis_tab.offset_popout_window is None

        # Click the button
        qtbot.mouseClick(analysis_tab.offset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        # Window should now exist
        assert analysis_tab.offset_popout_window is not None, "offset_popout_window should be created after clicking button"

        # Clean up
        if analysis_tab.offset_popout_window:
            analysis_tab.offset_popout_window.close()
            analysis_tab.offset_popout_window = None

    def test_onset_popout_window_is_shown(self, analysis_tab, qtbot):
        """Test that onset popout window is visible after click."""
        qtbot.mouseClick(analysis_tab.onset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert analysis_tab.onset_popout_window is not None
        assert analysis_tab.onset_popout_window.isVisible(), "onset_popout_window should be visible"

        # Clean up
        analysis_tab.onset_popout_window.close()
        analysis_tab.onset_popout_window = None

    def test_offset_popout_window_is_shown(self, analysis_tab, qtbot):
        """Test that offset popout window is visible after click."""
        qtbot.mouseClick(analysis_tab.offset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert analysis_tab.offset_popout_window is not None
        assert analysis_tab.offset_popout_window.isVisible(), "offset_popout_window should be visible"

        # Clean up
        analysis_tab.offset_popout_window.close()
        analysis_tab.offset_popout_window = None


class TestPopoutWindowProperties:
    """Test properties of created popout windows."""

    def test_onset_window_has_correct_title(self, analysis_tab, qtbot):
        """Test onset window has correct title."""
        qtbot.mouseClick(analysis_tab.onset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert "Onset" in analysis_tab.onset_popout_window.windowTitle()

        analysis_tab.onset_popout_window.close()
        analysis_tab.onset_popout_window = None

    def test_offset_window_has_correct_title(self, analysis_tab, qtbot):
        """Test offset window has correct title."""
        qtbot.mouseClick(analysis_tab.offset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert "Offset" in analysis_tab.offset_popout_window.windowTitle()

        analysis_tab.offset_popout_window.close()
        analysis_tab.offset_popout_window = None

    def test_onset_window_has_correct_type(self, analysis_tab, qtbot):
        """Test onset window has correct table_type."""
        qtbot.mouseClick(analysis_tab.onset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert analysis_tab.onset_popout_window.table_type == "onset"

        analysis_tab.onset_popout_window.close()
        analysis_tab.onset_popout_window = None

    def test_offset_window_has_correct_type(self, analysis_tab, qtbot):
        """Test offset window has correct table_type."""
        qtbot.mouseClick(analysis_tab.offset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)

        assert analysis_tab.offset_popout_window.table_type == "offset"

        analysis_tab.offset_popout_window.close()
        analysis_tab.offset_popout_window = None


class TestBothPopoutButtonsWork:
    """Test that both buttons work in sequence."""

    def test_both_buttons_can_be_clicked_sequentially(self, analysis_tab, qtbot):
        """Test clicking both buttons one after another."""
        # Click onset
        qtbot.mouseClick(analysis_tab.onset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)
        assert analysis_tab.onset_popout_window is not None, "onset window should be created"

        # Click offset
        qtbot.mouseClick(analysis_tab.offset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)
        assert analysis_tab.offset_popout_window is not None, "offset window should be created"

        # Both windows should exist
        assert analysis_tab.onset_popout_window is not None
        assert analysis_tab.offset_popout_window is not None

        # Clean up
        analysis_tab.onset_popout_window.close()
        analysis_tab.onset_popout_window = None
        analysis_tab.offset_popout_window.close()
        analysis_tab.offset_popout_window = None

    def test_clicking_same_button_twice_shows_existing_window(self, analysis_tab, qtbot):
        """Test that clicking the same button twice reuses the window."""
        # Click onset first time
        qtbot.mouseClick(analysis_tab.onset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)
        first_window = analysis_tab.onset_popout_window
        assert first_window is not None

        # Click onset second time
        qtbot.mouseClick(analysis_tab.onset_popout_button, Qt.MouseButton.LeftButton)
        qtbot.wait(200)
        second_window = analysis_tab.onset_popout_window

        # Should be the same window
        assert first_window is second_window, "Should reuse existing window"

        # Clean up
        analysis_tab.onset_popout_window.close()
        analysis_tab.onset_popout_window = None


class TestDirectSlotCall:
    """Test calling the slots directly (bypassing button click)."""

    def test_direct_onset_slot_call(self, analysis_tab, qtbot):
        """Test calling _on_onset_popout_clicked directly."""
        assert analysis_tab.onset_popout_window is None

        # Call slot directly
        analysis_tab._on_onset_popout_clicked()
        qtbot.wait(200)

        assert analysis_tab.onset_popout_window is not None, "Direct slot call should create window"

        analysis_tab.onset_popout_window.close()
        analysis_tab.onset_popout_window = None

    def test_direct_offset_slot_call(self, analysis_tab, qtbot):
        """Test calling _on_offset_popout_clicked directly."""
        assert analysis_tab.offset_popout_window is None

        # Call slot directly
        analysis_tab._on_offset_popout_clicked()
        qtbot.wait(200)

        assert analysis_tab.offset_popout_window is not None, "Direct slot call should create window"

        analysis_tab.offset_popout_window.close()
        analysis_tab.offset_popout_window = None
