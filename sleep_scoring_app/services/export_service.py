"""
Export system for sleep scoring application
Handles data export, backup creation, and file operations.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from sleep_scoring_app.core.constants import (
    ActivityDataPreference,
    AlgorithmType,
    DirectoryName,
    FeatureFlags,
    get_backup_filename,
    sanitize_filename_component,
)
from sleep_scoring_app.core.exceptions import DatabaseError, ErrorCodes, ValidationError
from sleep_scoring_app.data.database import DatabaseManager

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import SleepMetrics

# Configure logging
logger = logging.getLogger(__name__)


class ExportManager:
    """Handles all export operations."""

    def __init__(self, database_manager: DatabaseManager = None) -> None:
        self.db_manager = database_manager or DatabaseManager()
        self.max_backups = 10

    def _atomic_csv_write(self, df: pd.DataFrame, csv_path: Path, **kwargs) -> None:
        """Write CSV atomically to prevent corruption."""
        temp_path = csv_path.with_suffix(f".tmp.{os.getpid()}")

        try:
            df.to_csv(temp_path, float_format="%.4f", **kwargs)

            if temp_path.stat().st_size == 0:
                msg = "CSV write produced empty file"
                raise OSError(msg)

            temp_path.replace(csv_path)

        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _sanitize_csv_cell(self, value):
        """Prevent CSV formula injection."""
        if not isinstance(value, str):
            return value

        if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + value

        return value

    def autosave_sleep_metrics(
        self,
        sleep_metrics_list: list[SleepMetrics],
        algorithm_name: AlgorithmType = AlgorithmType.SADEH_1994_ACTILIFE,
    ) -> str | None:
        """Autosave sleep metrics on marker change (temporary storage only, no permanent CSV)."""
        if not FeatureFlags.ENABLE_AUTOSAVE:
            return None

        if not sleep_metrics_list:
            return None

        try:
            # Save each metric to the autosave table
            for sleep_metrics in sleep_metrics_list:
                sleep_metrics.algorithm_type = algorithm_name
                self.db_manager.save_sleep_metrics(sleep_metrics, is_autosave=True)

            logger.debug("Auto-saved markers on change for %s", sleep_metrics_list[0].filename)
            return "autosaved"

        except (DatabaseError, ValidationError, OSError) as e:
            logger.warning("Error autosaving metrics: %s", e)
            return None

    def export_all_sleep_data(self, output_directory: str | None = None) -> str | None:
        """Export all sleep data to CSV with backup creation."""
        try:
            # Get all data from database
            export_data = self.db_manager.get_all_sleep_data_for_export()

            if not export_data:
                return "No data available for export"

            # Convert to DataFrame
            df = pd.DataFrame(export_data)

            # Sanitize string columns
            for col in df.select_dtypes(include=["object"]).columns:
                df[col] = df[col].apply(self._sanitize_csv_cell)

            # Set output directory
            if not output_directory:
                output_directory = str(Path.cwd() / DirectoryName.SLEEP_DATA_EXPORTS)

            # Ensure output directory exists
            os.makedirs(output_directory, mode=0o755, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"sleep_scoring_export_{timestamp}.csv"
            csv_path = Path(output_directory) / csv_filename

            # Create backup of existing file BEFORE export
            if csv_path.exists():
                self._create_backup(csv_path)

            # Export to CSV atomically
            self._atomic_csv_write(df, csv_path, index=False)

            return f"Exported {len(df)} records to {csv_path}"

        except (DatabaseError, OSError, PermissionError, ValueError) as e:
            logger.warning("Error exporting data: %s", e)
            return None

    def create_export_csv_only(
        self,
        sleep_metrics_list: list[SleepMetrics],
        algorithm_name: AlgorithmType = AlgorithmType.SADEH_1994_ACTILIFE,
    ) -> str | None:
        """Create CSV file for export dialog WITHOUT saving to database (to avoid duplicates)."""
        if not sleep_metrics_list:
            return None

        # Sanitize algorithm name to prevent security issues
        safe_algorithm_name = sanitize_filename_component(algorithm_name)
        if not safe_algorithm_name:
            safe_algorithm_name = sanitize_filename_component(AlgorithmType.SADEH_1994_ACTILIFE)

        try:
            # CRITICAL: Ensure all metrics (including naps) are calculated before export
            self._ensure_metrics_calculated_for_export(sleep_metrics_list)

            # Create export file path
            export_dir = Path.cwd() / "sleep_data_exports"
            export_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filepath = export_dir / f"export_temp_{safe_algorithm_name}_{timestamp}.csv"

            # Create new data DataFrame from SleepMetrics objects - multiple periods per participant
            new_data = []
            for metrics in sleep_metrics_list:
                # Get all sleep periods for this participant/date
                period_rows = metrics.to_export_dict_list()
                new_data.extend(period_rows)

            export_df = pd.DataFrame(new_data)

            # Sanitize string columns to prevent formula injection
            for col in export_df.select_dtypes(include=["object"]).columns:
                export_df[col] = export_df[col].apply(self._sanitize_csv_cell)

            # Sort by Participant ID, Sleep Date, and Marker Index for consistent ordering
            sort_columns = []
            if "Numerical Participant ID" in export_df.columns:
                sort_columns.append("Numerical Participant ID")
            if "Sleep Date" in export_df.columns:
                sort_columns.append("Sleep Date")
            if "Marker Index" in export_df.columns:
                sort_columns.append("Marker Index")

            if sort_columns:
                export_df = export_df.sort_values(by=sort_columns, ascending=True)

            # Count total sleep periods exported
            total_periods = len(new_data)
            total_participants = len(sleep_metrics_list)

            # Write CSV file with header comments atomically
            temp_path = export_filepath.with_suffix(f".tmp.{os.getpid()}")
            try:
                with open(temp_path, "w", newline="", encoding="utf-8") as f:
                    f.write("#\n")
                    f.write("# Sleep Scoring Export Data (Multiple Periods)\n")
                    f.write("# Algorithm: ")
                    f.write(safe_algorithm_name)
                    f.write("\n")
                    f.write("# Generated: ")
                    f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    f.write("\n")
                    f.write("# Participants: ")
                    f.write(str(total_participants))
                    f.write("\n")
                    f.write("# Sleep Periods: ")
                    f.write(str(total_periods))
                    f.write("\n")
                    f.write("# Note: Each row represents one sleep period (main sleep or nap)\n")
                    f.write("#\n")

                    export_df.to_csv(f, index=False, float_format="%.4f")

                    f.flush()
                    os.fsync(f.fileno())

                if temp_path.stat().st_size == 0:
                    msg = "CSV write produced empty file"
                    raise OSError(msg)

                temp_path.replace(export_filepath)

            except Exception:
                if temp_path.exists():
                    temp_path.unlink()
                raise

            logger.debug("Export CSV created: %s (%s participants, %s periods, NO database save)", export_filepath, total_participants, total_periods)
            return str(export_filepath)

        except (OSError, PermissionError, ValueError, pd.errors.ParserError) as e:
            logger.warning("Error creating export CSV: %s", e)
            return None

    def perform_direct_export(
        self,
        sleep_metrics_list: list[SleepMetrics],
        grouping_option: int,
        output_directory: str,
        selected_columns: list[str],
        include_headers: bool = True,
        include_metadata: bool = True,
        include_config_in_metadata: bool = False,
        export_config_sidecar: bool = False,
        config_manager: any | None = None,
        export_nonwear_separate: bool = True,
    ) -> bool:
        """Perform direct export from UI tab without modal dialog."""
        if not sleep_metrics_list:
            return False

        try:
            # Create output directory if it doesn't exist
            output_path = Path(output_directory)
            output_path.mkdir(parents=True, exist_ok=True)

            # CRITICAL FIX: Ensure metrics are calculated before export
            self._ensure_metrics_calculated_for_export(sleep_metrics_list)

            # Filter data based on grouping option
            grouped_data = self._group_export_data(sleep_metrics_list, grouping_option)

            # Export each group
            for group_name, metrics in grouped_data.items():
                # Create filename based on group
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"sleep_data_{group_name}_{timestamp}.csv"
                filepath = output_path / filename

                # Convert to export format - multiple periods per participant
                export_data = []
                for metric in metrics:
                    period_rows = metric.to_export_dict_list()
                    export_data.extend(period_rows)

                export_df = pd.DataFrame(export_data)

                # Sanitize string columns
                for col in export_df.select_dtypes(include=["object"]).columns:
                    export_df[col] = export_df[col].apply(self._sanitize_csv_cell)

                # Sort by Participant ID, Sleep Date, and Marker Index for consistent ordering
                sort_columns = []
                if "Numerical Participant ID" in export_df.columns:
                    sort_columns.append("Numerical Participant ID")
                if "Sleep Date" in export_df.columns:
                    sort_columns.append("Sleep Date")
                if "Marker Index" in export_df.columns:
                    sort_columns.append("Marker Index")

                if sort_columns:
                    export_df = export_df.sort_values(by=sort_columns, ascending=True)

                # Filter columns if specified
                if selected_columns:
                    available_columns = [col for col in selected_columns if col in export_df.columns]
                    if available_columns:
                        export_df = export_df[available_columns]

                # Count totals for metadata
                total_periods = len(export_data)
                total_participants = len(metrics)

                # Write to CSV atomically
                temp_path = filepath.with_suffix(f".tmp.{os.getpid()}")
                try:
                    with open(temp_path, "w", newline="", encoding="utf-8") as f:
                        if include_metadata:
                            f.write("#\n")
                            f.write("# Sleep Scoring Export Data (Multiple Periods)\n")
                            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"# Group: {group_name}\n")
                            f.write(f"# Participants: {total_participants}\n")
                            f.write(f"# Sleep Periods: {total_periods}\n")
                            f.write("# Note: Each row represents one sleep period (main sleep or nap)\n")
                            f.write("#\n")

                            # Include configuration in metadata if requested
                            if include_config_in_metadata and config_manager is not None:
                                config_lines = config_manager.get_config_metadata_header()
                                f.writelines(line + "\n" for line in config_lines)
                                f.write("#\n")

                        export_df.to_csv(f, index=False, header=include_headers, float_format="%.4f")

                        f.flush()
                        os.fsync(f.fileno())

                    if temp_path.stat().st_size == 0:
                        msg = "CSV write produced empty file"
                        raise OSError(msg)

                    temp_path.replace(filepath)

                except Exception:
                    if temp_path.exists():
                        temp_path.unlink()
                    raise

                logger.debug("Exported %s participants (%s periods) to %s", total_participants, total_periods, filepath)

                # Export config sidecar file if requested
                if export_config_sidecar and config_manager is not None:
                    config_sidecar_path = filepath.with_suffix(".config.csv")
                    config_manager.export_config_csv(config_sidecar_path)
                    logger.debug("Exported config sidecar to %s", config_sidecar_path)

            # Export nonwear markers to separate file if requested
            if export_nonwear_separate:
                self._export_nonwear_markers_separate(
                    sleep_metrics_list,
                    output_path,
                    include_headers,
                    include_metadata,
                )

            return True

        except (OSError, PermissionError, ValueError, DatabaseError) as e:
            logger.warning("Error in direct export: %s", e)
            return False

    def _ensure_metrics_calculated_for_export(self, sleep_metrics_list: list[SleepMetrics]) -> None:
        """Ensure all sleep metrics have calculated values before export."""
        from datetime import datetime, timedelta

        import pandas as pd

        from sleep_scoring_app.core.algorithms import AlgorithmFactory, NonwearAlgorithmFactory
        from sleep_scoring_app.core.constants import NonwearDataSource
        from sleep_scoring_app.services.data_service import DataManager
        from sleep_scoring_app.services.nonwear_service import NonwearDataService

        # Get service instances
        data_manager = DataManager(database_manager=self.db_manager)
        nonwear_service = NonwearDataService(database_manager=self.db_manager)

        # CRITICAL FIX #4: Cache for activity data to avoid redundant database calls
        # Key is filename, value is (timestamps, axis_y, vector_mag)
        # This prevents loading the same file's data multiple times for different periods
        activity_data_cache: dict[str, tuple[list, list, list]] = {}

        for metrics in sleep_metrics_list:
            # Get all complete sleep periods
            complete_periods = metrics.daily_sleep_markers.get_complete_periods()
            if not complete_periods:
                continue

            try:
                filename = metrics.filename

                # Load activity data ONCE per file (cache hit or miss)
                if filename not in activity_data_cache:
                    # Find the full time range needed for all periods in this file
                    all_starts = [datetime.fromtimestamp(p.onset_timestamp) for p in complete_periods]
                    all_ends = [datetime.fromtimestamp(p.offset_timestamp) for p in complete_periods]
                    earliest_start = min(all_starts) - timedelta(minutes=5)  # 5 min buffer for Sadeh
                    latest_end = max(all_ends) + timedelta(minutes=5)

                    # Load AXIS_Y data for Sadeh
                    timestamps, axis_y_values = self.db_manager.load_raw_activity_data(
                        filename=filename, start_time=earliest_start, end_time=latest_end, activity_column=ActivityDataPreference.AXIS_Y
                    )

                    if not timestamps or not axis_y_values:
                        logger.debug("No activity data found for %s", filename)
                        activity_data_cache[filename] = ([], [], [])
                        continue

                    # Also load vector magnitude for Choi algorithm
                    _, vector_magnitude = self.db_manager.load_raw_activity_data(
                        filename=filename, start_time=earliest_start, end_time=latest_end, activity_column=ActivityDataPreference.VECTOR_MAGNITUDE
                    )

                    activity_data_cache[filename] = (timestamps, axis_y_values, vector_magnitude or [])
                    logger.debug("Cached activity data for %s (%d epochs)", filename, len(timestamps))

                # Get cached data
                cached_timestamps, cached_axis_y, cached_vector_mag = activity_data_cache[filename]
                if not cached_timestamps:
                    continue

                # Calculate metrics for ALL periods using cached data
                for period in complete_periods:
                    # Extract the subset of data for this period
                    period_start = datetime.fromtimestamp(period.onset_timestamp) - timedelta(minutes=5)
                    period_end = datetime.fromtimestamp(period.offset_timestamp) + timedelta(minutes=5)

                    # Filter cached data to the period's time range
                    indices = []
                    for i, ts in enumerate(cached_timestamps):
                        ts_dt = ts if isinstance(ts, datetime) else datetime.fromtimestamp(ts)
                        if period_start <= ts_dt <= period_end:
                            indices.append(i)

                    if not indices:
                        continue

                    timestamps = [cached_timestamps[i] for i in indices]
                    axis_y_values = [cached_axis_y[i] for i in indices]
                    vector_magnitude = [cached_vector_mag[i] for i in indices] if cached_vector_mag else []

                    # Convert datetime timestamps to Unix timestamps for compatibility
                    unix_timestamps = [ts.timestamp() if isinstance(ts, datetime) else ts for ts in timestamps]

                    # Get the algorithm from metrics or use default
                    algorithm_id = metrics.sleep_algorithm_name or AlgorithmFactory.get_default_algorithm_id()
                    sleep_algorithm = AlgorithmFactory.create(algorithm_id)

                    # Run sleep scoring algorithm using DI pattern
                    sadeh_results = sleep_algorithm.score_array(axis_y_values)

                    # Run REAL Choi algorithm for nonwear detection
                    choi_results = []
                    if vector_magnitude:
                        # Create DataFrame for Choi algorithm
                        df = pd.DataFrame(
                            {
                                "datetime": timestamps,
                                ActivityDataPreference.AXIS_Y: axis_y_values,
                                ActivityDataPreference.VECTOR_MAGNITUDE: vector_magnitude,
                            }
                        )

                        # Run Choi nonwear detection using DI pattern
                        choi_algorithm = NonwearAlgorithmFactory.create("choi_2011")
                        choi_results = choi_algorithm.detect_mask(vector_magnitude)
                    else:
                        choi_results = [0] * len(sadeh_results)

                    # Get NWT sensor data from database
                    nwt_sensor_results = []
                    try:
                        # Get nonwear periods from sensor - convert timestamps to datetime
                        from datetime import datetime as dt

                        onset_dt = (
                            dt.fromtimestamp(period.onset_timestamp) if isinstance(period.onset_timestamp, int | float) else period.onset_timestamp
                        )
                        offset_dt = (
                            dt.fromtimestamp(period.offset_timestamp) if isinstance(period.offset_timestamp, int | float) else period.offset_timestamp
                        )

                        sensor_periods = nonwear_service.get_nonwear_periods_for_file(
                            filename=filename, source=NonwearDataSource.NONWEAR_SENSOR, start_time=onset_dt, end_time=offset_dt
                        )

                        # Convert to per-minute results
                        nwt_sensor_results = [0] * len(timestamps)
                        for nw_period in sensor_periods:
                            for i, ts in enumerate(timestamps):
                                # Convert timestamp to datetime if needed
                                ts_dt = datetime.fromtimestamp(ts) if isinstance(ts, int | float) else ts
                                # Access attributes of NonwearPeriod object
                                if nw_period.start_time <= ts_dt <= nw_period.end_time:
                                    nwt_sensor_results[i] = 1
                    except Exception as e:
                        logger.debug("Could not get NWT sensor data: %s", e)
                        nwt_sensor_results = [0] * len(timestamps)

                    # Calculate metrics for this period with REAL algorithm results
                    period_metrics = data_manager.calculate_sleep_metrics(
                        sleep_markers=[period.onset_timestamp, period.offset_timestamp],
                        sadeh_results=sadeh_results,
                        choi_results=choi_results,  # REAL Choi results
                        activity_data=axis_y_values,
                        x_data=unix_timestamps,
                        file_path=filename,
                        nwt_sensor_results=nwt_sensor_results,  # REAL NWT sensor data
                    )

                    if period_metrics:
                        if not isinstance(period_metrics, dict):
                            logger.warning(f"period_metrics is {type(period_metrics)} instead of dict: {period_metrics}")
                            continue

                        # Store calculated metrics for this specific period
                        period_metrics_for_storage = {
                            "total_sleep_time": period_metrics.get("Total Sleep Time (TST)"),
                            "sleep_efficiency": period_metrics.get("Efficiency"),
                            "total_minutes_in_bed": period_metrics.get("Total Minutes in Bed"),
                            "waso": period_metrics.get("Wake After Sleep Onset (WASO)"),
                            "awakenings": period_metrics.get("Number of Awakenings"),
                            "average_awakening_length": period_metrics.get("Average Awakening Length"),
                            "total_activity": period_metrics.get("Total Counts"),
                            "movement_index": period_metrics.get("Movement Index"),
                            "fragmentation_index": period_metrics.get("Fragmentation Index"),
                            "sleep_fragmentation_index": period_metrics.get("Sleep Fragmentation Index"),
                            "sadeh_onset": period_metrics.get("Sadeh Algorithm Value at Sleep Onset"),
                            "sadeh_offset": period_metrics.get("Sadeh Algorithm Value at Sleep Offset"),
                            "overlapping_nonwear_minutes_algorithm": period_metrics.get("Overlapping Nonwear Minutes (Algorithm)"),
                            "overlapping_nonwear_minutes_sensor": period_metrics.get("Overlapping Nonwear Minutes (Sensor)"),
                        }

                        # Store metrics for this period (works for both main sleep and naps)
                        metrics.store_period_metrics(period, period_metrics_for_storage)

                        # If this is the main sleep period, also update the top-level metrics fields
                        main_sleep_period = metrics.daily_sleep_markers.get_main_sleep()
                        if period == main_sleep_period:
                            metrics.total_sleep_time = period_metrics.get("Total Sleep Time (TST)")
                            metrics.sleep_efficiency = period_metrics.get("Efficiency")
                            metrics.total_minutes_in_bed = period_metrics.get("Total Minutes in Bed")
                            metrics.waso = period_metrics.get("Wake After Sleep Onset (WASO)")
                            metrics.awakenings = period_metrics.get("Number of Awakenings")
                            metrics.average_awakening_length = period_metrics.get("Average Awakening Length")
                            metrics.total_activity = period_metrics.get("Total Counts")
                            metrics.movement_index = period_metrics.get("Movement Index")
                            metrics.fragmentation_index = period_metrics.get("Fragmentation Index")
                            metrics.sleep_fragmentation_index = period_metrics.get("Sleep Fragmentation Index")
                            metrics.sadeh_onset = period_metrics.get("Sadeh Algorithm Value at Sleep Onset")
                            metrics.sadeh_offset = period_metrics.get("Sadeh Algorithm Value at Sleep Offset")
                            metrics.overlapping_nonwear_minutes_algorithm = period_metrics.get("Overlapping Nonwear Minutes (Algorithm)")
                            metrics.overlapping_nonwear_minutes_sensor = period_metrics.get("Overlapping Nonwear Minutes (Sensor)")

                            # Store calculated values back to database for future exports
                            self.db_manager.save_sleep_metrics(metrics, is_autosave=False)
                            logger.debug("Calculated and saved metrics for %s on %s", filename, metrics.analysis_date)

            except Exception as e:
                import traceback

                logger.warning("Error calculating metrics for %s: %s", metrics.filename, e)
                logger.warning("Full traceback: %s", traceback.format_exc())
                # Continue with export even if calculation fails for one file
                continue

    def _export_nonwear_markers_separate(
        self,
        sleep_metrics_list: list[SleepMetrics],
        output_path: Path,
        include_headers: bool,
        include_metadata: bool,
    ) -> None:
        """Export manual nonwear markers to a separate CSV file."""
        from datetime import datetime

        nonwear_data = []

        for metrics in sleep_metrics_list:
            try:
                filename = metrics.filename
                if not filename or not metrics.analysis_date:
                    continue

                # Parse analysis date
                try:
                    analysis_date = datetime.strptime(metrics.analysis_date, "%Y-%m-%d").date()
                except ValueError:
                    continue

                # Load manual nonwear markers for this file/date
                daily_nonwear = self.db_manager.load_manual_nonwear_markers(filename, analysis_date)
                complete_periods = daily_nonwear.get_complete_periods()

                if not complete_periods:
                    continue

                # Get participant info
                participant_id = ""
                group = ""
                timepoint = ""
                if hasattr(metrics, "participant") and metrics.participant:
                    participant_id = getattr(metrics.participant, "numerical_id", "")
                    group = getattr(metrics.participant, "group_str", "")
                    timepoint = getattr(metrics.participant, "timepoint_str", "")

                # Add each nonwear period as a row
                for i, period in enumerate(complete_periods, start=1):
                    start_dt = datetime.fromtimestamp(period.start_timestamp)
                    end_dt = datetime.fromtimestamp(period.end_timestamp)
                    duration = period.duration_minutes or 0.0

                    nonwear_data.append(
                        {
                            "Participant ID": participant_id,
                            "Group": group,
                            "Timepoint": timepoint,
                            "Filename": filename,
                            "Date": metrics.analysis_date,
                            "Nonwear Period Index": i,
                            "Start Time": start_dt.strftime("%H:%M"),
                            "End Time": end_dt.strftime("%H:%M"),
                            "Start Datetime": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                            "End Datetime": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                            "Duration (minutes)": round(duration, 1),
                        }
                    )

            except Exception as e:
                logger.warning("Failed to get nonwear data for %s: %s", metrics.filename, e)
                continue

        if not nonwear_data:
            logger.debug("No nonwear markers to export separately")
            return

        # Create DataFrame and export
        nonwear_df = pd.DataFrame(nonwear_data)

        # Sanitize string columns
        for col in nonwear_df.select_dtypes(include=["object"]).columns:
            nonwear_df[col] = nonwear_df[col].apply(self._sanitize_csv_cell)

        # Sort by participant and date
        sort_columns = []
        if "Participant ID" in nonwear_df.columns:
            sort_columns.append("Participant ID")
        if "Date" in nonwear_df.columns:
            sort_columns.append("Date")
        if "Nonwear Period Index" in nonwear_df.columns:
            sort_columns.append("Nonwear Period Index")

        if sort_columns:
            nonwear_df = nonwear_df.sort_values(by=sort_columns, ascending=True)

        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_path / f"nonwear_markers_{timestamp}.csv"

        # Write to CSV atomically
        temp_path = filepath.with_suffix(f".tmp.{os.getpid()}")
        try:
            with open(temp_path, "w", newline="", encoding="utf-8") as f:
                if include_metadata:
                    f.write("#\n")
                    f.write("# Manual Nonwear Markers Export\n")
                    f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Total Nonwear Periods: {len(nonwear_data)}\n")
                    f.write(f"# Participants with Nonwear: {len({row['Participant ID'] for row in nonwear_data})}\n")
                    f.write("#\n")

                nonwear_df.to_csv(f, index=False, header=include_headers, float_format="%.1f")

                f.flush()
                os.fsync(f.fileno())

            if temp_path.stat().st_size == 0:
                msg = "Nonwear CSV write produced empty file"
                raise OSError(msg)

            temp_path.replace(filepath)
            logger.info("Exported %d nonwear periods to %s", len(nonwear_data), filepath)

        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _group_export_data(self, sleep_metrics_list: list[SleepMetrics], grouping_option: int) -> dict[str, list[SleepMetrics]]:
        """Group sleep metrics based on grouping option."""
        if grouping_option == 0:  # All data in one file
            return {"all_data": sleep_metrics_list}
        if grouping_option == 1:  # By participant
            groups = {}
            for metrics in sleep_metrics_list:
                participant_id = metrics.participant.numerical_id
                if participant_id not in groups:
                    groups[participant_id] = []
                groups[participant_id].append(metrics)
            return groups
        if grouping_option == 2:  # By group
            groups = {}
            for metrics in sleep_metrics_list:
                group = metrics.participant.group_str
                if group not in groups:
                    groups[group] = []
                groups[group].append(metrics)
            return groups
        if grouping_option == 3:  # By timepoint
            groups = {}
            for metrics in sleep_metrics_list:
                timepoint = metrics.participant.timepoint_str
                if timepoint not in groups:
                    groups[timepoint] = []
                groups[timepoint].append(metrics)
            return groups
        return {"all_data": sleep_metrics_list}

    def save_comprehensive_sleep_metrics(
        self,
        sleep_metrics_list: list[SleepMetrics],
        algorithm_name: AlgorithmType = AlgorithmType.SADEH_1994_ACTILIFE,
    ) -> str | None:
        """
        Save comprehensive sleep metrics to ongoing backup file.

        This saves BOTH the main sleep_metrics table AND the sleep_markers_extended
        table to ensure data consistency between legacy single-period storage and
        multi-period extended storage.
        """
        if not sleep_metrics_list:
            return None

        # Sanitize algorithm name to prevent security issues
        safe_algorithm_name = sanitize_filename_component(algorithm_name)
        if not safe_algorithm_name:
            safe_algorithm_name = sanitize_filename_component(AlgorithmType.SADEH_1994_ACTILIFE)

        try:
            # Save to database - both main table AND extended markers table
            for metrics in sleep_metrics_list:
                metrics.algorithm_type = algorithm_name
                # Save to main sleep_metrics table (legacy + comprehensive data)
                self.db_manager.save_sleep_metrics(metrics, is_autosave=False)
                # CRITICAL FIX #1: Also save to sleep_markers_extended table (multi-period support)
                # This ensures atomicity between the two tables
                self.db_manager.save_daily_sleep_markers(metrics)

            logger.debug("Saved comprehensive sleep metrics to database for %s", sleep_metrics_list[0].filename)
            return "saved"

        except (DatabaseError, ValidationError) as e:
            logger.warning("Error saving comprehensive sleep metrics: %s", e)
            return None

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _create_backup(self, csv_path: Path) -> Path:
        """Create a backup copy with hash verification and rotation."""
        backup_dir = csv_path.parent / DirectoryName.BACKUPS
        backup_dir.mkdir(mode=0o755, exist_ok=True)

        backup_filename = get_backup_filename(csv_path.name)
        backup_path = backup_dir / backup_filename

        original_hash = self._calculate_file_hash(csv_path)

        shutil.copy2(csv_path, backup_path)

        backup_hash = self._calculate_file_hash(backup_path)
        if original_hash != backup_hash:
            backup_path.unlink()
            msg = f"Backup verification failed for {csv_path.name}"
            raise DatabaseError(msg, ErrorCodes.FILE_CORRUPTED)

        checksum_path = backup_path.with_suffix(".sha256")
        checksum_path.write_text(f"{backup_hash}  {backup_path.name}\n")

        logger.info(f"Backup verified: {backup_path}")

        backup_pattern = f"*_{csv_path.stem}_*.csv"
        existing_backups = sorted(backup_dir.glob(backup_pattern))

        if len(existing_backups) > self.max_backups:
            for old_backup in existing_backups[: -self.max_backups]:
                try:
                    old_backup.unlink()
                    checksum_file = old_backup.with_suffix(".sha256")
                    if checksum_file.exists():
                        checksum_file.unlink()
                    logger.debug(f"Deleted old backup: {old_backup.name}")
                except OSError as e:
                    logger.warning(f"Failed to delete old backup {old_backup}: {e}")

        return backup_path
