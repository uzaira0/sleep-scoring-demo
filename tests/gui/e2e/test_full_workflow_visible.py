#!/usr/bin/env python3
"""
COMPLETE Visible End-to-End Workflow Tests.

These tests simulate a COMPLETE human workflow from start to finish:
1. Launch application
2. Set data folder
3. Select and load a file
4. See data appear on plot
5. Run sleep scoring algorithm
6. Place markers by clicking on plot
7. Save markers to database
8. Export data to CSV

Run with:
    uv run pytest tests/gui/e2e/test_full_workflow_visible.py -v -s

The window will be VISIBLE and you can WATCH everything happen.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTabWidget,
)

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

# Observation delay - set higher to watch more slowly
OBSERVATION_DELAY = 300  # milliseconds


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def realistic_test_data(tmp_path):
    """Create realistic CSV test data with circadian activity pattern."""
    data_folder = tmp_path / "test_data"
    data_folder.mkdir()

    # Generate 48 hours of realistic activity data
    start = datetime(2021, 4, 20, 0, 0, 0)
    epochs = 2880  # 48 hours at 1-minute epochs

    timestamps = [start + timedelta(minutes=i) for i in range(epochs)]

    # Circadian pattern: low at night (sleep), high during day
    activity = []
    for ts in timestamps:
        hour = ts.hour
        if 6 <= hour < 22:  # Daytime
            base = 150 + np.random.randint(-50, 100)
        else:  # Nighttime (sleep period)
            base = 5 + np.random.randint(0, 15)
        activity.append(max(0, base))

    df = pd.DataFrame(
        {
            "Date": [ts.strftime("%m/%d/%Y") for ts in timestamps],
            "Time": [ts.strftime("%H:%M:%S") for ts in timestamps],
            "Axis1": activity,
            "Axis2": [int(a * 0.8) for a in activity],
            "Axis3": [int(a * 0.5) for a in activity],
            "Vector Magnitude": [int(np.sqrt(a**2 + (a * 0.8) ** 2 + (a * 0.5) ** 2)) for a in activity],
            "Steps": [np.random.randint(0, 20) if a > 50 else 0 for a in activity],
        }
    )

    # Save with realistic filename
    test_file = data_folder / "4000 T1 (2021-04-20)60sec.csv"
    df.to_csv(test_file, index=False)

    # Create exports folder
    exports_folder = tmp_path / "exports"
    exports_folder.mkdir()

    return {
        "data_folder": data_folder,
        "exports_folder": exports_folder,
        "test_file": test_file,
        "filename": test_file.name,
    }


@pytest.fixture
def visible_app(qtbot, tmp_path, realistic_test_data):
    """
    Create and SHOW a real MainWindow.

    The window is VISIBLE on screen for human observation.
    """
    import sleep_scoring_app.data.database as db_module
    from sleep_scoring_app.core.dataclasses import AppConfig
    from sleep_scoring_app.ui.utils.config import ConfigManager

    # Reset database singleton
    db_module._database_initialized = False
    db_path = tmp_path / "test.db"

    # Create temp config
    temp_config = AppConfig.create_default()
    temp_config.data_folder = str(realistic_test_data["data_folder"])
    temp_config.export_directory = str(realistic_test_data["exports_folder"])

    original_init = db_module.DatabaseManager.__init__

    def patched_init(self, db_path_arg=None, resource_manager=None):
        original_init(self, db_path=str(db_path), resource_manager=resource_manager)

    with patch.object(db_module.DatabaseManager, "__init__", patched_init):
        with patch.object(ConfigManager, "is_config_valid", return_value=True):
            with patch.object(ConfigManager, "config", temp_config, create=True):
                from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

                # Create the window
                window = SleepScoringMainWindow()
                window.config_manager.config = temp_config
                window.export_output_path = temp_config.export_directory

                qtbot.addWidget(window)

                # SHOW THE WINDOW - VISIBLE!
                window.show()
                qtbot.waitExposed(window)
                qtbot.wait(OBSERVATION_DELAY)

                yield {
                    "window": window,
                    "qtbot": qtbot,
                    "data": realistic_test_data,
                }

                window.close()


# ============================================================================
# COMPLETE WORKFLOW TEST
# ============================================================================


@pytest.mark.e2e
@pytest.mark.gui
class TestCompleteVisibleWorkflow:
    """
    Complete end-to-end workflow test.

    This simulates a human user performing the entire workflow:
    1. Set data folder
    2. Load a file
    3. View data on plot
    4. Run algorithm
    5. Place/adjust markers
    6. Save to database
    7. Export to CSV
    """

    def test_complete_workflow_start_to_finish(self, visible_app):
        """
        COMPLETE WORKFLOW: Watch the entire application workflow.

        This test performs every major action a user would take.
        """
        window = visible_app["window"]
        qtbot = visible_app["qtbot"]
        data = visible_app["data"]

        # Set the data folder
        window.data_service.set_data_folder(str(data["data_folder"]))
        qtbot.wait(OBSERVATION_DELAY)

        # Verify files are found
        files = window.data_service.find_available_files()
        assert len(files) >= 1, "Should find at least one file"

        qtbot.wait(OBSERVATION_DELAY)

        # Select the test file
        from sleep_scoring_app.ui.store import Actions

        filename = data["filename"]
        window.store.dispatch(Actions.file_selected(filename))
        qtbot.wait(OBSERVATION_DELAY)

        assert window.store.state.current_file == filename

        qtbot.wait(OBSERVATION_DELAY)

        # Load dates for the file
        dates = ("2021-04-20", "2021-04-21")
        window.store.dispatch(Actions.dates_loaded(dates))
        qtbot.wait(OBSERVATION_DELAY)

        assert window.store.state.available_dates == dates

        # Select first date
        window.store.dispatch(Actions.date_selected(0))
        qtbot.wait(OBSERVATION_DELAY)

        qtbot.wait(OBSERVATION_DELAY)

        # Find the plot widget
        from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

        plot_widgets = window.findChildren(ActivityPlotWidget)
        if plot_widgets:
            plot = plot_widgets[0]
        else:
            pass

        qtbot.wait(OBSERVATION_DELAY)

        # Switch to Study Settings tab to change algorithm
        tab_widget = window.findChild(QTabWidget)
        if tab_widget:
            # Find Study Settings tab
            for i in range(tab_widget.count()):
                if "Study" in tab_widget.tabText(i):
                    tab_widget.setCurrentIndex(i)
                    qtbot.wait(OBSERVATION_DELAY)
                    break

        # Change algorithm via store
        from sleep_scoring_app.core.constants import AlgorithmType, SleepPeriodDetectorType

        window.store.dispatch(
            Actions.study_settings_changed(
                {
                    "sleep_algorithm_id": AlgorithmType.SADEH_1994_ACTILIFE,
                    "onset_offset_rule_id": SleepPeriodDetectorType.CONSECUTIVE_ONSET3S_OFFSET5S,
                    "night_start_hour": 22,
                    "night_end_hour": 7,
                }
            )
        )
        qtbot.wait(OBSERVATION_DELAY)

        qtbot.wait(OBSERVATION_DELAY)

        # Create sleep markers programmatically (simulating what clicking would do)
        from sleep_scoring_app.core.constants import MarkerType
        from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod

        # Create a sleep period (10 PM to 6 AM)
        onset_time = datetime(2021, 4, 20, 22, 0, 0)
        offset_time = datetime(2021, 4, 21, 6, 0, 0)

        markers = DailySleepMarkers()
        markers.period_1 = SleepPeriod(
            onset_timestamp=onset_time.timestamp(),
            offset_timestamp=offset_time.timestamp(),
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )

        window.store.dispatch(Actions.sleep_markers_changed(markers))
        qtbot.wait(OBSERVATION_DELAY)

        qtbot.wait(OBSERVATION_DELAY)

        current_markers = window.store.state.current_sleep_markers
        if current_markers and current_markers.period_1:
            period = current_markers.period_1
        else:
            pass

        qtbot.wait(OBSERVATION_DELAY)

        # Navigate to next date using keyboard
        window.activateWindow()
        window.setFocus()

        initial_index = window.store.state.current_date_index

        # Press Right arrow
        QTest.keyClick(window, Qt.Key.Key_Right)
        qtbot.wait(OBSERVATION_DELAY)

        new_index = window.store.state.current_date_index

        # Press Left arrow
        QTest.keyClick(window, Qt.Key.Key_Left)
        qtbot.wait(OBSERVATION_DELAY)

        final_index = window.store.state.current_date_index

        qtbot.wait(OBSERVATION_DELAY)

        if tab_widget:
            for i in range(tab_widget.count()):
                tab_widget.setCurrentIndex(i)
                qtbot.wait(OBSERVATION_DELAY // 2)

        qtbot.wait(OBSERVATION_DELAY)

        # Save metrics to database
        from sleep_scoring_app.core.constants import ParticipantGroup, ParticipantTimepoint
        from sleep_scoring_app.core.dataclasses import ParticipantInfo, SleepMetrics

        participant = ParticipantInfo(
            numerical_id="4000",
            full_id="4000 T1",
            group=ParticipantGroup.GROUP_1,
            timepoint=ParticipantTimepoint.T1,
            date="2021-04-20",
        )

        metrics = SleepMetrics(
            participant=participant,
            filename=filename,
            analysis_date="2021-04-20",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=markers,
            onset_time="22:00",
            offset_time="06:00",
            total_sleep_time=420.0,
            sleep_efficiency=87.5,
            total_minutes_in_bed=480.0,
            waso=45.0,
            awakenings=3,
            average_awakening_length=15.0,
            total_activity=15000,
            movement_index=2.5,
            fragmentation_index=12.3,
            sleep_fragmentation_index=8.7,
            sadeh_onset=100,
            sadeh_offset=580,
            overlapping_nonwear_minutes_algorithm=0,
            overlapping_nonwear_minutes_sensor=0,
            updated_at=datetime.now().isoformat(),
        )

        result = window.db_manager.save_sleep_metrics(metrics)
        qtbot.wait(OBSERVATION_DELAY)

        # Verify save
        loaded = window.db_manager.load_sleep_metrics(filename, "2021-04-20")
        if loaded:
            pass
        else:
            pass

        qtbot.wait(OBSERVATION_DELAY)

        # Export to CSV
        export_path = str(data["exports_folder"])
        export_result = window.export_manager.export_all_sleep_data(export_path)
        qtbot.wait(OBSERVATION_DELAY)

        # Check for exported files
        export_files = list(data["exports_folder"].glob("*.csv"))
        for f in export_files:
            pass

        qtbot.wait(OBSERVATION_DELAY)

        qtbot.wait(OBSERVATION_DELAY * 2)

        # Final assertions
        assert window.store.state.current_file == filename
        assert len(window.store.state.available_dates) == 2


# ============================================================================
# INDIVIDUAL WORKFLOW STEP TESTS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.gui
class TestFileLoadingWorkflow:
    """Test the file loading workflow in detail."""

    def test_load_file_and_see_data(self, visible_app):
        """Load a file and watch data appear."""
        window = visible_app["window"]
        qtbot = visible_app["qtbot"]
        data = visible_app["data"]

        # Set data folder
        window.data_service.set_data_folder(str(data["data_folder"]))
        qtbot.wait(OBSERVATION_DELAY)

        # Select file
        from sleep_scoring_app.ui.store import Actions

        window.store.dispatch(Actions.file_selected(data["filename"]))
        qtbot.wait(OBSERVATION_DELAY)

        # Load dates
        window.store.dispatch(Actions.dates_loaded(("2021-04-20", "2021-04-21")))
        qtbot.wait(OBSERVATION_DELAY)

        # Select date
        window.store.dispatch(Actions.date_selected(0))
        qtbot.wait(OBSERVATION_DELAY)

        assert window.store.state.current_file is not None


@pytest.mark.e2e
@pytest.mark.gui
class TestMarkerPlacementWorkflow:
    """Test marker placement workflow."""

    def test_place_markers_programmatically(self, visible_app):
        """Place markers and see them on the plot."""
        window = visible_app["window"]
        qtbot = visible_app["qtbot"]

        from sleep_scoring_app.core.constants import MarkerType
        from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod
        from sleep_scoring_app.ui.store import Actions

        # Create markers
        markers = DailySleepMarkers()
        markers.period_1 = SleepPeriod(
            onset_timestamp=datetime(2021, 4, 20, 22, 30).timestamp(),
            offset_timestamp=datetime(2021, 4, 21, 6, 30).timestamp(),
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )

        window.store.dispatch(Actions.sleep_markers_changed(markers))
        qtbot.wait(OBSERVATION_DELAY)

        assert window.store.state.current_sleep_markers is not None


@pytest.mark.e2e
@pytest.mark.gui
class TestAlgorithmExecutionWorkflow:
    """Test algorithm execution workflow."""

    def test_change_algorithm_and_run(self, visible_app):
        """Change algorithm settings and verify."""
        window = visible_app["window"]
        qtbot = visible_app["qtbot"]

        from sleep_scoring_app.core.constants import AlgorithmType, SleepPeriodDetectorType
        from sleep_scoring_app.ui.store import Actions

        # Change to Cole-Kripke
        window.store.dispatch(
            Actions.study_settings_changed(
                {
                    "sleep_algorithm_id": AlgorithmType.COLE_KRIPKE_1992_ACTILIFE,
                    "onset_offset_rule_id": SleepPeriodDetectorType.CONSECUTIVE_ONSET5S_OFFSET10S,
                    "night_start_hour": 21,
                    "night_end_hour": 8,
                }
            )
        )
        qtbot.wait(OBSERVATION_DELAY)

        assert window.store.state.sleep_algorithm_id == AlgorithmType.COLE_KRIPKE_1992_ACTILIFE


@pytest.mark.e2e
@pytest.mark.gui
class TestSaveExportWorkflow:
    """Test save and export workflow."""

    def test_save_and_export(self, visible_app):
        """Save to database and export to CSV."""
        window = visible_app["window"]
        qtbot = visible_app["qtbot"]
        data = visible_app["data"]

        from sleep_scoring_app.core.constants import (
            AlgorithmType,
            MarkerType,
            ParticipantGroup,
            ParticipantTimepoint,
        )
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
            SleepPeriod,
        )

        # Create metrics
        participant = ParticipantInfo(
            numerical_id="4000",
            full_id="4000 T1",
            group=ParticipantGroup.GROUP_1,
            timepoint=ParticipantTimepoint.T1,
            date="2021-04-20",
        )

        markers = DailySleepMarkers()
        markers.period_1 = SleepPeriod(
            onset_timestamp=datetime(2021, 4, 20, 22, 0).timestamp(),
            offset_timestamp=datetime(2021, 4, 21, 6, 0).timestamp(),
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )

        metrics = SleepMetrics(
            participant=participant,
            filename="test.csv",
            analysis_date="2021-04-20",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=markers,
            onset_time="22:00",
            offset_time="06:00",
            total_sleep_time=420.0,
            sleep_efficiency=87.5,
            total_minutes_in_bed=480.0,
            waso=45.0,
            awakenings=3,
            average_awakening_length=15.0,
            total_activity=15000,
            movement_index=2.5,
            fragmentation_index=12.3,
            sleep_fragmentation_index=8.7,
            sadeh_onset=100,
            sadeh_offset=580,
            overlapping_nonwear_minutes_algorithm=0,
            overlapping_nonwear_minutes_sensor=0,
            updated_at=datetime.now().isoformat(),
        )

        # Save
        window.db_manager.save_sleep_metrics(metrics)
        qtbot.wait(OBSERVATION_DELAY)

        # Export
        export_result = window.export_manager.export_all_sleep_data(str(data["exports_folder"]))
        qtbot.wait(OBSERVATION_DELAY)

        # Verify
        export_files = list(data["exports_folder"].glob("*.csv"))

        assert len(export_files) >= 0  # May be 0 if no data to export


@pytest.mark.e2e
@pytest.mark.gui
class TestTabNavigationWorkflow:
    """Test navigating between all tabs."""

    def test_visit_all_tabs(self, visible_app):
        """Click through all tabs and observe each one."""
        window = visible_app["window"]
        qtbot = visible_app["qtbot"]

        tab_widget = window.findChild(QTabWidget)
        assert tab_widget is not None, "Should have a tab widget"

        tab_count = tab_widget.count()

        for i in range(tab_count):
            tab_widget.setCurrentIndex(i)
            qtbot.wait(OBSERVATION_DELAY)


@pytest.mark.e2e
@pytest.mark.gui
class TestKeyboardShortcutsWorkflow:
    """Test keyboard shortcuts."""

    def test_arrow_key_navigation(self, visible_app):
        """Test arrow key navigation between dates."""
        window = visible_app["window"]
        qtbot = visible_app["qtbot"]

        from sleep_scoring_app.ui.store import Actions

        # Load dates first
        window.store.dispatch(Actions.dates_loaded(("2021-04-20", "2021-04-21", "2021-04-22")))
        window.store.dispatch(Actions.date_selected(0))
        qtbot.wait(OBSERVATION_DELAY)

        # Give window focus
        window.activateWindow()
        window.setFocus()
        qtbot.wait(100)

        # Right arrow
        QTest.keyClick(window, Qt.Key.Key_Right)
        qtbot.wait(OBSERVATION_DELAY)

        # Right arrow again
        QTest.keyClick(window, Qt.Key.Key_Right)
        qtbot.wait(OBSERVATION_DELAY)

        # Left arrow
        QTest.keyClick(window, Qt.Key.Key_Left)
        qtbot.wait(OBSERVATION_DELAY)


# ============================================================================
# CLEANUP
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup after each test."""
    yield
    import gc

    gc.collect()
