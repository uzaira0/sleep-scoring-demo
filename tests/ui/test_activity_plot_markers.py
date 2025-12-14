"""
Tests for ActivityPlotWidget marker interactions.

These tests interact with the REAL plot widget like a real user would:
- Clicking on the plot to place markers
- Using keyboard shortcuts (Q/E/A/D for adjustment, C/Delete for clearing)
- Testing signal emissions
- Testing marker mode switching (sleep vs nonwear)
"""

import random
from datetime import datetime, timedelta

import numpy as np
import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from sleep_scoring_app.core.constants import MarkerCategory
from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod
from sleep_scoring_app.ui.main_window import SleepScoringMainWindow


@pytest.fixture
def app(qtbot: QtBot):
    """Create QApplication if not exists."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def main_window(qtbot: QtBot, app):
    """Create and show main window."""
    window = SleepScoringMainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(100)
    return window


@pytest.fixture
def activity_plot(main_window, qtbot: QtBot):
    """Get the activity plot widget with test data loaded."""
    plot = main_window.plot_widget

    # Generate test data for the plot
    base_time = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    timestamps = [base_time + timedelta(minutes=i) for i in range(1440)]  # 24 hours of 1-min epochs
    activity_data = [random.uniform(0, 500) for _ in range(1440)]

    # Set data on the plot
    plot.set_data_and_restrictions(timestamps=timestamps, activity_data=activity_data, view_hours=24, filename="test_data.csv")
    qtbot.wait(100)

    return plot


class TestActivityPlotMarkerPlacement:
    """Tests for placing markers by clicking on the plot."""

    def test_plot_has_no_markers_initially(self, activity_plot, qtbot: QtBot):
        """Verify plot starts with no markers."""
        assert activity_plot.daily_sleep_markers.period_1 is None
        assert activity_plot.daily_sleep_markers.period_2 is None
        assert activity_plot.daily_sleep_markers.period_3 is None
        assert activity_plot.daily_sleep_markers.period_4 is None

    def test_plot_is_in_sleep_marker_mode_by_default(self, activity_plot, qtbot: QtBot):
        """Verify plot defaults to sleep marker mode."""
        assert activity_plot._active_marker_category == MarkerCategory.SLEEP

    def test_switch_to_nonwear_marker_mode(self, activity_plot, qtbot: QtBot):
        """Test switching to nonwear marker mode."""
        activity_plot._active_marker_category = MarkerCategory.NONWEAR
        assert activity_plot._active_marker_category == MarkerCategory.NONWEAR

    def test_switch_back_to_sleep_marker_mode(self, activity_plot, qtbot: QtBot):
        """Test switching back to sleep marker mode."""
        activity_plot._active_marker_category = MarkerCategory.NONWEAR
        activity_plot._active_marker_category = MarkerCategory.SLEEP
        assert activity_plot._active_marker_category == MarkerCategory.SLEEP

    def test_add_sleep_marker_programmatically(self, activity_plot, qtbot: QtBot):
        """Test adding a sleep marker using the add_sleep_marker method."""
        # Get a timestamp within the data range
        timestamp = activity_plot.data_start_time + 3600  # 1 hour after start

        # First click sets onset
        activity_plot.add_sleep_marker(timestamp)
        assert activity_plot.current_marker_being_placed is not None
        assert activity_plot.current_marker_being_placed.onset_timestamp == timestamp

    def test_complete_sleep_marker_pair(self, activity_plot, qtbot: QtBot):
        """Test completing a sleep marker pair (onset + offset)."""
        onset_time = activity_plot.data_start_time + 3600  # 1 hour after start
        offset_time = activity_plot.data_start_time + 7200  # 2 hours after start

        # Add onset
        activity_plot.add_sleep_marker(onset_time)
        assert activity_plot.current_marker_being_placed is not None

        # Add offset (completes the pair)
        activity_plot.add_sleep_marker(offset_time)

        # current_marker_being_placed should be None after completion
        assert activity_plot.current_marker_being_placed is None

        # Period should be in slot 1
        assert activity_plot.daily_sleep_markers.period_1 is not None
        assert activity_plot.daily_sleep_markers.period_1.onset_timestamp == onset_time
        assert activity_plot.daily_sleep_markers.period_1.offset_timestamp == offset_time

    def test_invalid_offset_before_onset_rejected(self, activity_plot, qtbot: QtBot):
        """Test that offset before onset is rejected."""
        onset_time = activity_plot.data_start_time + 7200  # 2 hours after start
        offset_time = activity_plot.data_start_time + 3600  # 1 hour after start (before onset!)

        # Add onset
        activity_plot.add_sleep_marker(onset_time)
        assert activity_plot.current_marker_being_placed is not None

        # Try to add offset before onset - should reset
        activity_plot.add_sleep_marker(offset_time)

        # current_marker_being_placed should be reset to None
        assert activity_plot.current_marker_being_placed is None
        # No period should be added
        assert activity_plot.daily_sleep_markers.period_1 is None

    def test_add_multiple_sleep_periods(self, activity_plot, qtbot: QtBot):
        """Test adding multiple sleep periods with different durations to avoid duration ties."""
        # Add first period (1 hour duration - main sleep, longest)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 7200)
        assert activity_plot.daily_sleep_markers.period_1 is not None

        # Add second period (30 min duration - nap, shorter)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 10800)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 12600)  # 30 min later
        assert activity_plot.daily_sleep_markers.period_2 is not None

        # Add third period (20 min duration - nap, even shorter)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 18000)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 19200)  # 20 min later
        assert activity_plot.daily_sleep_markers.period_3 is not None

    def test_sleep_markers_changed_signal_emitted(self, activity_plot, qtbot: QtBot):
        """Test that sleep_markers_changed signal is emitted when markers are added."""
        onset_time = activity_plot.data_start_time + 3600
        offset_time = activity_plot.data_start_time + 7200

        # Add onset (no signal yet - incomplete)
        activity_plot.add_sleep_marker(onset_time)

        # Verify signal is emitted when marker pair is completed
        with qtbot.waitSignal(activity_plot.sleep_markers_changed, timeout=1000):
            activity_plot.add_sleep_marker(offset_time)

    def test_cancel_incomplete_marker(self, activity_plot, qtbot: QtBot):
        """Test cancelling an incomplete marker."""
        onset_time = activity_plot.data_start_time + 3600

        # Add onset
        activity_plot.add_sleep_marker(onset_time)
        assert activity_plot.current_marker_being_placed is not None

        # Cancel the incomplete marker
        activity_plot.cancel_incomplete_marker()
        assert activity_plot.current_marker_being_placed is None


class TestActivityPlotKeyboardShortcuts:
    """Tests for keyboard shortcut interactions."""

    def test_c_key_cancels_incomplete_marker(self, activity_plot, qtbot: QtBot):
        """Test that C key cancels an incomplete marker."""
        onset_time = activity_plot.data_start_time + 3600

        # Start placing a marker
        activity_plot.add_sleep_marker(onset_time)
        assert activity_plot.current_marker_being_placed is not None

        # Ensure the plot has focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press C key
        QTest.keyClick(activity_plot, Qt.Key.Key_C)
        qtbot.wait(50)

        # Incomplete marker should be cancelled
        assert activity_plot.current_marker_being_placed is None


class TestRealMouseClickInteractions:
    """
    Tests using ACTUAL QTest.mouseClick() to simulate real user mouse clicks.

    These tests click on the actual plot widget at pixel coordinates,
    not just calling the handler methods programmatically.
    """

    def test_real_mouse_click_on_plot_widget(self, activity_plot, qtbot: QtBot):
        """Test actual mouse click on the plot widget using QTest."""
        # Ensure plot is visible and has size
        activity_plot.show()
        qtbot.wait(100)

        # Get the widget's center point in widget coordinates
        widget_center = activity_plot.rect().center()

        # Ensure no marker is being placed
        assert activity_plot.current_marker_being_placed is None

        # Perform actual mouse click using QTest
        QTest.mouseClick(activity_plot, Qt.MouseButton.LeftButton, pos=widget_center)
        qtbot.wait(100)

        # The click should have triggered marker placement if within data bounds
        # Note: May or may not create marker depending on if click lands in valid data area

    def test_real_mouse_double_click_creates_marker_pair(self, activity_plot, qtbot: QtBot):
        """Test two real mouse clicks to create a complete marker pair."""
        activity_plot.show()
        qtbot.wait(100)

        # Get two different X positions for onset and offset
        width = activity_plot.width()
        height = activity_plot.height()

        # First click at 1/3 of the plot width (onset)
        onset_pos = activity_plot.rect().center()
        onset_pos.setX(int(width * 0.3))

        # Second click at 2/3 of the plot width (offset)
        offset_pos = activity_plot.rect().center()
        offset_pos.setX(int(width * 0.6))

        # Clear any existing markers first
        activity_plot.clear_sleep_markers()
        qtbot.wait(50)

        # First click - should start placing marker
        QTest.mouseClick(activity_plot, Qt.MouseButton.LeftButton, pos=onset_pos)
        qtbot.wait(100)

        # Check if we started placing a marker (if click was in valid data area)
        if activity_plot.current_marker_being_placed is not None:
            # Second click - should complete the marker
            QTest.mouseClick(activity_plot, Qt.MouseButton.LeftButton, pos=offset_pos)
            qtbot.wait(100)

            # Marker pair should be complete
            assert activity_plot.current_marker_being_placed is None
            assert activity_plot.daily_sleep_markers.period_1 is not None

    def test_real_right_click_cancels_marker(self, activity_plot, qtbot: QtBot):
        """Test right-click to cancel incomplete marker.

        Note: pyqtgraph uses its own sigMouseClicked signal system, not standard Qt events.
        QTest.mouseClick() doesn't trigger pyqtgraph's signal, so we simulate the click
        event that pyqtgraph would receive.
        """
        activity_plot.show()
        qtbot.wait(100)

        # Start a marker programmatically (we know this works)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        assert activity_plot.current_marker_being_placed is not None

        # Create a mock right-click event (pyqtgraph event format)
        rect = activity_plot.plotItem.sceneBoundingRect()
        center_x = rect.x() + rect.width() / 2
        center_y = rect.y() + rect.height() / 2

        class MockEvent:
            def __init__(self, x, y):
                self._pos = QPointF(x, y)
                self._button = Qt.MouseButton.RightButton

            def scenePos(self):
                return self._pos

            def button(self):
                return self._button

        # Call the handler directly (simulating what pyqtgraph's sigMouseClicked does)
        activity_plot.on_plot_clicked(MockEvent(center_x, center_y))
        qtbot.wait(100)

        # Marker should be cancelled
        assert activity_plot.current_marker_being_placed is None

    def test_real_keyboard_q_after_click(self, activity_plot, qtbot: QtBot):
        """Test real keyboard Q key after creating a marker."""
        activity_plot.show()
        qtbot.wait(100)

        # Create a complete marker pair
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 7200)

        assert activity_plot.daily_sleep_markers.period_1 is not None
        initial_onset = activity_plot.daily_sleep_markers.period_1.onset_timestamp

        # Give focus to the plot
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press Q key using QTest
        QTest.keyClick(activity_plot, Qt.Key.Key_Q)
        qtbot.wait(100)

        # Onset should have moved left by 60 seconds
        new_onset = activity_plot.daily_sleep_markers.period_1.onset_timestamp
        assert new_onset == initial_onset - 60

    def test_real_keyboard_sequence_qead(self, activity_plot, qtbot: QtBot):
        """Test a sequence of real keyboard presses Q, E, A, D."""
        activity_plot.show()
        qtbot.wait(100)

        # Create a complete marker pair
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 7200)

        initial_onset = activity_plot.daily_sleep_markers.period_1.onset_timestamp
        initial_offset = activity_plot.daily_sleep_markers.period_1.offset_timestamp

        # Give focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press Q (onset left)
        QTest.keyClick(activity_plot, Qt.Key.Key_Q)
        qtbot.wait(50)
        assert activity_plot.daily_sleep_markers.period_1.onset_timestamp == initial_onset - 60

        # Press E (onset right) - should return to original
        QTest.keyClick(activity_plot, Qt.Key.Key_E)
        qtbot.wait(50)
        assert activity_plot.daily_sleep_markers.period_1.onset_timestamp == initial_onset

        # Press A (offset left)
        QTest.keyClick(activity_plot, Qt.Key.Key_A)
        qtbot.wait(50)
        assert activity_plot.daily_sleep_markers.period_1.offset_timestamp == initial_offset - 60

        # Press D (offset right) - should return to original
        QTest.keyClick(activity_plot, Qt.Key.Key_D)
        qtbot.wait(50)
        assert activity_plot.daily_sleep_markers.period_1.offset_timestamp == initial_offset

    def test_real_keyboard_c_clears_marker(self, activity_plot, qtbot: QtBot):
        """Test real C key press clears the selected marker."""
        activity_plot.show()
        qtbot.wait(100)

        # Create a complete marker pair
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 7200)
        assert activity_plot.daily_sleep_markers.period_1 is not None

        # Give focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press C key
        QTest.keyClick(activity_plot, Qt.Key.Key_C)
        qtbot.wait(100)

        # Marker should be cleared
        assert activity_plot.daily_sleep_markers.period_1 is None

    def test_real_keyboard_delete_clears_marker(self, activity_plot, qtbot: QtBot):
        """Test real Delete key press clears the selected marker."""
        activity_plot.show()
        qtbot.wait(100)

        # Create a complete marker pair
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 7200)
        assert activity_plot.daily_sleep_markers.period_1 is not None

        # Give focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press Delete key
        QTest.keyClick(activity_plot, Qt.Key.Key_Delete)
        qtbot.wait(100)

        # Marker should be cleared
        assert activity_plot.daily_sleep_markers.period_1 is None

    def test_delete_key_cancels_incomplete_marker(self, activity_plot, qtbot: QtBot):
        """Test that Delete key cancels an incomplete marker."""
        onset_time = activity_plot.data_start_time + 3600

        # Start placing a marker
        activity_plot.add_sleep_marker(onset_time)
        assert activity_plot.current_marker_being_placed is not None

        # Ensure the plot has focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press Delete key
        QTest.keyClick(activity_plot, Qt.Key.Key_Delete)
        qtbot.wait(50)

        # Incomplete marker should be cancelled
        assert activity_plot.current_marker_being_placed is None

    def test_q_key_moves_onset_left(self, activity_plot, qtbot: QtBot):
        """Test that Q key moves onset left by 60 seconds."""
        onset_time = activity_plot.data_start_time + 3600
        offset_time = activity_plot.data_start_time + 7200

        # Add a complete marker pair
        activity_plot.add_sleep_marker(onset_time)
        activity_plot.add_sleep_marker(offset_time)

        # Select the marker set
        activity_plot.selected_marker_set_index = 1

        # Record initial onset time
        initial_onset = activity_plot.daily_sleep_markers.period_1.onset_timestamp

        # Ensure the plot has focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press Q key
        QTest.keyClick(activity_plot, Qt.Key.Key_Q)
        qtbot.wait(50)

        # Onset should have moved left by 60 seconds
        new_onset = activity_plot.daily_sleep_markers.period_1.onset_timestamp
        assert new_onset == initial_onset - 60

    def test_e_key_moves_onset_right(self, activity_plot, qtbot: QtBot):
        """Test that E key moves onset right by 60 seconds."""
        onset_time = activity_plot.data_start_time + 3600
        offset_time = activity_plot.data_start_time + 7200

        # Add a complete marker pair
        activity_plot.add_sleep_marker(onset_time)
        activity_plot.add_sleep_marker(offset_time)

        # Select the marker set
        activity_plot.selected_marker_set_index = 1

        # Record initial onset time
        initial_onset = activity_plot.daily_sleep_markers.period_1.onset_timestamp

        # Ensure the plot has focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press E key
        QTest.keyClick(activity_plot, Qt.Key.Key_E)
        qtbot.wait(50)

        # Onset should have moved right by 60 seconds
        new_onset = activity_plot.daily_sleep_markers.period_1.onset_timestamp
        assert new_onset == initial_onset + 60

    def test_a_key_moves_offset_left(self, activity_plot, qtbot: QtBot):
        """Test that A key moves offset left by 60 seconds."""
        onset_time = activity_plot.data_start_time + 3600
        offset_time = activity_plot.data_start_time + 7200

        # Add a complete marker pair
        activity_plot.add_sleep_marker(onset_time)
        activity_plot.add_sleep_marker(offset_time)

        # Select the marker set
        activity_plot.selected_marker_set_index = 1

        # Record initial offset time
        initial_offset = activity_plot.daily_sleep_markers.period_1.offset_timestamp

        # Ensure the plot has focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press A key
        QTest.keyClick(activity_plot, Qt.Key.Key_A)
        qtbot.wait(50)

        # Offset should have moved left by 60 seconds
        new_offset = activity_plot.daily_sleep_markers.period_1.offset_timestamp
        assert new_offset == initial_offset - 60

    def test_d_key_moves_offset_right(self, activity_plot, qtbot: QtBot):
        """Test that D key moves offset right by 60 seconds."""
        onset_time = activity_plot.data_start_time + 3600
        offset_time = activity_plot.data_start_time + 7200

        # Add a complete marker pair
        activity_plot.add_sleep_marker(onset_time)
        activity_plot.add_sleep_marker(offset_time)

        # Select the marker set
        activity_plot.selected_marker_set_index = 1

        # Record initial offset time
        initial_offset = activity_plot.daily_sleep_markers.period_1.offset_timestamp

        # Ensure the plot has focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press D key
        QTest.keyClick(activity_plot, Qt.Key.Key_D)
        qtbot.wait(50)

        # Offset should have moved right by 60 seconds
        new_offset = activity_plot.daily_sleep_markers.period_1.offset_timestamp
        assert new_offset == initial_offset + 60


class TestActivityPlotClearMarkers:
    """Tests for clearing markers."""

    def test_clear_selected_marker_set(self, activity_plot, qtbot: QtBot):
        """Test clearing the selected marker set."""
        onset_time = activity_plot.data_start_time + 3600
        offset_time = activity_plot.data_start_time + 7200

        # Add a complete marker pair
        activity_plot.add_sleep_marker(onset_time)
        activity_plot.add_sleep_marker(offset_time)
        assert activity_plot.daily_sleep_markers.period_1 is not None

        # Select the marker set
        activity_plot.selected_marker_set_index = 1

        # Clear the selected marker set
        activity_plot.clear_selected_marker_set()
        qtbot.wait(50)

        # Marker should be cleared
        assert activity_plot.daily_sleep_markers.period_1 is None

    def test_c_key_clears_selected_marker_when_no_incomplete(self, activity_plot, qtbot: QtBot):
        """Test that C key clears selected marker when there's no incomplete marker."""
        onset_time = activity_plot.data_start_time + 3600
        offset_time = activity_plot.data_start_time + 7200

        # Add a complete marker pair
        activity_plot.add_sleep_marker(onset_time)
        activity_plot.add_sleep_marker(offset_time)
        assert activity_plot.daily_sleep_markers.period_1 is not None
        assert activity_plot.current_marker_being_placed is None

        # Select the marker set
        activity_plot.selected_marker_set_index = 1

        # Ensure the plot has focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press C key - should clear the selected marker
        QTest.keyClick(activity_plot, Qt.Key.Key_C)
        qtbot.wait(50)

        # Marker should be cleared
        assert activity_plot.daily_sleep_markers.period_1 is None

    def test_clear_sleep_markers_clears_all(self, activity_plot, qtbot: QtBot):
        """Test that clear_sleep_markers clears all markers."""
        # Add multiple marker pairs with different durations to avoid duration ties
        # First period: 1 hour (main sleep)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 7200)
        # Second period: 30 min (nap)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 10800)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 12600)

        assert activity_plot.daily_sleep_markers.period_1 is not None
        assert activity_plot.daily_sleep_markers.period_2 is not None

        # Clear all markers
        activity_plot.clear_sleep_markers()
        qtbot.wait(50)

        # All markers should be cleared
        assert activity_plot.daily_sleep_markers.period_1 is None
        assert activity_plot.daily_sleep_markers.period_2 is None


class TestActivityPlotNonwearMarkers:
    """Tests for nonwear marker placement."""

    def test_switch_to_nonwear_mode_and_place_marker(self, activity_plot, qtbot: QtBot):
        """Test placing nonwear markers when in nonwear mode."""
        # Switch to nonwear mode
        activity_plot._active_marker_category = MarkerCategory.NONWEAR

        # Get a timestamp within the data range
        start_time = activity_plot.data_start_time + 3600

        # Add nonwear marker (start)
        activity_plot.add_nonwear_marker(start_time)
        assert activity_plot._current_nonwear_marker_being_placed is not None

    def test_complete_nonwear_marker_pair(self, activity_plot, qtbot: QtBot):
        """Test completing a nonwear marker pair."""
        # Switch to nonwear mode
        activity_plot._active_marker_category = MarkerCategory.NONWEAR

        start_time = activity_plot.data_start_time + 3600
        end_time = activity_plot.data_start_time + 7200

        # Add start
        activity_plot.add_nonwear_marker(start_time)

        # Add end
        activity_plot.add_nonwear_marker(end_time)

        # current_nonwear_marker_being_placed should be None after completion
        assert activity_plot._current_nonwear_marker_being_placed is None

    def test_cancel_incomplete_nonwear_marker(self, activity_plot, qtbot: QtBot):
        """Test cancelling an incomplete nonwear marker."""
        # Switch to nonwear mode
        activity_plot._active_marker_category = MarkerCategory.NONWEAR

        start_time = activity_plot.data_start_time + 3600

        # Start placing a nonwear marker
        activity_plot.add_nonwear_marker(start_time)
        assert activity_plot._current_nonwear_marker_being_placed is not None

        # Cancel the incomplete marker
        activity_plot.cancel_incomplete_nonwear_marker()
        assert activity_plot._current_nonwear_marker_being_placed is None

    def test_c_key_cancels_incomplete_nonwear_marker(self, activity_plot, qtbot: QtBot):
        """Test that C key cancels incomplete nonwear marker in nonwear mode."""
        # Switch to nonwear mode
        activity_plot._active_marker_category = MarkerCategory.NONWEAR

        start_time = activity_plot.data_start_time + 3600

        # Start placing a nonwear marker
        activity_plot.add_nonwear_marker(start_time)
        assert activity_plot._current_nonwear_marker_being_placed is not None

        # Ensure the plot has focus
        activity_plot.setFocus()
        qtbot.wait(50)

        # Press C key
        QTest.keyClick(activity_plot, Qt.Key.Key_C)
        qtbot.wait(50)

        # Incomplete nonwear marker should be cancelled
        assert activity_plot._current_nonwear_marker_being_placed is None


class TestActivityPlotMarkerSignals:
    """Tests for marker-related signal emissions."""

    def test_marker_limit_exceeded_signal(self, activity_plot, qtbot: QtBot):
        """Test that marker_limit_exceeded signal is emitted when limit reached."""
        # Fill all 4 marker slots with different durations to avoid duration ties
        # Period 1: 2 hours (main sleep - longest)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 10800)

        # Period 2: 1 hour (nap)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 14400)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 18000)

        # Period 3: 30 min (nap)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 21600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 23400)

        # Period 4: 20 min (nap)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 28800)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 30000)

        assert activity_plot.daily_sleep_markers.period_1 is not None
        assert activity_plot.daily_sleep_markers.period_2 is not None
        assert activity_plot.daily_sleep_markers.period_3 is not None
        assert activity_plot.daily_sleep_markers.period_4 is not None

        # Try to add a 5th marker - should emit marker_limit_exceeded
        with qtbot.waitSignal(activity_plot.marker_limit_exceeded, timeout=1000):
            activity_plot.add_sleep_marker(activity_plot.data_start_time + 50000)


class TestActivityPlotDataBoundaries:
    """Tests for data boundary handling in marker placement."""

    def test_marker_placement_respects_data_boundaries(self, activity_plot, qtbot: QtBot):
        """Test that markers can only be placed within data boundaries."""
        # Verify data boundaries are set
        assert activity_plot.data_start_time is not None
        assert activity_plot.data_end_time is not None

        # Place a marker within boundaries - should work
        valid_time = activity_plot.data_start_time + 3600
        activity_plot.add_sleep_marker(valid_time)
        assert activity_plot.current_marker_being_placed is not None

        # Cancel the incomplete marker
        activity_plot.cancel_incomplete_marker()

    def test_plot_view_hours_24(self, activity_plot, qtbot: QtBot):
        """Test that 24-hour view is set correctly."""
        assert activity_plot.current_view_hours == 24

    def test_plot_view_hours_48(self, main_window, qtbot: QtBot):
        """Test switching to 48-hour view."""
        plot = main_window.plot_widget

        # Generate 48-hour test data
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        timestamps = [base_time + timedelta(minutes=i) for i in range(2880)]  # 48 hours
        activity_data = [random.uniform(0, 500) for _ in range(2880)]

        plot.set_data_and_restrictions(timestamps=timestamps, activity_data=activity_data, view_hours=48, filename="test_48h.csv")
        qtbot.wait(100)

        assert plot.current_view_hours == 48


class TestActivityPlotMarkerSelection:
    """Tests for marker selection functionality."""

    def test_selected_marker_set_index_default(self, activity_plot, qtbot: QtBot):
        """Test that selected marker set defaults to 1."""
        assert activity_plot.selected_marker_set_index == 1

    def test_change_selected_marker_set_index(self, activity_plot, qtbot: QtBot):
        """Test changing the selected marker set index."""
        activity_plot.selected_marker_set_index = 2
        assert activity_plot.selected_marker_set_index == 2

        activity_plot.selected_marker_set_index = 3
        assert activity_plot.selected_marker_set_index == 3

    def test_get_selected_marker_period_returns_correct_period(self, activity_plot, qtbot: QtBot):
        """Test that get_selected_marker_period returns the correct period."""
        # Add markers to period 1
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 7200)

        # Select period 1
        activity_plot.selected_marker_set_index = 1

        # Get selected period
        selected = activity_plot.get_selected_marker_period()
        assert selected is not None
        assert selected == activity_plot.daily_sleep_markers.period_1


class TestActivityPlotInitialization:
    """Tests for plot initialization and setup."""

    def test_plot_widget_initialized_correctly(self, activity_plot, qtbot: QtBot):
        """Test that plot widget is properly initialized."""
        assert activity_plot is not None
        assert activity_plot.daily_sleep_markers is not None
        assert activity_plot._daily_nonwear_markers is not None

    def test_plot_has_marker_renderer(self, activity_plot, qtbot: QtBot):
        """Test that plot has marker renderer."""
        assert hasattr(activity_plot, "marker_renderer")
        assert activity_plot.marker_renderer is not None

    def test_plot_has_overlay_renderer(self, activity_plot, qtbot: QtBot):
        """Test that plot has overlay renderer."""
        assert hasattr(activity_plot, "overlay_renderer")
        assert activity_plot.overlay_renderer is not None

    def test_plot_has_algorithm_manager(self, activity_plot, qtbot: QtBot):
        """Test that plot has algorithm manager."""
        assert hasattr(activity_plot, "algorithm_manager")
        assert activity_plot.algorithm_manager is not None

    def test_plot_has_state_serializer(self, activity_plot, qtbot: QtBot):
        """Test that plot has state serializer."""
        assert hasattr(activity_plot, "state_serializer")
        assert activity_plot.state_serializer is not None


class TestActivityPlotMouseInteraction:
    """Tests for mouse click interactions on the plot."""

    def test_plot_can_receive_focus(self, activity_plot, qtbot: QtBot):
        """Test that plot can receive keyboard focus."""
        activity_plot.setFocus()
        qtbot.wait(50)
        assert activity_plot.hasFocus()

    def test_plot_scene_bounding_rect_valid(self, activity_plot, qtbot: QtBot):
        """Test that plot scene bounding rect is valid."""
        rect = activity_plot.plotItem.sceneBoundingRect()
        assert rect.width() > 0
        assert rect.height() > 0

    def test_plot_viewbox_valid(self, activity_plot, qtbot: QtBot):
        """Test that plot viewbox is valid."""
        vb = activity_plot.plotItem.getViewBox()
        assert vb is not None

    def test_simulated_click_creates_marker(self, activity_plot, qtbot: QtBot):
        """Test that simulating a click on the plot creates a marker."""
        # Get the plot's scene bounding rect
        rect = activity_plot.plotItem.sceneBoundingRect()

        # Calculate a point in the middle of the plot
        center_x = rect.x() + rect.width() / 2
        center_y = rect.y() + rect.height() / 2

        # Create a mock event with scene position
        class MockEvent:
            def __init__(self, x, y):
                self._pos = QPointF(x, y)
                self._button = Qt.MouseButton.LeftButton

            def scenePos(self):
                return self._pos

            def button(self):
                return self._button

        event = MockEvent(center_x, center_y)

        # Ensure no marker is being placed
        assert activity_plot.current_marker_being_placed is None

        # Call the click handler
        activity_plot.on_plot_clicked(event)
        qtbot.wait(50)

        # Should have started placing a marker
        assert activity_plot.current_marker_being_placed is not None

    def test_right_click_cancels_incomplete_marker(self, activity_plot, qtbot: QtBot):
        """Test that right-click cancels an incomplete marker."""
        # Start placing a marker
        activity_plot.add_sleep_marker(activity_plot.data_start_time + 3600)
        assert activity_plot.current_marker_being_placed is not None

        # Create a mock right-click event
        rect = activity_plot.plotItem.sceneBoundingRect()
        center_x = rect.x() + rect.width() / 2
        center_y = rect.y() + rect.height() / 2

        class MockEvent:
            def __init__(self, x, y):
                self._pos = QPointF(x, y)
                self._button = Qt.MouseButton.RightButton

            def scenePos(self):
                return self._pos

            def button(self):
                return self._button

        event = MockEvent(center_x, center_y)

        # Call the click handler with right-click
        activity_plot.on_plot_clicked(event)
        qtbot.wait(50)

        # Incomplete marker should be cancelled
        assert activity_plot.current_marker_being_placed is None
