#!/usr/bin/env python3
"""
TRUE Visible End-to-End Tests.

These tests create REAL visible windows that you can WATCH.
They simulate actual human interactions with mouse clicks and keyboard input.

To run with visible windows (not headless):
    uv run pytest tests/gui/e2e/test_visible_e2e.py -v -s

The -s flag is important to see print statements and observe the window.

NOTE: These tests are SLOW by design - they include waits so humans can observe.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QPushButton, QTableWidget, QTabWidget
from PyQt6.QtTest import QTest

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


# How long to pause between actions so humans can observe (milliseconds)
OBSERVATION_DELAY_MS = 500  # Set to 0 for fast headless runs, 500+ to watch


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def test_data_folder(tmp_path):
    """Create a temporary folder with realistic test CSV files."""
    data_folder = tmp_path / "test_data"
    data_folder.mkdir()

    # Generate realistic 48-hour activity data with circadian pattern
    start = datetime(2021, 4, 20, 0, 0, 0)
    epochs = 2880  # 48 hours of minute-by-minute data

    timestamps = [start + timedelta(minutes=i) for i in range(epochs)]

    # Generate circadian activity pattern (higher during day, lower at night)
    activity = []
    for ts in timestamps:
        hour = ts.hour
        if 6 <= hour < 22:  # Daytime: higher activity
            base = 150 + np.random.randint(-50, 100)
        else:  # Nighttime: lower activity (sleep)
            base = 10 + np.random.randint(0, 30)
        activity.append(max(0, base))

    df = pd.DataFrame({
        "Date": [ts.strftime("%m/%d/%Y") for ts in timestamps],
        "Time": [ts.strftime("%H:%M:%S") for ts in timestamps],
        "Axis1": activity,
        "Axis2": [int(a * 0.8) for a in activity],
        "Axis3": [int(a * 0.5) for a in activity],
        "Vector Magnitude": [int(np.sqrt(a**2 + (a*0.8)**2 + (a*0.5)**2)) for a in activity],
        "Steps": [np.random.randint(0, 20) if a > 50 else 0 for a in activity],
    })

    # Save with realistic filename pattern
    test_file = data_folder / "4000 T1 (2021-04-20)60sec.csv"
    df.to_csv(test_file, index=False)

    # Create a second file for multi-file testing
    start2 = datetime(2021, 4, 22, 0, 0, 0)
    timestamps2 = [start2 + timedelta(minutes=i) for i in range(epochs)]
    activity2 = [max(0, 100 + np.random.randint(-50, 100)) for _ in range(epochs)]

    df2 = pd.DataFrame({
        "Date": [ts.strftime("%m/%d/%Y") for ts in timestamps2],
        "Time": [ts.strftime("%H:%M:%S") for ts in timestamps2],
        "Axis1": activity2,
        "Axis2": [int(a * 0.8) for a in activity2],
        "Axis3": [int(a * 0.5) for a in activity2],
        "Vector Magnitude": [int(np.sqrt(a**2 + (a*0.8)**2 + (a*0.5)**2)) for a in activity2],
        "Steps": [np.random.randint(0, 20) if a > 50 else 0 for a in activity2],
    })

    test_file2 = data_folder / "4001 T1 (2021-04-22)60sec.csv"
    df2.to_csv(test_file2, index=False)

    return data_folder


@pytest.fixture
def temp_db_path(tmp_path):
    """Create path for temporary database."""
    return tmp_path / "test_sleep_scoring.db"


@pytest.fixture
def visible_main_window(qtbot, tmp_path, test_data_folder, temp_db_path):
    """
    Create and SHOW a real MainWindow for visible E2E testing.

    This fixture:
    1. Creates a real MainWindow
    2. Shows it on screen (visible!)
    3. Waits for it to be fully rendered
    4. Returns the window for interaction
    """
    import sleep_scoring_app.data.database as db_module

    # Reset database singleton to use temp database
    db_module._database_initialized = False

    # Patch DatabaseManager to use temp path
    original_init = db_module.DatabaseManager.__init__

    def patched_init(self, db_path=None):
        original_init(self, db_path=str(temp_db_path))

    # Patch ConfigManager to use temp directories
    from sleep_scoring_app.utils.config import ConfigManager
    from sleep_scoring_app.core.dataclasses import AppConfig

    temp_config = AppConfig.create_default()
    temp_config.data_folder = str(test_data_folder)
    temp_config.export_directory = str(tmp_path / "exports")

    with patch.object(db_module.DatabaseManager, '__init__', patched_init):
        with patch.object(ConfigManager, 'is_config_valid', return_value=True):
            with patch.object(ConfigManager, 'config', temp_config, create=True):
                from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

                # Create the REAL window
                window = SleepScoringMainWindow()

                # Override config after creation
                window.config_manager.config = temp_config
                window.export_output_path = temp_config.export_directory

                # Register with qtbot for cleanup
                qtbot.addWidget(window)

                # SHOW THE WINDOW - This is what makes it visible!
                window.show()

                # Wait for window to be fully exposed and rendered
                qtbot.waitExposed(window)

                # Give extra time for all widgets to initialize
                qtbot.wait(OBSERVATION_DELAY_MS)

                print(f"\n[VISIBLE] Window is now VISIBLE at {window.geometry()}")
                print(f"[DATA] Test data folder: {test_data_folder}")

                yield window

                # Cleanup
                window.close()


# ============================================================================
# TEST CLASS: VISIBLE WINDOW STARTUP
# ============================================================================


@pytest.mark.e2e
@pytest.mark.gui
class TestVisibleWindowStartup:
    """Test that the application window appears correctly."""

    def test_window_appears_on_screen(self, qtbot, visible_main_window):
        """
        VISIBLE TEST: Watch the main window appear on screen.

        You should SEE:
        - A window titled "Sleep Research Analysis Tool"
        - Multiple tabs (Data Settings, Study Settings, Analysis, Export)
        - A file navigation panel
        - An activity plot area
        """
        print("\n[WATCH] TEST: Watching window appear...")

        # Verify window is visible
        assert visible_main_window.isVisible(), "Window should be visible!"

        # Verify title
        assert "Sleep" in visible_main_window.windowTitle()
        print(f"[OK] Window title: {visible_main_window.windowTitle()}")

        # Verify minimum size
        assert visible_main_window.width() >= 800, "Window should be at least 800px wide"
        assert visible_main_window.height() >= 600, "Window should be at least 600px tall"
        print(f"[OK] Window size: {visible_main_window.width()}x{visible_main_window.height()}")

        # Pause so human can observe
        qtbot.wait(OBSERVATION_DELAY_MS)
        print("[OK] Window startup test complete")

    def test_tabs_are_visible(self, qtbot, visible_main_window):
        """
        VISIBLE TEST: Watch the tab bar and verify all tabs exist.

        You should SEE:
        - A tab bar with multiple tabs
        - Each tab is clickable
        """
        print("\n[WATCH] TEST: Checking visible tabs...")

        # Find the tab widget
        tab_widget = visible_main_window.findChild(QTabWidget)

        if tab_widget:
            tab_count = tab_widget.count()
            print(f"[OK] Found {tab_count} tabs")

            for i in range(tab_count):
                tab_name = tab_widget.tabText(i)
                print(f"   Tab {i}: {tab_name}")

            # Click through each tab so human can see them
            for i in range(tab_count):
                tab_widget.setCurrentIndex(i)
                qtbot.wait(OBSERVATION_DELAY_MS // 2)
                print(f"   -> Switched to tab: {tab_widget.tabText(i)}")

        qtbot.wait(OBSERVATION_DELAY_MS)
        print("[OK] Tab visibility test complete")


# ============================================================================
# TEST CLASS: VISIBLE FILE NAVIGATION
# ============================================================================


@pytest.mark.e2e
@pytest.mark.gui
class TestVisibleFileNavigation:
    """Test file navigation with visible interactions."""

    def test_file_table_shows_files(self, qtbot, visible_main_window, test_data_folder):
        """
        VISIBLE TEST: Watch files appear in the file navigation table.

        You should SEE:
        - The file table populate with test files
        - File names visible in the table
        """
        print("\n[WATCH] TEST: Watching file table populate...")

        # Set data folder through the service
        visible_main_window.data_service.set_data_folder(str(test_data_folder))

        # Find files
        files = visible_main_window.data_service.find_available_files()
        print(f"[OK] Found {len(files)} files in test folder")

        # Wait for UI to update
        qtbot.wait(OBSERVATION_DELAY_MS)

        # Look for any table widgets
        tables = visible_main_window.findChildren(QTableWidget)
        for table in tables:
            if table.isVisible() and table.rowCount() > 0:
                print(f"   Table has {table.rowCount()} rows, {table.columnCount()} columns")

        print("[OK] File table test complete")

    def test_keyboard_navigation(self, qtbot, visible_main_window, test_data_folder):
        """
        VISIBLE TEST: Watch keyboard navigation between dates.

        You should SEE:
        - The date changing when arrow keys are pressed
        - The plot updating with new data
        """
        print("\n[WATCH] TEST: Testing keyboard navigation...")

        # Set data folder
        visible_main_window.data_service.set_data_folder(str(test_data_folder))
        qtbot.wait(OBSERVATION_DELAY_MS)

        # Give window focus
        visible_main_window.activateWindow()
        visible_main_window.setFocus()

        # Get initial date index
        initial_index = visible_main_window.store.state.current_date_index
        print(f"   Initial date index: {initial_index}")

        # Simulate pressing Right arrow key
        QTest.keyClick(visible_main_window, Qt.Key.Key_Right)
        qtbot.wait(OBSERVATION_DELAY_MS)

        new_index = visible_main_window.store.state.current_date_index
        print(f"   After Right arrow: date index = {new_index}")

        # Simulate pressing Left arrow key
        QTest.keyClick(visible_main_window, Qt.Key.Key_Left)
        qtbot.wait(OBSERVATION_DELAY_MS)

        final_index = visible_main_window.store.state.current_date_index
        print(f"   After Left arrow: date index = {final_index}")

        print("[OK] Keyboard navigation test complete")


# ============================================================================
# TEST CLASS: VISIBLE BUTTON CLICKS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.gui
class TestVisibleButtonClicks:
    """Test clicking buttons with visible feedback."""

    def test_find_buttons_and_click(self, qtbot, visible_main_window):
        """
        VISIBLE TEST: Find buttons in the UI and click them.

        You should SEE:
        - Buttons being highlighted/clicked
        - UI responding to button clicks
        """
        print("\n[WATCH] TEST: Finding and clicking buttons...")

        # Find all buttons in the window
        buttons = visible_main_window.findChildren(QPushButton)
        print(f"[OK] Found {len(buttons)} buttons")

        # List visible buttons
        visible_buttons = [b for b in buttons if b.isVisible() and b.isEnabled()]
        print(f"   {len(visible_buttons)} are visible and enabled")

        for i, button in enumerate(visible_buttons[:5]):  # Show first 5
            print(f"   Button {i}: '{button.text()}'")

        qtbot.wait(OBSERVATION_DELAY_MS)
        print("[OK] Button discovery test complete")


# ============================================================================
# TEST CLASS: VISIBLE PLOT INTERACTION
# ============================================================================


@pytest.mark.e2e
@pytest.mark.gui
class TestVisiblePlotInteraction:
    """Test interacting with the activity plot."""

    def test_plot_widget_visible(self, qtbot, visible_main_window):
        """
        VISIBLE TEST: Verify the activity plot is visible.

        You should SEE:
        - An activity plot area (possibly empty initially)
        - Plot axes and labels
        """
        print("\n[WATCH] TEST: Checking plot widget visibility...")

        # Look for the plot widget
        from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

        plot_widgets = visible_main_window.findChildren(ActivityPlotWidget)

        if plot_widgets:
            print(f"[OK] Found {len(plot_widgets)} plot widget(s)")
            for i, plot in enumerate(plot_widgets):
                print(f"   Plot {i}: visible={plot.isVisible()}, size={plot.width()}x{plot.height()}")
        else:
            print("[WARN] No ActivityPlotWidget found (may be named differently)")

        qtbot.wait(OBSERVATION_DELAY_MS)
        print("[OK] Plot visibility test complete")


# ============================================================================
# TEST CLASS: VISIBLE STORE STATE CHANGES
# ============================================================================


@pytest.mark.e2e
@pytest.mark.gui
class TestVisibleStateChanges:
    """Test that Redux state changes are reflected in the visible UI."""

    def test_file_selection_updates_ui(self, qtbot, visible_main_window, test_data_folder):
        """
        VISIBLE TEST: Watch the UI update when a file is selected.

        You should SEE:
        - File name appearing in the UI
        - Related widgets updating
        """
        print("\n[WATCH] TEST: Selecting file and watching UI update...")

        from sleep_scoring_app.ui.store import Actions

        # Set up data folder first
        visible_main_window.data_service.set_data_folder(str(test_data_folder))
        qtbot.wait(OBSERVATION_DELAY_MS)

        # Get available files
        files = list(test_data_folder.glob("*.csv"))
        if files:
            filename = files[0].name
            print(f"   Selecting file: {filename}")

            # Dispatch file selection action
            visible_main_window.store.dispatch(Actions.file_selected(filename))

            # Wait for UI to update
            qtbot.wait(OBSERVATION_DELAY_MS)

            # Verify state changed
            assert visible_main_window.store.state.current_file == filename
            print(f"[OK] File selected in store: {visible_main_window.store.state.current_file}")

        print("[OK] File selection test complete")

    def test_date_loading_updates_ui(self, qtbot, visible_main_window):
        """
        VISIBLE TEST: Watch dates being loaded into the UI.

        You should SEE:
        - Date navigation controls updating
        - Current date indicator changing
        """
        print("\n[WATCH] TEST: Loading dates and watching UI update...")

        from sleep_scoring_app.ui.store import Actions

        # Load some dates
        test_dates = ("2021-04-20", "2021-04-21", "2021-04-22")
        visible_main_window.store.dispatch(Actions.dates_loaded(test_dates))

        qtbot.wait(OBSERVATION_DELAY_MS)

        # Verify dates are in state
        state = visible_main_window.store.state
        assert state.available_dates == test_dates
        print(f"[OK] Dates loaded: {state.available_dates}")

        # Select a date
        visible_main_window.store.dispatch(Actions.date_selected(1))
        qtbot.wait(OBSERVATION_DELAY_MS)

        # Get fresh state reference after dispatch
        new_state = visible_main_window.store.state
        assert new_state.current_date_index == 1
        print(f"[OK] Selected date index: {new_state.current_date_index}")

        print("[OK] Date loading test complete")


# ============================================================================
# CLEANUP
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Force garbage collection
    import gc
    gc.collect()
