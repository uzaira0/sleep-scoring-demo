#!/usr/bin/env python3
"""
Unified Marker Service for Sleep Scoring Application.

Consolidates all marker-related operations:
- MarkerValidationService
- MarkerClassificationService
- MarkerPersistenceService
- MarkerCoordinationService
- MarkerCacheService
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from sleep_scoring_app.core.constants import DatabaseTable, MarkerLimits

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepMetrics, SleepPeriod
    from sleep_scoring_app.core.dataclasses_markers import DailyNonwearMarkers
    from sleep_scoring_app.data.database import DatabaseManager

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================


@dataclass(frozen=True)
class ValidationResult:
    """Immutable validation result."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarkerStatus:
    """Immutable marker status for a date."""

    has_sleep_markers: bool = False
    has_nonwear_markers: bool = False
    sleep_periods_count: int = 0
    nonwear_periods_count: int = 0
    is_complete: bool = False


# ==================== Unified Marker Service ====================


class MarkerService:
    """
    Unified marker operations service.

    Organized by responsibility with clear section headers.
    Consolidates all marker validation, classification, persistence,
    coordination, and caching operations.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize marker service with database manager."""
        self._db = db_manager
        # Simple dict cache for marker data
        self._cache: dict[str, DailySleepMarkers | DailyNonwearMarkers] = {}

    # ==================== Validation ====================

    def validate(self, markers: DailySleepMarkers) -> ValidationResult:
        """
        Validate sleep markers.

        Args:
            markers: Daily sleep markers to validate

        Returns:
            ValidationResult with errors and warnings

        """
        errors: list[str] = []
        warnings: list[str] = []

        for period in markers.get_complete_periods():
            # Check timestamps are valid
            if period.onset_timestamp is not None and period.offset_timestamp is not None:
                if period.onset_timestamp >= period.offset_timestamp:
                    errors.append(f"Period {period.marker_index}: onset must be before offset")

            # Check duration is reasonable
            duration_hours = period.duration_hours
            if duration_hours is not None:
                if duration_hours > 24:
                    warnings.append(f"Period {period.marker_index}: duration > 24 hours")
                if duration_hours < 0.5:
                    warnings.append(f"Period {period.marker_index}: duration < 30 minutes")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_nonwear(self, markers: DailyNonwearMarkers) -> ValidationResult:
        """
        Validate nonwear markers.

        Args:
            markers: Daily nonwear markers to validate

        Returns:
            ValidationResult with errors and warnings

        """
        errors: list[str] = []
        warnings: list[str] = []

        for period in markers.get_complete_periods():
            # ManualNonwearPeriod uses start_timestamp and end_timestamp (not onset/offset)
            if period.start_timestamp is not None and period.end_timestamp is not None:
                if period.start_timestamp >= period.end_timestamp:
                    errors.append(f"Nonwear period {period.marker_index}: start must be before end")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_marker_addition(self, daily_markers: DailySleepMarkers, new_period: SleepPeriod) -> tuple[bool, str]:
        """
        Validate if a new sleep period can be added.

        Args:
            daily_markers: Existing daily markers
            new_period: New period to add

        Returns:
            Tuple of (is_valid, error_message)

        """
        # Check if we have space for new period
        if not daily_markers.has_space_for_new_period():
            return False, f"Maximum {MarkerLimits.MAX_SLEEP_PERIODS_PER_DAY} sleep periods per day allowed"

        # Check for overlaps with existing periods
        if new_period.is_complete:
            for existing_period in daily_markers.get_complete_periods():
                if self._periods_overlap(new_period, existing_period):
                    return False, "Sleep periods cannot overlap"

        return True, ""

    def validate_duration_tie(self, daily_markers: DailySleepMarkers) -> tuple[bool, str]:
        """
        Check for duration ties and return validation result.

        Args:
            daily_markers: Daily markers to check

        Returns:
            Tuple of (has_tie, message)

        """
        if daily_markers.check_duration_tie():
            return True, "Cannot determine main sleep: multiple periods with identical duration"
        return False, ""

    @staticmethod
    def _periods_overlap(period1: SleepPeriod, period2: SleepPeriod) -> bool:
        """Check if two sleep periods overlap in time."""
        if not (period1.is_complete and period2.is_complete):
            return False

        # Type guards for None checks
        if period1.onset_timestamp is None or period1.offset_timestamp is None or period2.onset_timestamp is None or period2.offset_timestamp is None:
            return False

        # Check for any time overlap
        return period1.onset_timestamp < period2.offset_timestamp and period2.onset_timestamp < period1.offset_timestamp

    # ==================== Classification ====================

    def update_classifications(self, daily_markers: DailySleepMarkers) -> None:
        """Update all marker classifications based on current durations."""
        daily_markers.update_classifications()
        logger.debug("Updated marker classifications")

    def handle_duration_tie_cancellation(self, daily_markers: DailySleepMarkers, last_added_index: int) -> bool:
        """
        Handle duration tie by removing the last added period.

        Args:
            daily_markers: The daily markers collection
            last_added_index: Index of the last added period (1, 2, 3, or 4)

        Returns:
            True if successfully handled, False otherwise

        """
        try:
            # Remove the last added period
            if last_added_index == 1:
                daily_markers.period_1 = None
            elif last_added_index == 2:
                daily_markers.period_2 = None
            elif last_added_index == 3:
                daily_markers.period_3 = None
            elif last_added_index == 4:
                daily_markers.period_4 = None
            else:
                return False

            # Update classifications for remaining periods
            self.update_classifications(daily_markers)
            logger.info("Removed period %d due to duration tie", last_added_index)
            return True

        except Exception:
            logger.exception("Failed to handle duration tie cancellation")
            return False

    # ==================== Persistence ====================

    def save(
        self,
        filename: str,
        sleep_date: date | str,
        markers: DailySleepMarkers,
    ) -> bool:
        """
        Save sleep markers to database.

        Args:
            filename: File identifier
            sleep_date: Sleep date (date or ISO string)
            markers: Sleep markers to save

        Returns:
            True if save was successful

        """
        try:
            # Validate before saving
            result = self.validate(markers)
            if not result.is_valid:
                logger.error("Cannot save invalid markers: %s", result.errors)
                return False

            # Convert date to string if needed
            date_str = sleep_date.isoformat() if isinstance(sleep_date, date) else sleep_date

            # Serialize and save using JSON
            data = markers.to_dict()
            self._db.execute(
                f"""
                INSERT OR REPLACE INTO {self._db._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)}
                (filename, analysis_date, markers_json)
                VALUES (?, ?, ?)
                """,
                (filename, date_str, json.dumps(data)),
            )

            # Invalidate cache
            self._invalidate_cache_key(filename, date_str, "sleep")
            logger.debug("Saved sleep markers for %s on %s", filename, date_str)
            return True

        except Exception:
            logger.exception("Failed to save sleep markers")
            return False

    def save_nonwear(
        self,
        filename: str,
        sleep_date: date | str,
        markers: DailyNonwearMarkers,
    ) -> bool:
        """
        Save nonwear markers to database.

        Args:
            filename: File identifier
            sleep_date: Sleep date (date or ISO string)
            markers: Nonwear markers to save

        Returns:
            True if save was successful

        """
        try:
            # Convert date to string if needed
            date_str = sleep_date.isoformat() if isinstance(sleep_date, date) else sleep_date

            # Serialize and save using JSON
            data = markers.to_dict()
            self._db.execute(
                f"""
                INSERT OR REPLACE INTO {self._db._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)}
                (filename, sleep_date, markers_json)
                VALUES (?, ?, ?)
                """,
                (filename, date_str, json.dumps(data)),
            )

            # Invalidate cache
            self._invalidate_cache_key(filename, date_str, "nonwear")
            logger.debug("Saved nonwear markers for %s on %s", filename, date_str)
            return True

        except Exception:
            logger.exception("Failed to save nonwear markers")
            return False

    def load(self, filename: str, sleep_date: date | str) -> DailySleepMarkers | None:
        """
        Load sleep markers from database.

        Args:
            filename: File identifier
            sleep_date: Sleep date (date or ISO string)

        Returns:
            DailySleepMarkers if found, None otherwise

        """
        # Convert date to string if needed
        date_str = sleep_date.isoformat() if isinstance(sleep_date, date) else sleep_date

        # Check cache first
        cache_key = self._make_cache_key(filename, date_str, "sleep")
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore

        # Query database
        row = self._db.fetch_one(
            f"""
            SELECT markers_json FROM {self._db._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)}
            WHERE filename = ? AND analysis_date = ?
            """,
            (filename, date_str),
        )

        if row is None:
            return None

        # Deserialize using json.loads (NOT eval)
        from sleep_scoring_app.core.dataclasses import DailySleepMarkers

        data = json.loads(row[0])
        markers = DailySleepMarkers.from_dict(data)
        self._cache[cache_key] = markers
        return markers

    def load_nonwear(self, filename: str, sleep_date: date | str) -> DailyNonwearMarkers | None:
        """
        Load nonwear markers from database.

        Args:
            filename: File identifier
            sleep_date: Sleep date (date or ISO string)

        Returns:
            DailyNonwearMarkers if found, None otherwise

        """
        # Convert date to string if needed
        date_str = sleep_date.isoformat() if isinstance(sleep_date, date) else sleep_date

        # Check cache first
        cache_key = self._make_cache_key(filename, date_str, "nonwear")
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore

        # Query database
        row = self._db.fetch_one(
            f"""
            SELECT markers_json FROM {self._db._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)}
            WHERE filename = ? AND sleep_date = ?
            """,
            (filename, date_str),
        )

        if row is None:
            return None

        # Deserialize using json.loads (NOT eval)
        from sleep_scoring_app.core.dataclasses_markers import DailyNonwearMarkers

        data = json.loads(row[0])
        markers = DailyNonwearMarkers.from_dict(data)
        self._cache[cache_key] = markers
        return markers

    def load_adjacent_day_markers(
        self,
        filename: str,
        available_dates: list[str],
        current_date_index: int,
    ) -> list[dict]:
        """
        Load sleep markers from adjacent days for display.

        This is a headless service method - no Qt dependencies.
        Returns marker data in dict format suitable for plot display.

        Args:
            filename: File identifier
            available_dates: List of date strings (ISO format)
            current_date_index: Index of current date in available_dates

        Returns:
            List of marker dicts with onset_datetime, offset_datetime, adjacent_date, is_adjacent_day

        """
        if not available_dates or current_date_index < 0 or current_date_index >= len(available_dates):
            return []

        adjacent_markers: list[dict] = []

        # Load from previous day
        if current_date_index > 0:
            prev_date_str = available_dates[current_date_index - 1]
            prev_markers = self._load_markers_as_dicts(filename, prev_date_str)
            for marker in prev_markers:
                marker["adjacent_date"] = prev_date_str
                marker["is_adjacent_day"] = True
            adjacent_markers.extend(prev_markers)

        # Load from next day
        if current_date_index < len(available_dates) - 1:
            next_date_str = available_dates[current_date_index + 1]
            next_markers = self._load_markers_as_dicts(filename, next_date_str)
            for marker in next_markers:
                marker["adjacent_date"] = next_date_str
                marker["is_adjacent_day"] = True
            adjacent_markers.extend(next_markers)

        return adjacent_markers

    def _load_markers_as_dicts(self, filename: str, date_str: str) -> list[dict]:
        """Load markers for a date and convert to display dicts."""
        markers = self.load(filename, date_str)
        if not markers:
            return []

        result = []
        for period in markers.get_complete_periods():
            if period.onset_timestamp and period.offset_timestamp:
                result.append(
                    {
                        "onset_datetime": period.onset_timestamp,
                        "offset_datetime": period.offset_timestamp,
                    }
                )
        return result

    # ==================== Coordination ====================

    def get_marker_status(self, filename: str, sleep_date: date | str) -> MarkerStatus:
        """
        Get status of markers for a file/date.

        Args:
            filename: File identifier
            sleep_date: Sleep date (date or ISO string)

        Returns:
            MarkerStatus with counts and flags

        """
        sleep = self.load(filename, sleep_date)
        nonwear = self.load_nonwear(filename, sleep_date)

        sleep_periods = len(sleep.get_complete_periods()) if sleep else 0
        nonwear_periods = len(nonwear.get_complete_periods()) if nonwear else 0

        return MarkerStatus(
            has_sleep_markers=sleep is not None and sleep_periods > 0,
            has_nonwear_markers=nonwear is not None and nonwear_periods > 0,
            sleep_periods_count=sleep_periods,
            nonwear_periods_count=nonwear_periods,
            is_complete=sleep_periods > 0,
        )

    def get_all_marker_statuses(self, filename: str) -> dict[date, MarkerStatus]:
        """
        Get marker status for all dates of a file.

        Args:
            filename: File identifier

        Returns:
            Dictionary mapping dates to MarkerStatus

        """
        rows = self._db.fetch_all(
            f"""
            SELECT DISTINCT analysis_date FROM {self._db._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)}
            WHERE filename = ?
            UNION
            SELECT DISTINCT sleep_date FROM {self._db._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)}
            WHERE filename = ?
            """,
            (filename, filename),
        )

        result: dict[date, MarkerStatus] = {}
        for row in rows:
            d = date.fromisoformat(row[0])
            result[d] = self.get_marker_status(filename, d)

        return result

    def add_sleep_period(self, sleep_metrics: SleepMetrics, onset_timestamp: float, offset_timestamp: float) -> tuple[bool, str]:
        """
        Add a new sleep period to the daily markers.

        Args:
            sleep_metrics: Sleep metrics containing daily markers
            onset_timestamp: Period onset timestamp
            offset_timestamp: Period offset timestamp

        Returns:
            Tuple of (success, message)

        """
        try:
            from sleep_scoring_app.core.dataclasses import SleepPeriod

            # Create new sleep period
            new_period = SleepPeriod(
                onset_timestamp=onset_timestamp,
                offset_timestamp=offset_timestamp,
            )

            # Validate addition
            is_valid, error_msg = self.validate_marker_addition(sleep_metrics.daily_sleep_markers, new_period)

            if not is_valid:
                return False, error_msg

            # Find next available slot
            slot = self.get_next_available_slot(sleep_metrics.daily_sleep_markers)
            if slot is None:
                return False, "No available slots for new sleep period"

            # Add to appropriate slot
            new_period.marker_index = slot
            if slot == 1:
                sleep_metrics.daily_sleep_markers.period_1 = new_period
            elif slot == 2:
                sleep_metrics.daily_sleep_markers.period_2 = new_period
            elif slot == 3:
                sleep_metrics.daily_sleep_markers.period_3 = new_period
            elif slot == 4:
                sleep_metrics.daily_sleep_markers.period_4 = new_period

            # Update classifications
            self.update_classifications(sleep_metrics.daily_sleep_markers)

            # Check for duration ties
            has_tie, tie_msg = self.validate_duration_tie(sleep_metrics.daily_sleep_markers)
            if has_tie:
                # Remove the just-added period
                self.handle_duration_tie_cancellation(sleep_metrics.daily_sleep_markers, slot)
                return False, tie_msg

            return True, f"Added sleep period {slot}"

        except Exception:
            logger.exception("Error adding sleep period")
            return False, "Failed to add sleep period"

    def remove_sleep_period(self, sleep_metrics: SleepMetrics, period_index: int) -> tuple[bool, str]:
        """
        Remove a sleep period by index.

        Args:
            sleep_metrics: Sleep metrics containing daily markers
            period_index: Period index (1, 2, 3, or 4)

        Returns:
            Tuple of (success, message)

        """
        try:
            daily_markers = sleep_metrics.daily_sleep_markers

            # Remove the specified period
            if period_index == 1 and daily_markers.period_1 is not None:
                daily_markers.period_1 = None
            elif period_index == 2 and daily_markers.period_2 is not None:
                daily_markers.period_2 = None
            elif period_index == 3 and daily_markers.period_3 is not None:
                daily_markers.period_3 = None
            elif period_index == 4 and daily_markers.period_4 is not None:
                daily_markers.period_4 = None
            else:
                return False, f"No sleep period found at index {period_index}"

            # Update classifications for remaining periods
            self.update_classifications(daily_markers)

            return True, f"Removed sleep period {period_index}"

        except Exception:
            logger.exception("Error removing sleep period %d", period_index)
            return False, "Failed to remove sleep period"

    def get_next_available_slot(self, daily_markers: DailySleepMarkers) -> int | None:
        """
        Get the next available period slot (1, 2, 3, or 4).

        Args:
            daily_markers: Daily markers to check

        Returns:
            Next available slot number or None if all full

        """
        if daily_markers.period_1 is None:
            return 1
        if daily_markers.period_2 is None:
            return 2
        if daily_markers.period_3 is None:
            return 3
        if daily_markers.period_4 is None:
            return 4
        return None

    # ==================== Cache ====================

    def _make_cache_key(self, filename: str, sleep_date: str, marker_type: str) -> str:
        """Create cache key from filename, date, and marker type."""
        return f"{filename}:{sleep_date}:{marker_type}"

    def _invalidate_cache_key(self, filename: str, sleep_date: str, marker_type: str) -> None:
        """Invalidate a specific cache entry."""
        key = self._make_cache_key(filename, sleep_date, marker_type)
        self._cache.pop(key, None)

    def invalidate_cache(self, filename: str, sleep_date: date | str | None = None) -> None:
        """
        Invalidate cache for a file, optionally for a specific date.

        Args:
            filename: File identifier
            sleep_date: Optional specific date to invalidate

        """
        if sleep_date:
            date_str = sleep_date.isoformat() if isinstance(sleep_date, date) else sleep_date
            self._invalidate_cache_key(filename, date_str, "sleep")
            self._invalidate_cache_key(filename, date_str, "nonwear")
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{filename}:")]
            for key in keys_to_remove:
                del self._cache[key]

    def clear_cache(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
        logger.debug("Cleared marker cache")
