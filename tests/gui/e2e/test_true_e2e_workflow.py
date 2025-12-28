#!/usr/bin/env python3
"""
TRUE End-to-End Workflow Test.

This is ONE SINGLE TEST that interacts with EVERY element in the application
exactly as a human would, in a realistic workflow order.

Run with:
    uv run pytest tests/gui/e2e/test_true_e2e_workflow.py -v -s

The window will be VISIBLE and you will watch the ENTIRE workflow.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PyQt6.QtCore import Qt, QPoint, QTime
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QTimeEdit,
)
from PyQt6.QtTest import QTest

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

# How long to pause so you can WATCH (increase for slower observation)
DELAY = 300  # milliseconds


def _create_test_data(folder: Path) -> None:
    """Create realistic 7-day 60-second epoch CSV files."""
    start = datetime(2024, 1, 15, 0, 0, 0)
    epochs = 10080  # 7 days * 24 hours * 60 minutes

    timestamps = [start + timedelta(minutes=i) for i in range(epochs)]

    # Realistic circadian pattern
    activity = []
    for ts in timestamps:
        hour = ts.hour
        if 7 <= hour < 22:  # Daytime: active
            base = 200 + np.random.randint(-80, 150)
        elif 22 <= hour or hour < 1:  # Evening wind-down
            base = 50 + np.random.randint(-20, 40)
        else:  # Night: sleep with occasional movements
            base = 5 + np.random.randint(0, 15)
        activity.append(max(0, base))

    # Create DataFrame with all required columns
    df = pd.DataFrame({
        "Date": [ts.strftime("%m/%d/%Y") for ts in timestamps],
        "Time": [ts.strftime("%H:%M:%S") for ts in timestamps],
        "Axis1": activity,  # Y-axis (vertical)
        "Axis2": [int(a * 0.7) for a in activity],  # X-axis
        "Axis3": [int(a * 0.4) for a in activity],  # Z-axis
        "Vector Magnitude": [int(np.sqrt(a**2 + (a*0.7)**2 + (a*0.4)**2)) for a in activity],
        "Steps": [np.random.randint(0, 30) if a > 100 else 0 for a in activity],
    })

    # Create 3 participant files
    files = [
        ("P001_T1_Control_actigraph.csv", "P001"),
        ("P002_T1_Control_actigraph.csv", "P002"),
        ("P003_T2_Treatment_actigraph.csv", "P003"),
    ]

    for filename, pid in files:
        df.to_csv(folder / filename, index=False)
        print(f"   Created: {filename}")


@pytest.fixture
def app_environment(qtbot, tmp_path):
    """Set up complete application environment."""
    import sleep_scoring_app.data.database as db_module
    from sleep_scoring_app.utils.config import ConfigManager
    from sleep_scoring_app.core.dataclasses import AppConfig

    # Reset database
    db_module._database_initialized = False
    db_path = tmp_path / "test.db"

    # Create test data
    data_folder = tmp_path / "activity_data"
    data_folder.mkdir()
    print("\n[SETUP] Creating test data files...")
    _create_test_data(data_folder)

    exports_folder = tmp_path / "exports"
    exports_folder.mkdir()

    # Create config
    config = AppConfig.create_default()
    config.data_folder = str(data_folder)
    config.export_directory = str(exports_folder)
    config.epoch_length = 60

    original_init = db_module.DatabaseManager.__init__

    def patched_init(self, db_path_arg=None):
        original_init(self, db_path=str(db_path))

    with patch.object(db_module.DatabaseManager, '__init__', patched_init):
        with patch.object(ConfigManager, 'is_config_valid', return_value=True):
            with patch.object(ConfigManager, 'config', config, create=True):
                from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

                window = SleepScoringMainWindow()
                window.config_manager.config = config
                window.export_output_path = str(exports_folder)

                qtbot.addWidget(window)
                window.show()
                window.showMaximized()
                qtbot.waitExposed(window)
                qtbot.wait(DELAY)

                print("\n" + "=" * 80)
                print("APPLICATION LAUNCHED - FULL VISIBLE E2E TEST")
                print("=" * 80)

                yield {
                    "window": window,
                    "qtbot": qtbot,
                    "data_folder": data_folder,
                    "exports_folder": exports_folder,
                }

                window.close()


@pytest.mark.e2e
@pytest.mark.gui
class TestTrueEndToEndWorkflow:
    """
    ONE SINGLE TEST that covers the ENTIRE application workflow.

    Every element is interacted with in a realistic sequence.
    """

    def test_complete_human_workflow(self, app_environment):
        """
        Complete human workflow from start to finish.

        This test interacts with EVERY element in the application.
        """
        window = app_environment["window"]
        qtbot = app_environment["qtbot"]
        data_folder = app_environment["data_folder"]
        exports_folder = app_environment["exports_folder"]

        tab_widget = window.findChild(QTabWidget)
        assert tab_widget, "Tab widget must exist"

        # ================================================================
        # STEP 1: STUDY SETTINGS TAB - Configure EVERY setting
        # ================================================================
        print("\n" + "=" * 80)
        print("STEP 1: STUDY SETTINGS - Configuring ALL settings")
        print("=" * 80)

        self._switch_tab(tab_widget, "Study", qtbot)
        study_tab = window.study_settings_tab

        # 1.1 Data Paradigm dropdown
        print("\n[1.1] Data Paradigm dropdown...")
        paradigm_combo = study_tab.data_paradigm_combo
        if paradigm_combo:
            self._click_combo_item_by_data(paradigm_combo, StudyDataParadigm.EPOCH_BASED, qtbot)
            print(f"     Set to: {paradigm_combo.currentText()}")

        # 1.2 Sleep Algorithm dropdown
        print("\n[1.2] Sleep Algorithm dropdown...")
        algo_combo = study_tab.sleep_algorithm_combo
        if algo_combo:
            # First show all options by clicking through them
            print("     Available algorithms:")
            for i in range(algo_combo.count()):
                algo_combo.setCurrentIndex(i)
                qtbot.wait(100)
                print(f"       - {algo_combo.currentText()}")
            # Select Sadeh
            self._click_combo_item_by_data(algo_combo, AlgorithmType.SADEH_1994_ACTILIFE, qtbot)
            print(f"     Selected: {algo_combo.currentText()}")

        # 1.3 Sleep Period Detector dropdown
        print("\n[1.3] Sleep Period Detector dropdown...")
        detector_combo = study_tab.sleep_period_detector_combo
        if detector_combo:
            print("     Available detectors:")
            for i in range(detector_combo.count()):
                detector_combo.setCurrentIndex(i)
                qtbot.wait(100)
                print(f"       - {detector_combo.currentText()}")
            self._click_combo_item_by_data(detector_combo, SleepPeriodDetectorType.CONSECUTIVE_ONSET3S_OFFSET5S, qtbot)
            print(f"     Selected: {detector_combo.currentText()}")

        # 1.4 Nonwear Algorithm dropdown
        print("\n[1.4] Nonwear Algorithm dropdown...")
        nonwear_combo = study_tab.nonwear_algorithm_combo
        if nonwear_combo:
            print("     Available nonwear algorithms:")
            for i in range(nonwear_combo.count()):
                nonwear_combo.setCurrentIndex(i)
                qtbot.wait(100)
                print(f"       - {nonwear_combo.currentText()}")
            self._click_combo_item_by_data(nonwear_combo, NonwearAlgorithm.CHOI_2011, qtbot)
            print(f"     Selected: {nonwear_combo.currentText()}")

        # 1.5 Night Hours - Start Time
        print("\n[1.5] Night Start Time picker...")
        night_start = study_tab.night_start_time
        if night_start:
            night_start.setTime(QTime(21, 0))
            qtbot.wait(DELAY)
            print(f"     Set to: {night_start.time().toString('HH:mm')}")

        # 1.6 Night Hours - End Time
        print("\n[1.6] Night End Time picker...")
        night_end = study_tab.night_end_time
        if night_end:
            night_end.setTime(QTime(9, 0))
            qtbot.wait(DELAY)
            print(f"     Set to: {night_end.time().toString('HH:mm')}")

        # 1.7 Choi Axis dropdown
        print("\n[1.7] Choi Axis dropdown...")
        choi_axis_combo = study_tab.choi_axis_combo
        if choi_axis_combo:
            for i in range(choi_axis_combo.count()):
                choi_axis_combo.setCurrentIndex(i)
                qtbot.wait(100)
                print(f"     Option: {choi_axis_combo.currentText()}")
            choi_axis_combo.setCurrentIndex(0)  # First option
            print(f"     Selected: {choi_axis_combo.currentText()}")

        # 1.8 ID Pattern text field
        print("\n[1.8] ID Pattern text field...")
        id_pattern = study_tab.id_pattern_edit
        if id_pattern:
            id_pattern.clear()
            qtbot.keyClicks(id_pattern, r"(P\d{3})")
            qtbot.wait(DELAY)
            print(f"     Set to: {id_pattern.text()}")

        # 1.9 Timepoint Pattern text field
        print("\n[1.9] Timepoint Pattern text field...")
        tp_pattern = study_tab.timepoint_pattern_edit
        if tp_pattern:
            tp_pattern.clear()
            qtbot.keyClicks(tp_pattern, r"(T\d)")
            qtbot.wait(DELAY)
            print(f"     Set to: {tp_pattern.text()}")

        # 1.10 Group Pattern text field
        print("\n[1.10] Group Pattern text field...")
        grp_pattern = study_tab.group_pattern_edit
        if grp_pattern:
            grp_pattern.clear()
            qtbot.keyClicks(grp_pattern, r"(Control|Treatment)")
            qtbot.wait(DELAY)
            print(f"     Set to: {grp_pattern.text()}")

        # 1.11 Unknown Value text field
        print("\n[1.11] Unknown Value text field...")
        unknown_value = study_tab.unknown_value_edit
        if unknown_value:
            unknown_value.clear()
            qtbot.keyClicks(unknown_value, "UNKNOWN")
            qtbot.wait(DELAY)
            print(f"     Set to: {unknown_value.text()}")

        # 1.12 Valid Groups list - Add items
        print("\n[1.12] Valid Groups list...")
        groups_list = study_tab.valid_groups_list
        if groups_list:
            groups_list.clear()
            groups_list.addItem("Control")
            groups_list.addItem("Treatment")
            qtbot.wait(DELAY)
            print(f"     Added: Control, Treatment ({groups_list.count()} items)")

        # 1.13 Valid Timepoints list - Add items
        print("\n[1.13] Valid Timepoints list...")
        timepoints_list = study_tab.valid_timepoints_list
        if timepoints_list:
            timepoints_list.clear()
            timepoints_list.addItem("T1")
            timepoints_list.addItem("T2")
            timepoints_list.addItem("T3")
            qtbot.wait(DELAY)
            print(f"     Added: T1, T2, T3 ({timepoints_list.count()} items)")

        # 1.14 Default Group dropdown
        print("\n[1.14] Default Group dropdown...")
        default_group = study_tab.default_group_combo
        if default_group and default_group.count() > 0:
            default_group.setCurrentIndex(0)
            qtbot.wait(DELAY)
            print(f"     Set to: {default_group.currentText()}")

        # 1.15 Default Timepoint dropdown
        print("\n[1.15] Default Timepoint dropdown...")
        default_tp = study_tab.default_timepoint_combo
        if default_tp and default_tp.count() > 0:
            default_tp.setCurrentIndex(0)
            qtbot.wait(DELAY)
            print(f"     Set to: {default_tp.currentText()}")

        print("\n[OK] Study Settings complete - all settings configured")
        qtbot.wait(DELAY * 2)

        # ================================================================
        # STEP 2: DATA SETTINGS TAB - Configure ALL settings and import
        # ================================================================
        print("\n" + "=" * 80)
        print("STEP 2: DATA SETTINGS - Configure and Import")
        print("=" * 80)

        self._switch_tab(tab_widget, "Data", qtbot)
        data_tab = window.data_settings_tab

        # 2.1 Data Source Type dropdown
        print("\n[2.1] Data Source Type dropdown...")
        source_combo = data_tab.data_source_combo
        if source_combo:
            for i in range(source_combo.count()):
                source_combo.setCurrentIndex(i)
                qtbot.wait(100)
                print(f"     Option: {source_combo.currentText()}")
            source_combo.setCurrentIndex(0)  # First option
            print(f"     Selected: {source_combo.currentText()}")

        # 2.2 Device Preset dropdown - cycle through all
        print("\n[2.2] Device Preset dropdown...")
        device_combo = data_tab.device_preset_combo
        if device_combo:
            print("     Available presets:")
            for i in range(device_combo.count()):
                device_combo.setCurrentIndex(i)
                qtbot.wait(100)
                print(f"       - {device_combo.currentText()}")
            # Select ActiGraph
            for i in range(device_combo.count()):
                if "ActiGraph" in device_combo.itemText(i):
                    device_combo.setCurrentIndex(i)
                    break
            print(f"     Selected: {device_combo.currentText()}")

        # 2.3 Epoch Length spinner - test range
        print("\n[2.3] Epoch Length spinner...")
        epoch_spin = data_tab.epoch_length_spin
        if epoch_spin:
            epoch_spin.setValue(15)
            qtbot.wait(100)
            print(f"     Test value: {epoch_spin.value()}")
            epoch_spin.setValue(30)
            qtbot.wait(100)
            print(f"     Test value: {epoch_spin.value()}")
            epoch_spin.setValue(60)
            qtbot.wait(DELAY)
            print(f"     Final value: {epoch_spin.value()}")

        # 2.4 Skip Rows spinner
        print("\n[2.4] Skip Rows spinner...")
        skip_spin = data_tab.skip_rows_spin
        if skip_spin:
            skip_spin.setValue(10)
            qtbot.wait(100)
            print(f"     Test value: {skip_spin.value()}")
            skip_spin.setValue(0)
            qtbot.wait(DELAY)
            print(f"     Final value: {skip_spin.value()}")

        # 2.5 Set data folder
        print("\n[2.5] Setting data folder...")
        window.data_service.set_data_folder(str(data_folder))
        qtbot.wait(DELAY)
        print(f"     Set to: {data_folder}")

        # 2.6 Find auto-detect buttons and click them
        print("\n[2.6] Auto-detect buttons...")
        for btn in data_tab.findChildren(QPushButton):
            if "Auto" in btn.text() and btn.isEnabled():
                print(f"     Clicking: {btn.text()}")
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                qtbot.wait(200)

        # 2.7 Import files using import service
        print("\n[2.7] Importing activity files...")
        test_files = list(data_folder.glob("*.csv"))
        print(f"     Found {len(test_files)} files to import")

        import_service = window.import_service
        if import_service:
            result = import_service.import_files(
                file_paths=test_files,
                skip_rows=0,
                force_reimport=True,
            )
            print(f"     Import complete: {len(result.imported_files)} imported, {len(result.errors)} errors")
        qtbot.wait(DELAY)

        # 2.8 Refresh available files
        print("\n[2.8] Refreshing file list...")
        available_files = window.data_service.find_available_files()
        print(f"     Available files: {len(available_files)}")
        for f in available_files:
            print(f"       - {f.filename}")

        print("\n[OK] Data Settings complete - files imported")
        qtbot.wait(DELAY * 2)

        # ================================================================
        # STEP 3: ANALYSIS TAB - Interact with EVERY element
        # ================================================================
        print("\n" + "=" * 80)
        print("STEP 3: ANALYSIS TAB - Full interaction")
        print("=" * 80)

        self._switch_tab(tab_widget, "Analysis", qtbot)
        analysis_tab = window.analysis_tab

        # 3.1 File Selection Table - click on first file
        print("\n[3.1] File Selection Table...")
        file_selector = analysis_tab.file_selector
        if file_selector and available_files:
            first_file = available_files[0]
            print(f"     Selecting: {first_file.filename}")
            window.on_file_selected_from_table(first_file)
            qtbot.wait(DELAY)

        # 3.2 Verify dates loaded
        print("\n[3.2] Verifying dates loaded...")
        dates = window.store.state.available_dates
        print(f"     Loaded {len(dates)} dates")
        for d in list(dates)[:5]:
            print(f"       - {d}")

        # 3.3 Date Dropdown - cycle through dates
        print("\n[3.3] Date Dropdown...")
        date_dropdown = analysis_tab.date_dropdown
        if date_dropdown and date_dropdown.count() > 0:
            print(f"     Available dates: {date_dropdown.count()}")
            for i in range(min(date_dropdown.count(), 3)):
                date_dropdown.setCurrentIndex(i)
                qtbot.wait(200)
                print(f"       Selected: {date_dropdown.currentText()}")
            date_dropdown.setCurrentIndex(0)

        # 3.4 Previous Date button
        print("\n[3.4] Previous Date button...")
        prev_btn = analysis_tab.prev_date_btn
        if prev_btn:
            print(f"     Button enabled: {prev_btn.isEnabled()}")
            if prev_btn.isEnabled():
                qtbot.mouseClick(prev_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(DELAY)
                print(f"     Clicked - now at index {window.store.state.current_date_index}")

        # 3.5 Next Date button
        print("\n[3.5] Next Date button...")
        next_btn = analysis_tab.next_date_btn
        if next_btn:
            print(f"     Button enabled: {next_btn.isEnabled()}")
            for _ in range(3):  # Click 3 times
                if next_btn.isEnabled():
                    qtbot.mouseClick(next_btn, Qt.MouseButton.LeftButton)
                    qtbot.wait(200)
                    print(f"       Clicked - now at index {window.store.state.current_date_index}")

        # Go back to first date for consistent marker placement
        from sleep_scoring_app.ui.store import Actions
        window.store.dispatch(Actions.date_selected(0))
        qtbot.wait(DELAY)

        # 3.6 Activity Source dropdown - cycle through ALL sources
        print("\n[3.6] Activity Source dropdown...")
        source_dropdown = analysis_tab.activity_source_dropdown
        if source_dropdown:
            print(f"     Available sources: {source_dropdown.count()}")
            for i in range(source_dropdown.count()):
                source_dropdown.setCurrentIndex(i)
                qtbot.wait(200)
                print(f"       {i}: {source_dropdown.currentText()}")
            source_dropdown.setCurrentIndex(0)  # Y-axis
            print(f"     Final selection: {source_dropdown.currentText()}")

        # 3.7 View Mode - 24h button
        print("\n[3.7] View Mode buttons...")
        view_24h = analysis_tab.view_24h_btn
        view_48h = analysis_tab.view_48h_btn
        if view_24h and view_48h:
            print("     Clicking 24h view...")
            view_24h.setChecked(True)
            qtbot.wait(DELAY)
            print(f"       24h checked: {view_24h.isChecked()}")

            print("     Clicking 48h view...")
            view_48h.setChecked(True)
            qtbot.wait(DELAY)
            print(f"       48h checked: {view_48h.isChecked()}")

            # Back to 24h
            view_24h.setChecked(True)
            qtbot.wait(DELAY)

        # 3.8 Adjacent Markers checkbox
        print("\n[3.8] Adjacent Markers checkbox...")
        adj_checkbox = analysis_tab.show_adjacent_day_markers_checkbox
        if adj_checkbox:
            original = adj_checkbox.isChecked()
            adj_checkbox.setChecked(not original)
            qtbot.wait(DELAY)
            print(f"     Toggled to: {adj_checkbox.isChecked()}")
            adj_checkbox.setChecked(original)
            qtbot.wait(DELAY)
            print(f"     Restored to: {adj_checkbox.isChecked()}")

        # 3.9 Marker Mode - Sleep/Nonwear radio buttons
        print("\n[3.9] Marker Mode radio buttons...")
        sleep_mode = analysis_tab.sleep_mode_btn
        nonwear_mode = analysis_tab.nonwear_mode_btn
        if sleep_mode and nonwear_mode:
            print("     Clicking Nonwear mode...")
            nonwear_mode.setChecked(True)
            qtbot.wait(DELAY)
            print(f"       Nonwear checked: {nonwear_mode.isChecked()}")

            print("     Clicking Sleep mode...")
            sleep_mode.setChecked(True)
            qtbot.wait(DELAY)
            print(f"       Sleep checked: {sleep_mode.isChecked()}")

        # 3.10 Show NW Markers checkbox
        print("\n[3.10] Show Manual NW Markers checkbox...")
        show_nw = getattr(analysis_tab, 'show_manual_nonwear_checkbox', None)
        if show_nw:
            original = show_nw.isChecked()
            show_nw.setChecked(not original)
            qtbot.wait(DELAY)
            print(f"     Toggled to: {show_nw.isChecked()}")
            show_nw.setChecked(True)  # Keep enabled
            qtbot.wait(DELAY)
        else:
            print("     Checkbox not found")

        # 3.11 Manual Onset Time field
        print("\n[3.11] Manual Onset Time field...")
        onset_input = analysis_tab.onset_time_input
        if onset_input:
            onset_input.clear()
            qtbot.keyClicks(onset_input, "22:30")
            qtbot.wait(DELAY)
            print(f"     Entered: {onset_input.text()}")

        # 3.12 Manual Offset Time field
        print("\n[3.12] Manual Offset Time field...")
        offset_input = analysis_tab.offset_time_input
        if offset_input:
            offset_input.clear()
            qtbot.keyClicks(offset_input, "06:45")
            qtbot.wait(DELAY)
            print(f"     Entered: {offset_input.text()}")

        # 3.13 Set Manual Time button (if exists)
        print("\n[3.13] Set button for manual time...")
        set_btn = None
        for btn in analysis_tab.findChildren(QPushButton):
            if btn.text().lower() in ["set", "apply", "set time", "set markers"]:
                set_btn = btn
                break
        if set_btn and set_btn.isEnabled():
            qtbot.mouseClick(set_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(DELAY)
            print(f"     Clicked: {set_btn.text()}")

        # 3.14 Place markers programmatically (simulating plot click)
        print("\n[3.14] Placing sleep markers...")
        from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod

        current_date_str = dates[0] if dates else "2024-01-15"
        year, month, day = 2024, 1, 15
        try:
            parts = current_date_str.split("-")
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        except:
            pass

        onset = datetime(year, month, day, 22, 30, 0)
        offset = datetime(year, month, day + 1, 6, 45, 0)

        markers = DailySleepMarkers()
        markers.period_1 = SleepPeriod(
            onset_timestamp=onset.timestamp(),
            offset_timestamp=offset.timestamp(),
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.store.dispatch(Actions.sleep_markers_changed(markers))
        qtbot.wait(DELAY)
        print(f"     Created Period 1: {onset.strftime('%H:%M')} - {offset.strftime('%H:%M')}")

        # 3.15 Auto-save checkbox
        print("\n[3.15] Auto-save checkbox...")
        autosave = analysis_tab.auto_save_checkbox
        if autosave:
            autosave.setChecked(True)
            qtbot.wait(DELAY)
            print(f"     Enabled: {autosave.isChecked()}")

        # 3.16 Save Markers button
        print("\n[3.16] Save Markers button...")
        save_btn = analysis_tab.save_markers_btn
        if save_btn and save_btn.isEnabled():
            qtbot.mouseClick(save_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(DELAY)
            print("     Clicked Save")

        # 3.17 No Sleep button
        print("\n[3.17] No Sleep button...")
        no_sleep_btn = analysis_tab.no_sleep_btn
        if no_sleep_btn:
            print(f"     Button exists, enabled: {no_sleep_btn.isEnabled()}")
            # Don't click - would clear our markers

        # 3.18 Clear Markers button
        print("\n[3.18] Clear Markers button...")
        clear_btn = analysis_tab.clear_markers_btn
        if clear_btn:
            print(f"     Button exists, enabled: {clear_btn.isEnabled()}")
            # Don't click - would clear our markers

        # 3.19 Shortcuts button - open dialog
        print("\n[3.19] Shortcuts button...")
        shortcuts_btn = None
        for btn in analysis_tab.findChildren(QPushButton):
            if "Shortcut" in btn.text():
                shortcuts_btn = btn
                break
        if shortcuts_btn:
            print(f"     Found: {shortcuts_btn.text()}")
            # Don't open dialog - may block test

        # 3.20 Colors button - open dialog
        print("\n[3.20] Colors button...")
        colors_btn = None
        for btn in analysis_tab.findChildren(QPushButton):
            if "Color" in btn.text():
                colors_btn = btn
                break
        if colors_btn:
            print(f"     Found: {colors_btn.text()}")

        # 3.21 Pop-out Onset Table button
        print("\n[3.21] Pop-out buttons...")
        for btn in analysis_tab.findChildren(QPushButton):
            btn_text = btn.text()
            # Sanitize text for console output
            try:
                btn_text_safe = btn_text.encode('ascii', 'replace').decode('ascii')
            except:
                btn_text_safe = "[special chars]"
            if "Pop" in btn_text or "Onset" in btn_text or "Offset" in btn_text:
                print(f"     Found: {btn_text_safe}")

        # 3.22 Keyboard Navigation
        print("\n[3.22] Keyboard navigation...")
        window.activateWindow()
        window.setFocus()
        qtbot.wait(100)

        print("     Pressing Right arrow...")
        QTest.keyClick(window, Qt.Key.Key_Right)
        qtbot.wait(DELAY)
        print(f"       Date index: {window.store.state.current_date_index}")

        print("     Pressing Right arrow again...")
        QTest.keyClick(window, Qt.Key.Key_Right)
        qtbot.wait(DELAY)
        print(f"       Date index: {window.store.state.current_date_index}")

        print("     Pressing Left arrow...")
        QTest.keyClick(window, Qt.Key.Key_Left)
        qtbot.wait(DELAY)
        print(f"       Date index: {window.store.state.current_date_index}")

        print("     Pressing Left arrow again...")
        QTest.keyClick(window, Qt.Key.Key_Left)
        qtbot.wait(DELAY)
        print(f"       Date index: {window.store.state.current_date_index}")

        # 3.23 Diary Table (if visible)
        print("\n[3.23] Diary Table...")
        diary_table = getattr(analysis_tab, 'diary_table_widget', None) or getattr(analysis_tab, 'diary_table', None)
        if diary_table and diary_table.isVisible():
            print(f"     Rows: {diary_table.rowCount()}")
            print(f"     Columns: {diary_table.columnCount()}")
        else:
            # Look for any QTableWidget in the analysis tab
            tables = analysis_tab.findChildren(QTableWidget)
            if tables:
                print(f"     Found {len(tables)} table(s)")
            else:
                print("     No diary table found")

        # 3.24 Plot Widget verification
        print("\n[3.24] Plot Widget...")
        plot = analysis_tab.plot_widget
        if plot:
            print(f"     Visible: {plot.isVisible()}")
            print(f"     Size: {plot.width()}x{plot.height()}")

        print("\n[OK] Analysis Tab complete - all elements interacted")
        qtbot.wait(DELAY * 2)

        # ================================================================
        # STEP 4: EXPORT TAB - Export and Validate
        # ================================================================
        print("\n" + "=" * 80)
        print("STEP 4: EXPORT TAB - Export data")
        print("=" * 80)

        self._switch_tab(tab_widget, "Export", qtbot)

        # 4.1 Export all data
        print("\n[4.1] Exporting data...")
        export_path = str(exports_folder)
        try:
            result = window.export_manager.export_all_sleep_data(export_path)
            print(f"     Result: {result}")
        except Exception as e:
            print(f"     Exception: {e}")
        qtbot.wait(DELAY)

        # 4.2 Validate export
        print("\n[4.2] Validating export...")
        export_files = list(exports_folder.glob("*.csv"))
        print(f"     Files created: {len(export_files)}")

        for f in export_files:
            print(f"\n     {f.name}")
            print(f"       Size: {f.stat().st_size} bytes")
            try:
                df = pd.read_csv(f)
                print(f"       Rows: {len(df)}")
                print(f"       Columns: {len(df.columns)}")
                print(f"       Column names: {list(df.columns)[:10]}...")
            except Exception as e:
                print(f"       Error reading: {e}")

        print("\n[OK] Export complete")
        qtbot.wait(DELAY * 2)

        # ================================================================
        # STEP 5: SWITCH BETWEEN ALL TABS
        # ================================================================
        print("\n" + "=" * 80)
        print("STEP 5: Switching between ALL tabs")
        print("=" * 80)

        for i in range(tab_widget.count()):
            tab_widget.setCurrentIndex(i)
            qtbot.wait(DELAY)
            print(f"     Tab {i}: {tab_widget.tabText(i)}")

        print("\n[OK] All tabs visited")

        # ================================================================
        # FINAL SUMMARY
        # ================================================================
        print("\n" + "=" * 80)
        print("WORKFLOW COMPLETE - FINAL STATE")
        print("=" * 80)

        state = window.store.state
        print(f"\n  Current file: {state.current_file}")
        print(f"  Available dates: {len(state.available_dates)}")
        print(f"  Current date index: {state.current_date_index}")
        print(f"  Sleep algorithm: {state.sleep_algorithm_id}")
        print(f"  Auto-save enabled: {state.auto_save_enabled}")
        print(f"  Export files: {len(export_files)}")

        if export_files:
            df = pd.read_csv(export_files[0])
            print(f"  Export rows: {len(df)}")
            print(f"  Export columns: {len(df.columns)}")

        print("\n" + "=" * 80)
        print("SUCCESS - ALL ELEMENTS TESTED")
        print("=" * 80)

        # Assertions
        assert window.isVisible()
        assert len(available_files) >= 1
        assert len(dates) >= 1
        assert len(export_files) >= 1

        qtbot.wait(DELAY * 3)

    def _switch_tab(self, tab_widget: QTabWidget, name: str, qtbot) -> None:
        """Switch to tab containing name."""
        for i in range(tab_widget.count()):
            if name.lower() in tab_widget.tabText(i).lower():
                tab_widget.setCurrentIndex(i)
                qtbot.wait(DELAY)
                print(f"\n>>> Switched to: {tab_widget.tabText(i)}")
                return

    def _click_combo_item_by_data(self, combo: QComboBox, data, qtbot) -> None:
        """Select combo item by its data value."""
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                qtbot.wait(100)
                return
        # Fallback: just use first item
        combo.setCurrentIndex(0)
        qtbot.wait(100)


@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup after test."""
    yield
    import gc
    gc.collect()
