"""Repository for sleep metrics database operations."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sleep_scoring_app.core.constants import (
    AlgorithmType,
    DatabaseColumn,
    DatabaseTable,
    ExportColumn,
    FeatureFlags,
    ParticipantGroup,
    ParticipantTimepoint,
)
from sleep_scoring_app.core.dataclasses import (
    DailySleepMarkers,
    ParticipantInfo,
    SleepMetrics,
    SleepPeriod,
)
from sleep_scoring_app.core.exceptions import DatabaseError, ErrorCodes, ValidationError
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.config import DataConfig
from sleep_scoring_app.data.repositories.base_repository import BaseRepository
from sleep_scoring_app.utils.column_registry import column_registry

if TYPE_CHECKING:
    from datetime import date

logger = logging.getLogger(__name__)


class SleepMetricsRepository(BaseRepository):
    """Repository for sleep metrics operations."""

    def save_sleep_metrics(self, sleep_metrics: SleepMetrics) -> bool:
        """Save sleep metrics to database with validation."""
        if not isinstance(sleep_metrics, SleepMetrics):
            msg = "sleep_metrics must be SleepMetrics instance"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        InputValidator.validate_string(sleep_metrics.filename, min_length=1, name="filename")
        InputValidator.validate_string(sleep_metrics.analysis_date, min_length=1, name="analysis_date")

        try:
            return self._save_permanent_metrics(sleep_metrics)

        except (DatabaseError, ValidationError):
            raise
        except Exception as e:
            logger.exception("Unexpected error saving sleep metrics")
            msg = f"Unexpected error saving sleep metrics: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def _validate_sleep_metrics_data(self, data: dict[str, Any]) -> None:
        """Validate sleep metrics data before database insertion."""
        required_fields = [DatabaseColumn.FILENAME, DatabaseColumn.ANALYSIS_DATE]

        for field in required_fields:
            if field not in data or not data[field]:
                msg = f"Missing required field: {field}"
                raise ValidationError(msg, ErrorCodes.MISSING_REQUIRED)

        InputValidator.validate_string(data[DatabaseColumn.FILENAME], min_length=1, name="filename")

        if data.get(DatabaseColumn.ONSET_TIMESTAMP) is not None:
            InputValidator.validate_timestamp(data[DatabaseColumn.ONSET_TIMESTAMP])

        if data.get(DatabaseColumn.OFFSET_TIMESTAMP) is not None:
            InputValidator.validate_timestamp(data[DatabaseColumn.OFFSET_TIMESTAMP])

    def _validate_export_data(self, data: dict[str, Any]) -> None:
        """Validate export data structure."""
        if not isinstance(data, dict):
            msg = "Export data must be a dictionary"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        if "filename" not in data or not data["filename"]:
            msg = "Export data missing filename"
            raise ValidationError(msg, ErrorCodes.MISSING_REQUIRED)

    def _save_permanent_metrics(self, metrics: SleepMetrics) -> bool:
        """Save to permanent sleep_metrics table with validation."""
        db_data = self._metrics_to_database_dict(metrics)
        self._validate_sleep_metrics_data(db_data)

        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        with self._get_connection() as conn:
            columns = []
            values = []
            placeholders = []

            for column_name, value in db_data.items():
                if value is not None:
                    columns.append(self._validate_column_name(column_name))
                    values.append(value)
                    placeholders.append("?")

            columns_str = ", ".join(columns)
            placeholders_str = ", ".join(placeholders)

            conn.execute(
                f"INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders_str})",
                values,
            )

            conn.commit()
            logger.info("Saved permanent metrics for %s", metrics.filename)
            return True

    def save_sleep_metrics_atomic(self, metrics: SleepMetrics) -> bool:
        """Atomically save sleep metrics to BOTH sleep_metrics and sleep_markers_extended tables."""
        if not isinstance(metrics, SleepMetrics):
            msg = "metrics must be SleepMetrics instance"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        InputValidator.validate_string(metrics.filename, min_length=1, name="filename")
        InputValidator.validate_string(metrics.analysis_date, min_length=1, name="analysis_date")

        db_data = self._metrics_to_database_dict(metrics)
        self._validate_sleep_metrics_data(db_data)

        metrics_table = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
        markers_table = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)

        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN TRANSACTION")

                try:
                    # 1. Save to sleep_metrics table
                    columns = []
                    values = []
                    placeholders = []

                    for column_name, value in db_data.items():
                        if value is not None:
                            columns.append(self._validate_column_name(column_name))
                            values.append(value)
                            placeholders.append("?")

                    columns_str = ", ".join(columns)
                    placeholders_str = ", ".join(placeholders)

                    conn.execute(
                        f"INSERT OR REPLACE INTO {metrics_table} ({columns_str}) VALUES ({placeholders_str})",
                        values,
                    )

                    # 2. Save to sleep_markers_extended table
                    conn.execute(
                        f"""
                        DELETE FROM {markers_table}
                        WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                        AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                        """,
                        (metrics.filename, metrics.analysis_date),
                    )

                    for i, period in enumerate(
                        [
                            metrics.daily_sleep_markers.period_1,
                            metrics.daily_sleep_markers.period_2,
                            metrics.daily_sleep_markers.period_3,
                            metrics.daily_sleep_markers.period_4,
                        ],
                        1,
                    ):
                        if period is not None and period.is_complete:
                            duration_minutes = int(period.duration_minutes) if period.duration_minutes else None

                            conn.execute(
                                f"""
                                INSERT INTO {markers_table} (
                                    {self._validate_column_name(DatabaseColumn.FILENAME)},
                                    {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                                    {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)},
                                    {self._validate_column_name(DatabaseColumn.MARKER_INDEX)},
                                    {self._validate_column_name(DatabaseColumn.ONSET_TIMESTAMP)},
                                    {self._validate_column_name(DatabaseColumn.OFFSET_TIMESTAMP)},
                                    {self._validate_column_name(DatabaseColumn.DURATION_MINUTES)},
                                    {self._validate_column_name(DatabaseColumn.MARKER_TYPE)}
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    metrics.filename,
                                    metrics.participant.numerical_id,
                                    metrics.analysis_date,
                                    i,
                                    period.onset_timestamp,
                                    period.offset_timestamp,
                                    duration_minutes,
                                    period.marker_type,
                                ),
                            )

                    conn.commit()
                    logger.info("Atomically saved metrics and markers for %s on %s", metrics.filename, metrics.analysis_date)
                    return True

                except sqlite3.Error as e:
                    conn.rollback()
                    logger.exception("Database error during atomic save for %s on %s", metrics.filename, metrics.analysis_date)
                    msg = f"Failed atomic save for {metrics.filename} on {metrics.analysis_date}: {e}"
                    raise DatabaseError(
                        msg,
                        ErrorCodes.DB_INSERT_FAILED,
                    ) from e
                except Exception as e:
                    conn.rollback()
                    logger.exception("Unexpected error during atomic save for %s on %s", metrics.filename, metrics.analysis_date)
                    msg = f"Unexpected error during atomic save for {metrics.filename} on {metrics.analysis_date}: {e}"
                    raise DatabaseError(
                        msg,
                        ErrorCodes.DB_INSERT_FAILED,
                    ) from e

        except DatabaseError:
            raise
        except sqlite3.Error as e:
            logger.exception("Database connection failed for atomic save of %s on %s", metrics.filename, metrics.analysis_date)
            msg = f"Connection failed for atomic save of {metrics.filename} on {metrics.analysis_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_CONNECTION_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected connection error for atomic save of %s on %s", metrics.filename, metrics.analysis_date)
            msg = f"Unexpected connection error for atomic save of {metrics.filename} on {metrics.analysis_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_CONNECTION_FAILED,
            ) from e

    def _metrics_to_database_dict(self, metrics: SleepMetrics) -> dict[str, Any]:
        """Convert SleepMetrics to database dictionary using column registry."""
        db_data = {
            DatabaseColumn.FILENAME: metrics.filename,
            DatabaseColumn.PARTICIPANT_ID: metrics.participant.numerical_id,
            DatabaseColumn.PARTICIPANT_GROUP: metrics.participant.group_str,
            DatabaseColumn.PARTICIPANT_TIMEPOINT: metrics.participant.timepoint_str,
            DatabaseColumn.ANALYSIS_DATE: metrics.analysis_date,
            DatabaseColumn.UPDATED_AT: datetime.now().isoformat(),
        }

        metrics_dict = metrics.to_dict()

        for column in column_registry.get_all():
            if column.database_column and column.database_column not in db_data:
                value = self._get_metrics_value(metrics_dict, column)
                if value is not None:
                    db_data[column.database_column] = value

        return db_data

    def _get_metrics_value(self, metrics_dict: dict[str, Any], column) -> Any:
        """Get value from metrics dictionary using column definition."""
        possible_names = [column.name, column.export_column, column.display_name]

        for name in possible_names:
            if name and name in metrics_dict:
                value = metrics_dict[name]
                return self._convert_value_for_database(value, column.data_type)

        return column.default_value

    def load_sleep_metrics_by_participant_key(self, participant_key: str, analysis_date: str | None = None) -> list[SleepMetrics]:
        """Load sleep metrics by PARTICIPANT_KEY with validation."""
        InputValidator.validate_string(participant_key, min_length=1, name="participant_key")

        if analysis_date is not None:
            InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row

            if analysis_date:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} = ?
                    AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """,
                    (participant_key, analysis_date),
                )
            else:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} DESC,
                          {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """,
                    (participant_key,),
                )

            rows = cursor.fetchall()
            metrics_list = []
            for row in rows:
                metrics = self._row_to_sleep_metrics(dict(row))
                if metrics:
                    metrics_list.append(metrics)

            return metrics_list

    def load_sleep_metrics(self, filename: str | None = None, analysis_date: str | None = None) -> list[SleepMetrics]:
        """Load sleep metrics from database with validation."""
        if filename is not None:
            InputValidator.validate_string(filename, min_length=1, name="filename")

        if analysis_date is not None:
            InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row

            if filename and analysis_date:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """,
                    (filename, analysis_date),
                )
            elif filename:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} DESC,
                           {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """,
                    (filename,),
                )
            else:
                cursor = conn.execute(f"""
                    SELECT * FROM {table_name}
                    ORDER BY {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """)

            results = []
            for row in cursor.fetchall():
                try:
                    result = self._row_to_sleep_metrics(row)
                    self._load_period_metrics_for_sleep_metrics(conn, result)
                    results.append(result)
                except (ValueError, KeyError, ValidationError) as e:
                    logger.warning("Skipping invalid database row: %s", e)
                    continue

            logger.debug("Loaded %s sleep metrics records", len(results))
            return results

    def get_sleep_metrics_by_filename_and_date(self, filename: str, analysis_date: str) -> SleepMetrics | None:
        """Get a single sleep metrics record by filename and date."""
        results = self.load_sleep_metrics(filename=filename, analysis_date=analysis_date)
        return results[0] if results else None

    def _row_to_sleep_metrics(self, row: sqlite3.Row) -> SleepMetrics:
        """Convert database row to SleepMetrics object with validation."""

        def safe_get(column_name, default=None):
            try:
                return row[column_name]
            except (KeyError, IndexError):
                return default

        if not safe_get(DatabaseColumn.FILENAME):
            msg = "Database row missing filename"
            raise ValidationError(msg, ErrorCodes.MISSING_REQUIRED)

        numerical_id = InputValidator.validate_string(
            safe_get(DatabaseColumn.PARTICIPANT_ID) or "Unknown",
            min_length=1,
            name="participant_id",
        )
        timepoint = safe_get(DatabaseColumn.PARTICIPANT_TIMEPOINT) or "BO"
        group = safe_get(DatabaseColumn.PARTICIPANT_GROUP) or "G1"
        full_id = f"{numerical_id} {timepoint} {group}" if numerical_id != "UNKNOWN" else "UNKNOWN BO G1"

        participant = ParticipantInfo(
            numerical_id=numerical_id,
            full_id=full_id,
            group=group,
            timepoint=timepoint,
        )

        onset_timestamp = safe_get(DatabaseColumn.ONSET_TIMESTAMP)
        offset_timestamp = safe_get(DatabaseColumn.OFFSET_TIMESTAMP)

        if onset_timestamp is not None:
            onset_timestamp = InputValidator.validate_timestamp(onset_timestamp)

        if offset_timestamp is not None:
            offset_timestamp = InputValidator.validate_timestamp(offset_timestamp)

        daily_markers = DailySleepMarkers()

        daily_markers_json = safe_get(DatabaseColumn.DAILY_SLEEP_MARKERS)
        if daily_markers_json:
            try:
                markers_data = json.loads(daily_markers_json) if isinstance(daily_markers_json, str) else daily_markers_json
                daily_markers = DailySleepMarkers.from_dict(markers_data)
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning("Failed to parse daily_sleep_markers JSON: %s", e)

        if not daily_markers.get_complete_periods() and onset_timestamp is not None and offset_timestamp is not None:
            sleep_period = SleepPeriod(
                onset_timestamp=onset_timestamp,
                offset_timestamp=offset_timestamp,
            )
            daily_markers.period_1 = sleep_period

        return SleepMetrics(
            participant=participant,
            filename=InputValidator.validate_string(safe_get(DatabaseColumn.FILENAME), min_length=1, name="filename"),
            analysis_date=InputValidator.validate_string(safe_get(DatabaseColumn.ANALYSIS_DATE) or "", min_length=0, name="analysis_date"),
            algorithm_type=AlgorithmType.from_value(safe_get(DatabaseColumn.ALGORITHM_TYPE) or AlgorithmType.SADEH_1994_ACTILIFE),
            daily_sleep_markers=daily_markers,
            onset_time=safe_get(DatabaseColumn.ONSET_TIME) or "",
            offset_time=safe_get(DatabaseColumn.OFFSET_TIME) or "",
            total_sleep_time=safe_get(DatabaseColumn.TOTAL_SLEEP_TIME),
            sleep_efficiency=safe_get(DatabaseColumn.SLEEP_EFFICIENCY),
            total_minutes_in_bed=safe_get(DatabaseColumn.TOTAL_MINUTES_IN_BED),
            waso=safe_get(DatabaseColumn.WASO),
            awakenings=safe_get(DatabaseColumn.AWAKENINGS),
            average_awakening_length=safe_get(DatabaseColumn.AVERAGE_AWAKENING_LENGTH),
            total_activity=safe_get(DatabaseColumn.TOTAL_ACTIVITY),
            movement_index=safe_get(DatabaseColumn.MOVEMENT_INDEX),
            fragmentation_index=safe_get(DatabaseColumn.FRAGMENTATION_INDEX),
            sleep_fragmentation_index=safe_get(DatabaseColumn.SLEEP_FRAGMENTATION_INDEX),
            sadeh_onset=safe_get(DatabaseColumn.SADEH_ONSET),
            sadeh_offset=safe_get(DatabaseColumn.SADEH_OFFSET),
            overlapping_nonwear_minutes_algorithm=safe_get(DatabaseColumn.OVERLAPPING_NONWEAR_MINUTES_ALGORITHM),
            overlapping_nonwear_minutes_sensor=safe_get(DatabaseColumn.OVERLAPPING_NONWEAR_MINUTES_SENSOR),
            sleep_algorithm_name=safe_get(DatabaseColumn.ALGORITHM_TYPE),
            sleep_period_detector_id=safe_get(DatabaseColumn.ONSET_OFFSET_RULE),
            created_at=safe_get(DatabaseColumn.CREATED_AT) or "",
            updated_at=safe_get(DatabaseColumn.UPDATED_AT) or "",
        )

    def _load_period_metrics_for_sleep_metrics(self, conn: sqlite3.Connection, metrics: SleepMetrics) -> None:
        """Load period metrics from sleep_markers_extended and populate SleepMetrics._dynamic_fields."""
        if not metrics.filename or not metrics.analysis_date:
            return

        table_name = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)

        try:
            cursor = conn.execute(
                f"""
                SELECT
                    {self._validate_column_name(DatabaseColumn.MARKER_INDEX)},
                    {self._validate_column_name(DatabaseColumn.PERIOD_METRICS_JSON)}
                FROM {table_name}
                WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
            """,
                (metrics.filename, metrics.analysis_date),
            )

            for row in cursor.fetchall():
                marker_index = row[0]
                period_metrics_json = row[1]

                if period_metrics_json:
                    try:
                        period_metrics = json.loads(period_metrics_json)
                        period_key = f"period_{marker_index}_metrics"
                        metrics._dynamic_fields[period_key] = period_metrics
                        logger.debug("Loaded period %s metrics for %s", marker_index, metrics.filename)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("Failed to parse period metrics JSON for %s period %s: %s", metrics.filename, marker_index, e)

        except sqlite3.OperationalError as e:
            if "no such column" in str(e).lower():
                logger.debug("period_metrics_json column not yet available: %s", e)
            else:
                logger.warning("Error loading period metrics: %s", e)

    def _dict_to_sleep_metrics(self, data: dict[str, Any]) -> SleepMetrics:
        """Convert dictionary data to SleepMetrics object with validation."""
        self._validate_export_data(data)

        try:
            group = ParticipantGroup(data.get("Participant Group", ParticipantGroup.GROUP_1))
        except ValueError:
            logger.warning("Invalid ParticipantGroup in database, using GROUP_1")
            group = ParticipantGroup.GROUP_1

        try:
            timepoint = ParticipantTimepoint(data.get("Participant Timepoint", ParticipantTimepoint.T1))
        except ValueError:
            logger.warning("Invalid ParticipantTimepoint in database, using T1")
            timepoint = ParticipantTimepoint.T1

        participant = ParticipantInfo(
            numerical_id=InputValidator.validate_string(
                data.get("Numerical Participant ID", "Unknown"),
                min_length=1,
                name="participant_id",
            ),
            group=group,
            timepoint=timepoint,
        )

        onset_timestamp = data.get("onset_timestamp")
        offset_timestamp = data.get("offset_timestamp")

        if onset_timestamp is not None:
            onset_timestamp = InputValidator.validate_timestamp(onset_timestamp)

        if offset_timestamp is not None:
            offset_timestamp = InputValidator.validate_timestamp(offset_timestamp)

        daily_markers = DailySleepMarkers()
        if onset_timestamp is not None and offset_timestamp is not None:
            sleep_period = SleepPeriod(
                onset_timestamp=onset_timestamp,
                offset_timestamp=offset_timestamp,
            )
            daily_markers.period_1 = sleep_period

        return SleepMetrics(
            participant=participant,
            filename=InputValidator.validate_string(data.get("filename", ""), min_length=1, name="filename"),
            analysis_date=data.get("Onset Date", ""),
            algorithm_type=AlgorithmType.from_value(data.get("Sleep Algorithm", AlgorithmType.SADEH_1994_ACTILIFE)),
            daily_sleep_markers=daily_markers,
            onset_time=data.get("Onset Time", ""),
            offset_time=data.get("Offset Time", ""),
            total_sleep_time=data.get("Total Sleep Time (TST)"),
            sleep_efficiency=data.get("Efficiency"),
            total_minutes_in_bed=data.get("Total Minutes in Bed"),
            waso=data.get("Wake After Sleep Onset (WASO)"),
            awakenings=data.get("Number of Awakenings"),
            average_awakening_length=data.get("Average Awakening Length"),
            total_activity=data.get("Total Counts"),
            movement_index=data.get("Movement Index"),
            fragmentation_index=data.get("Fragmentation Index"),
            sleep_fragmentation_index=data.get("Sleep Fragmentation Index"),
            sadeh_onset=data.get("Sadeh Algorithm Value at Sleep Onset"),
            sadeh_offset=data.get("Sadeh Algorithm Value at Sleep Offset"),
            overlapping_nonwear_minutes_algorithm=data.get("Overlapping Nonwear Minutes (Algorithm)"),
            overlapping_nonwear_minutes_sensor=data.get("Overlapping Nonwear Minutes (Sensor)"),
            sleep_algorithm_name=data.get("Sleep Algorithm"),
            sleep_period_detector_id=data.get("Onset/Offset Rule"),
            updated_at=data.get("Saved At", ""),
        )

    def delete_sleep_metrics_for_date(self, filename: str, analysis_date: str) -> bool:
        """Delete sleep metrics for a specific file and analysis date."""
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        metrics_table = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
        markers_table = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)

        try:
            with self._get_connection() as conn:
                conn.execute(
                    f"""
                    DELETE FROM {metrics_table}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                    """,
                    (filename, analysis_date),
                )

                conn.execute(
                    f"""
                    DELETE FROM {markers_table}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                    """,
                    (filename, analysis_date),
                )

                conn.commit()
                logger.info("Deleted sleep metrics for %s on %s", filename, analysis_date)
                return True

        except sqlite3.Error as e:
            logger.exception("Failed to delete sleep metrics for %s on %s", filename, analysis_date)
            msg = f"Failed to delete sleep metrics: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_DELETE_FAILED) from e

    def get_database_stats(self) -> dict[str, int]:
        """Get database statistics with validation (includes sleep and nonwear markers)."""
        sleep_table = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
        nonwear_table = self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)

        with self._get_connection() as conn:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {sleep_table}")
            total_records = cursor.fetchone()[0]

            # Count nonwear markers
            try:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {nonwear_table}")
                nonwear_records = cursor.fetchone()[0]
            except Exception:
                nonwear_records = 0

            cursor = conn.execute(f"""
                SELECT COUNT(DISTINCT {self._validate_column_name(DatabaseColumn.FILENAME)})
                FROM {sleep_table}
            """)
            unique_files = cursor.fetchone()[0]

            return {
                "total_records": total_records,
                "nonwear_records": nonwear_records,
                "unique_files": unique_files,
            }
