#!/usr/bin/env python3
"""
Marker Service for Sleep Scoring Application
Handles validation, classification, and management of sleep markers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sleep_scoring_app.core.constants import MarkerLimits
from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import SleepMetrics

logger = logging.getLogger(__name__)


class MarkerValidationService:
    """Service for validating sleep marker operations."""

    @staticmethod
    def validate_marker_addition(daily_markers: DailySleepMarkers, new_period: SleepPeriod) -> tuple[bool, str]:
        """
        Validate if a new sleep period can be added.

        Returns:
            tuple[bool, str]: (is_valid, error_message)

        """
        # Check if we have space for new period
        if not daily_markers.has_space_for_new_period():
            return False, f"Maximum {MarkerLimits.MAX_SLEEP_PERIODS_PER_DAY} sleep periods per day allowed"

        # Check for overlaps with existing periods
        if new_period.is_complete:
            for existing_period in daily_markers.get_complete_periods():
                if MarkerValidationService._periods_overlap(new_period, existing_period):
                    return False, "Sleep periods cannot overlap"

        return True, ""

    @staticmethod
    def validate_duration_tie(daily_markers: DailySleepMarkers) -> tuple[bool, str]:
        """
        Check for duration ties and return validation result.

        Returns:
            tuple[bool, str]: (has_tie, message)

        """
        if daily_markers.check_duration_tie():
            return True, "Cannot determine main sleep: multiple periods with identical duration"
        return False, ""

    @staticmethod
    def _periods_overlap(period1: SleepPeriod, period2: SleepPeriod) -> bool:
        """Check if two sleep periods overlap in time."""
        if not (period1.is_complete and period2.is_complete):
            return False

        # Check for any time overlap
        return period1.onset_timestamp < period2.offset_timestamp and period2.onset_timestamp < period1.offset_timestamp

    @staticmethod
    def get_next_available_slot(daily_markers: DailySleepMarkers) -> int | None:
        """Get the next available period slot (1, 2, 3, or 4)."""
        if daily_markers.period_1 is None:
            return 1
        if daily_markers.period_2 is None:
            return 2
        if daily_markers.period_3 is None:
            return 3
        if daily_markers.period_4 is None:
            return 4
        return None


class MarkerClassificationService:
    """Service for classifying markers as main sleep vs naps."""

    @staticmethod
    def update_classifications(daily_markers: DailySleepMarkers) -> None:
        """Update all marker classifications based on current durations."""
        daily_markers.update_classifications()
        logger.debug("Updated marker classifications")

    @staticmethod
    def handle_duration_tie_cancellation(daily_markers: DailySleepMarkers, last_added_index: int) -> bool:
        """
        Handle duration tie by removing the last added period.

        Args:
            daily_markers: The daily markers collection
            last_added_index: Index of the last added period (1, 2, 3, or 4)

        Returns:
            bool: True if successfully handled, False otherwise

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
            MarkerClassificationService.update_classifications(daily_markers)
            logger.info("Removed period %d due to duration tie", last_added_index)
            return True

        except Exception:
            logger.exception("Failed to handle duration tie cancellation")
            return False


class MarkerPersistenceService:
    """Service for managing marker persistence operations."""

    def __init__(self, database_manager) -> None:
        """Initialize with database manager dependency."""
        self.db_manager = database_manager

    def save_markers(self, sleep_metrics: SleepMetrics) -> bool:
        """Save sleep markers to database."""
        try:
            # Update time strings from main sleep period
            sleep_metrics.update_time_strings()

            # Save to extended markers table
            success = self.db_manager.save_daily_sleep_markers(sleep_metrics)

            if success:
                logger.debug("Successfully saved markers for %s on %s", sleep_metrics.filename, sleep_metrics.analysis_date)
            else:
                logger.warning("Failed to save markers for %s on %s", sleep_metrics.filename, sleep_metrics.analysis_date)

            return success

        except Exception:
            logger.exception("Error saving markers for %s on %s", sleep_metrics.filename, sleep_metrics.analysis_date)
            return False

    def load_markers(self, filename: str, analysis_date: str) -> DailySleepMarkers:
        """Load sleep markers from database."""
        try:
            daily_markers = self.db_manager.load_daily_sleep_markers(filename, analysis_date)
            logger.debug("Loaded markers for %s on %s", filename, analysis_date)
            return daily_markers

        except Exception:
            logger.exception("Error loading markers for %s on %s", filename, analysis_date)
            return DailySleepMarkers()


class MarkerCoordinationService:
    """Service for coordinating marker operations across UI and persistence layers."""

    def __init__(self, database_manager) -> None:
        """Initialize with database manager dependency."""
        self.persistence_service = MarkerPersistenceService(database_manager)

    def add_sleep_period(self, sleep_metrics: SleepMetrics, onset_timestamp: float, offset_timestamp: float) -> tuple[bool, str]:
        """
        Add a new sleep period to the daily markers.

        Returns:
            tuple[bool, str]: (success, message)

        """
        try:
            # Create new sleep period
            new_period = SleepPeriod(
                onset_timestamp=onset_timestamp,
                offset_timestamp=offset_timestamp,
            )

            # Validate addition
            is_valid, error_msg = MarkerValidationService.validate_marker_addition(sleep_metrics.daily_sleep_markers, new_period)

            if not is_valid:
                return False, error_msg

            # Find next available slot
            slot = MarkerValidationService.get_next_available_slot(sleep_metrics.daily_sleep_markers)
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
            MarkerClassificationService.update_classifications(sleep_metrics.daily_sleep_markers)

            # Check for duration ties
            has_tie, tie_msg = MarkerValidationService.validate_duration_tie(sleep_metrics.daily_sleep_markers)
            if has_tie:
                # Remove the just-added period
                MarkerClassificationService.handle_duration_tie_cancellation(sleep_metrics.daily_sleep_markers, slot)
                return False, tie_msg

            return True, f"Added sleep period {slot}"

        except Exception:
            logger.exception("Error adding sleep period")
            return False, "Failed to add sleep period"

    def remove_sleep_period(self, sleep_metrics: SleepMetrics, period_index: int) -> tuple[bool, str]:
        """
        Remove a sleep period by index.

        Args:
            sleep_metrics: The sleep metrics containing daily markers
            period_index: Period index (1, 2, 3, or 4)

        Returns:
            tuple[bool, str]: (success, message)

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
            MarkerClassificationService.update_classifications(daily_markers)

            return True, f"Removed sleep period {period_index}"

        except Exception:
            logger.exception("Error removing sleep period %d", period_index)
            return False, "Failed to remove sleep period"

    def save_and_persist(self, sleep_metrics: SleepMetrics) -> tuple[bool, str]:
        """Save markers and persist to database."""
        try:
            success = self.persistence_service.save_markers(sleep_metrics)
            if success:
                return True, "Markers saved successfully"
            return False, "Failed to save markers to database"

        except Exception:
            logger.exception("Error in save_and_persist")
            return False, "Error occurred while saving markers"
