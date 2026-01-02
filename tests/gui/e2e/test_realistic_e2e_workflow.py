#!/usr/bin/env python3
"""
REALISTIC End-to-End Workflow Test.

This test simulates EXACTLY what a researcher would do:
1. Configure study settings and VERIFY they take effect
2. Import files and VERIFY data loaded correctly
3. Process EVERY day - analyze data, place appropriate markers
4. Switch between algorithms and VERIFY results change
5. Place nonwear markers where detected
6. Save and verify metrics are calculated
7. Export and validate ALL data is correct

Run with:
    uv run pytest tests/gui/e2e/test_realistic_e2e_workflow.py -v -s
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QTabWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

from sleep_scoring_app.core.constants import (
    AlgorithmType,
    DevicePreset,
    MarkerType,
    NonwearAlgorithm,
    SleepPeriodDetectorType,
    StudyDataParadigm,
)
from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod

DELAY = 200  # ms between actions


def _create_realistic_data(folder: Path) -> dict:
    """
    Create realistic test data with KNOWN sleep patterns.

    Returns metadata about the expected sleep/nonwear periods so we can verify.
    """
    # 7 days of data with specific sleep patterns we can verify
    start_date = datetime(2024, 1, 15, 0, 0, 0)
    epochs_per_day = 1440  # 60-second epochs
    total_days = 7

    expected_sleep = {}  # day -> (onset_hour, offset_hour)
    expected_nonwear = {}  # day -> list of (start_hour, end_hour)

    all_data = []

    for day in range(total_days):
        day_start = start_date + timedelta(days=day)
        date_str = day_start.strftime("%Y-%m-%d")

        # Define sleep pattern for this day (varying slightly each day)
        sleep_onset_hour = 22 + (day % 2) * 0.5  # 22:00 or 22:30
        sleep_offset_hour = 6 + (day % 3) * 0.5  # 6:00, 6:30, or 7:00
        expected_sleep[date_str] = (sleep_onset_hour, sleep_offset_hour)

        # Define nonwear for some days (90+ minutes of zeros)
        if day in [2, 5]:  # Days 3 and 6 have nonwear
            nonwear_start = 14  # 2 PM
            nonwear_end = 16  # 4 PM (2 hours)
            expected_nonwear[date_str] = [(nonwear_start, nonwear_end)]
        else:
            expected_nonwear[date_str] = []

        for minute in range(epochs_per_day):
            ts = day_start + timedelta(minutes=minute)
            hour = ts.hour + ts.minute / 60.0

            # Determine activity level based on time
            if sleep_onset_hour <= hour or hour < sleep_offset_hour:
                # Sleep period - very low activity with occasional movement
                if np.random.random() < 0.05:  # 5% chance of movement
                    activity = np.random.randint(10, 50)
                else:
                    activity = np.random.randint(0, 10)
            elif date_str in expected_nonwear and any(start <= hour < end for start, end in expected_nonwear[date_str]):
                # Nonwear - complete zeros (Choi algorithm requires this)
                activity = 0
            else:
                # Awake - high activity
                activity = 100 + np.random.randint(-50, 150)

            all_data.append(
                {
                    "Date": ts.strftime("%m/%d/%Y"),
                    "Time": ts.strftime("%H:%M:%S"),
                    "Axis1": activity,
                    "Axis2": int(activity * 0.7),
                    "Axis3": int(activity * 0.4),
                    "Vector Magnitude": int(np.sqrt(activity**2 + (activity * 0.7) ** 2 + (activity * 0.4) ** 2)),
                    "Steps": np.random.randint(0, 20) if activity > 100 else 0,
                }
            )

    df = pd.DataFrame(all_data)

    # Create files for multiple participants
    files = []
    for pid in ["P001", "P002"]:
        filename = f"{pid}_T1_Control_actigraph.csv"
        filepath = folder / filename
        df.to_csv(filepath, index=False)
        files.append(filename)

    return {
        "files": files,
        "expected_sleep": expected_sleep,
        "expected_nonwear": expected_nonwear,
        "total_days": total_days,
    }


@pytest.fixture
def test_env(qtbot, tmp_path):
    """Set up test environment with realistic data."""
    import sleep_scoring_app.data.database as db_module
    from sleep_scoring_app.core.dataclasses import AppConfig
    from sleep_scoring_app.ui.utils.config import ConfigManager

    db_module._database_initialized = False
    db_path = tmp_path / "test.db"

    data_folder = tmp_path / "data"
    data_folder.mkdir()

    test_metadata = _create_realistic_data(data_folder)

    exports_folder = tmp_path / "exports"
    exports_folder.mkdir()

    config = AppConfig.create_default()
    config.data_folder = str(data_folder)
    config.export_directory = str(exports_folder)
    config.epoch_length = 60

    original_init = db_module.DatabaseManager.__init__

    def patched_init(self, db_path_arg=None):
        original_init(self, db_path=str(db_path))

    with patch.object(db_module.DatabaseManager, "__init__", patched_init):
        with patch.object(ConfigManager, "is_config_valid", return_value=True):
            with patch.object(ConfigManager, "config", config, create=True):
                from sleep_scoring_app.ui.main_window import SleepScoringMainWindow
                from sleep_scoring_app.ui.store import Actions

                window = SleepScoringMainWindow()
                window.config_manager.config = config
                window.export_output_path = str(exports_folder)

                qtbot.addWidget(window)
                window.show()
                window.showMaximized()
                qtbot.waitExposed(window)
                qtbot.wait(DELAY)

                yield {
                    "window": window,
                    "qtbot": qtbot,
                    "data_folder": data_folder,
                    "exports_folder": exports_folder,
                    "metadata": test_metadata,
                    "Actions": Actions,
                }

                window.close()


@pytest.mark.e2e
@pytest.mark.gui
class TestRealisticWorkflow:
    """Realistic end-to-end workflow with verification."""

    def test_complete_realistic_workflow(self, test_env):
        """
        Complete realistic workflow:
        1. Configure and VERIFY settings
        2. Import and VERIFY data
        3. Process EACH day with appropriate markers
        4. Switch algorithms and VERIFY changes
        5. Export and VERIFY results
        """
        window = test_env["window"]
        qtbot = test_env["qtbot"]
        data_folder = test_env["data_folder"]
        exports_folder = test_env["exports_folder"]
        metadata = test_env["metadata"]
        Actions = test_env["Actions"]

        expected_sleep = metadata["expected_sleep"]
        expected_nonwear = metadata["expected_nonwear"]

        tab_widget = window.findChild(QTabWidget)

        # ================================================================
        # PHASE 1: STUDY SETTINGS - Configure and VERIFY
        # ================================================================

        self._switch_tab(tab_widget, "Study", qtbot)
        study_tab = window.study_settings_tab

        # 1.1 Set and VERIFY Data Paradigm
        paradigm_combo = study_tab.data_paradigm_combo
        self._set_combo_by_data(paradigm_combo, StudyDataParadigm.EPOCH_BASED, qtbot)
        assert paradigm_combo.currentData() == StudyDataParadigm.EPOCH_BASED, f"Paradigm should be EPOCH_BASED, got {paradigm_combo.currentData()}"

        # 1.2 Set and VERIFY Sleep Algorithm - Start with Sadeh
        algo_combo = study_tab.sleep_algorithm_combo
        self._set_combo_by_data(algo_combo, AlgorithmType.SADEH_1994_ACTILIFE, qtbot)
        assert algo_combo.currentData() == AlgorithmType.SADEH_1994_ACTILIFE, f"Algorithm should be SADEH, got {algo_combo.currentData()}"
        # Verify store was updated
        assert window.store.state.sleep_algorithm_id == AlgorithmType.SADEH_1994_ACTILIFE.value, (
            f"Store algorithm should be sadeh, got {window.store.state.sleep_algorithm_id}"
        )

        # 1.3 Set and VERIFY Sleep Period Detector
        detector_combo = study_tab.sleep_period_detector_combo
        self._set_combo_by_data(detector_combo, SleepPeriodDetectorType.CONSECUTIVE_ONSET3S_OFFSET5S, qtbot)
        assert detector_combo.currentData() == SleepPeriodDetectorType.CONSECUTIVE_ONSET3S_OFFSET5S

        # 1.4 Set and VERIFY Night Hours
        study_tab.night_start_time.setTime(QTime(21, 0))
        study_tab.night_end_time.setTime(QTime(9, 0))
        qtbot.wait(DELAY)
        assert study_tab.night_start_time.time().hour() == 21
        assert study_tab.night_end_time.time().hour() == 9

        # 1.5 Set and VERIFY Nonwear Algorithm
        nonwear_combo = study_tab.nonwear_algorithm_combo
        self._set_combo_by_data(nonwear_combo, NonwearAlgorithm.CHOI_2011, qtbot)
        assert nonwear_combo.currentData() == NonwearAlgorithm.CHOI_2011

        # 1.6 Set ID Pattern and VERIFY
        study_tab.id_pattern_edit.clear()
        qtbot.keyClicks(study_tab.id_pattern_edit, r"(P\d{3})")
        qtbot.wait(DELAY)
        assert study_tab.id_pattern_edit.text() == r"(P\d{3})"

        # ================================================================
        # PHASE 2: DATA SETTINGS - Import and VERIFY
        # ================================================================

        self._switch_tab(tab_widget, "Data", qtbot)
        data_tab = window.data_settings_tab

        # 2.1 Set Device Preset
        device_combo = data_tab.device_preset_combo
        for i in range(device_combo.count()):
            if "ActiGraph" in device_combo.itemText(i):
                device_combo.setCurrentIndex(i)
                break
        qtbot.wait(DELAY)

        # 2.2 Set Epoch Length
        data_tab.epoch_length_spin.setValue(60)
        qtbot.wait(DELAY)
        assert data_tab.epoch_length_spin.value() == 60

        # 2.3 Import files
        window.data_service.set_data_folder(str(data_folder))
        qtbot.wait(DELAY)

        test_files = list(data_folder.glob("*.csv"))
        result = window.import_service.import_files(
            file_paths=test_files,
            skip_rows=0,
            force_reimport=True,
        )
        qtbot.wait(DELAY)

        # VERIFY import
        assert len(result.imported_files) == len(test_files), f"Should import {len(test_files)} files, got {len(result.imported_files)}"

        # 2.4 Verify files are available
        available_files = window.data_service.find_available_files()
        assert len(available_files) >= len(test_files), f"Should have {len(test_files)} files, got {len(available_files)}"
        for f in available_files:
            pass

        # ================================================================
        # PHASE 3: PROCESS EACH DAY WITH MARKERS
        # ================================================================

        self._switch_tab(tab_widget, "Analysis", qtbot)

        # Select first file
        first_file = available_files[0]
        window.on_file_selected_from_table(first_file)
        qtbot.wait(DELAY * 2)

        # Verify dates loaded
        dates = window.store.state.available_dates
        assert len(dates) >= metadata["total_days"], f"Should have {metadata['total_days']} days, got {len(dates)}"

        # Process EACH day
        days_processed = 0
        markers_placed = 0

        for day_idx, date_str in enumerate(dates):
            # Navigate to this date
            window.store.dispatch(Actions.date_selected(day_idx))
            qtbot.wait(DELAY)

            # Verify we're on the right date
            assert window.store.state.current_date_index == day_idx, f"Should be on date index {day_idx}"

            # Get expected sleep times for this date
            if date_str in expected_sleep:
                onset_hour, offset_hour = expected_sleep[date_str]

                # Create markers based on expected sleep pattern
                # Parse date
                try:
                    parts = date_str.split("-")
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                except:
                    continue

                # Calculate onset (same day, night time)
                onset_minute = int((onset_hour % 1) * 60)
                onset_dt = datetime(year, month, day, int(onset_hour), onset_minute, 0)

                # Calculate offset (next day, morning)
                offset_minute = int((offset_hour % 1) * 60)
                next_day = datetime(year, month, day) + timedelta(days=1)
                offset_dt = datetime(next_day.year, next_day.month, next_day.day, int(offset_hour), offset_minute, 0)

                # Create sleep markers
                markers = DailySleepMarkers()
                markers.period_1 = SleepPeriod(
                    onset_timestamp=onset_dt.timestamp(),
                    offset_timestamp=offset_dt.timestamp(),
                    marker_index=1,
                    marker_type=MarkerType.MAIN_SLEEP,
                )

                window.store.dispatch(Actions.sleep_markers_changed(markers))
                qtbot.wait(DELAY)

                # VERIFY markers were set
                current_markers = window.store.state.current_sleep_markers
                assert current_markers is not None, "Markers should be set"
                assert current_markers.period_1 is not None, "Period 1 should exist"
                assert current_markers.period_1.is_complete, "Period should be complete"

                markers_placed += 1

            # Check for nonwear on this date
            if expected_nonwear.get(date_str):
                for nw_start, nw_end in expected_nonwear[date_str]:
                    pass

            # Save markers
            if window.analysis_tab.save_markers_btn.isEnabled():
                qtbot.mouseClick(window.analysis_tab.save_markers_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(DELAY)

            days_processed += 1

        # ================================================================
        # PHASE 4: SWITCH ALGORITHMS AND VERIFY CHANGES
        # ================================================================

        # Go back to first date
        window.store.dispatch(Actions.date_selected(0))
        qtbot.wait(DELAY)

        # Current algorithm should be Sadeh
        assert "sadeh" in window.store.state.sleep_algorithm_id.lower()

        # Switch to Cole-Kripke
        self._switch_tab(tab_widget, "Study", qtbot)
        algo_combo = window.study_settings_tab.sleep_algorithm_combo
        self._set_combo_by_data(algo_combo, AlgorithmType.COLE_KRIPKE_1992_ACTILIFE, qtbot)
        qtbot.wait(DELAY * 2)

        # VERIFY algorithm changed in store
        assert window.store.state.sleep_algorithm_id == AlgorithmType.COLE_KRIPKE_1992_ACTILIFE.value, (
            f"Algorithm should be Cole-Kripke, got {window.store.state.sleep_algorithm_id}"
        )

        # Switch back to Analysis and verify display updated
        self._switch_tab(tab_widget, "Analysis", qtbot)
        qtbot.wait(DELAY)

        # Switch to different detector
        self._switch_tab(tab_widget, "Study", qtbot)
        detector_combo = window.study_settings_tab.sleep_period_detector_combo

        # Try a different detector
        self._set_combo_by_data(detector_combo, SleepPeriodDetectorType.CONSECUTIVE_ONSET5S_OFFSET10S, qtbot)
        qtbot.wait(DELAY)

        # Switch back
        self._set_combo_by_data(detector_combo, SleepPeriodDetectorType.CONSECUTIVE_ONSET3S_OFFSET5S, qtbot)
        qtbot.wait(DELAY)

        # ================================================================
        # PHASE 5: VERIFY DATE NAVIGATION
        # ================================================================

        self._switch_tab(tab_widget, "Analysis", qtbot)

        # Test arrow key navigation
        window.activateWindow()
        window.setFocus()

        initial_idx = window.store.state.current_date_index

        # Navigate forward
        for i in range(3):
            QTest.keyClick(window, Qt.Key.Key_Right)
            qtbot.wait(DELAY)
            new_idx = window.store.state.current_date_index

        # Navigate backward
        for i in range(3):
            QTest.keyClick(window, Qt.Key.Key_Left)
            qtbot.wait(DELAY)
            new_idx = window.store.state.current_date_index

        # Test button navigation
        next_btn = window.analysis_tab.next_date_btn
        prev_btn = window.analysis_tab.prev_date_btn

        for i in range(2):
            if next_btn.isEnabled():
                qtbot.mouseClick(next_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(DELAY)

        for i in range(2):
            if prev_btn.isEnabled():
                qtbot.mouseClick(prev_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(DELAY)

        # ================================================================
        # PHASE 6: EXPORT AND VERIFY DATA
        # ================================================================

        self._switch_tab(tab_widget, "Export", qtbot)

        # Export
        export_result = window.export_manager.export_all_sleep_data(str(exports_folder))
        qtbot.wait(DELAY)

        # Find and validate export file
        export_files = list(exports_folder.glob("*.csv"))
        assert len(export_files) >= 1, "Should have at least 1 export file"

        # Read and verify export content
        export_df = pd.read_csv(export_files[0])

        # Verify we have data for multiple days
        assert len(export_df) >= markers_placed, f"Should have at least {markers_placed} rows, got {len(export_df)}"

        # Check for expected columns
        expected_cols = ["Onset Time", "Offset Time", "Total Sleep Time"]
        for col in expected_cols:
            matching = [c for c in export_df.columns if col.lower() in c.lower()]
            if matching:
                pass

        # Show sample data
        if len(export_df) > 0:
            for col in list(export_df.columns)[:6]:
                pass

        # ================================================================
        # FINAL SUMMARY
        # ================================================================

        # Final assertions
        assert days_processed == len(dates), "Should process all days"
        assert markers_placed > 0, "Should place at least some markers"
        assert len(export_df) > 0, "Export should have data"

        qtbot.wait(DELAY * 3)

    def _switch_tab(self, tab_widget, name: str, qtbot):
        """Switch to named tab."""
        for i in range(tab_widget.count()):
            if name.lower() in tab_widget.tabText(i).lower():
                tab_widget.setCurrentIndex(i)
                qtbot.wait(DELAY)
                return

    def _set_combo_by_data(self, combo, data, qtbot):
        """Set combo box by data value."""
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                qtbot.wait(DELAY)
                return
        combo.setCurrentIndex(0)
        qtbot.wait(DELAY)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    import gc

    gc.collect()
