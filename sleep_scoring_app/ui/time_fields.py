#!/usr/bin/env python3
"""
Time Field Manager for Sleep Scoring Application.

Manages manual time entry fields for sleep onset/offset markers.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

logger = logging.getLogger(__name__)


class TimeFieldManager:
    """
    Manages manual time entry fields for sleep markers.

    Responsibilities:
    - Handle manual time input from onset/offset fields
    - Parse and validate time strings
    - Update plot markers from time input
    - Prevent infinite update loops
    - Handle overnight sleep periods
    """

    def __init__(self, parent: SleepScoringMainWindow) -> None:
        """
        Initialize the time field manager.

        Args:
            parent: Reference to main window for field and plot access

        """
        self.parent = parent
        logger.info("TimeFieldManager initialized")

    def set_manual_sleep_times(self) -> None:
        """Set sleep markers manually based on time input with loop prevention and validation."""
        # Check if we're already updating from markers to prevent loops
        if getattr(self.parent, "_updating_from_markers", False):
            logger.debug("Skipping marker update - currently updating from markers to prevent loop")
            return

        onset_text = self.parent.onset_time_input.text().strip()
        offset_text = self.parent.offset_time_input.text().strip()

        # Allow partial updates - if only one field has changed
        if not onset_text and not offset_text:
            return

        # Set flag to prevent recursive updates
        self.parent._updating_from_fields = True
        try:
            # Validate and parse time inputs
            onset_timestamp = None
            offset_timestamp = None

            # Get current date
            if not self.parent.available_dates:
                return

            current_date = self.parent.available_dates[self.parent.current_date_index]

            # Parse onset time if provided
            if onset_text:
                onset_timestamp = self.parent._parse_time_to_timestamp(onset_text, current_date)
                if onset_timestamp is None:
                    logger.warning("Invalid onset time format: %s", onset_text)
                    # Reset field to previous valid value if marker exists
                    self.parent._restore_field_from_marker("onset")
                    return

            # Parse offset time if provided
            if offset_text:
                offset_timestamp = self.parent._parse_time_to_timestamp(offset_text, current_date)
                if offset_timestamp is None:
                    logger.warning("Invalid offset time format: %s", offset_text)
                    # Reset field to previous valid value if marker exists
                    self.parent._restore_field_from_marker("offset")
                    return

            # Handle different update scenarios based on what's provided
            if onset_timestamp and offset_timestamp:
                # Both times provided - full update
                # Handle overnight sleep (offset in next day)
                if offset_timestamp <= onset_timestamp:
                    offset_dt = datetime.fromtimestamp(offset_timestamp)
                    offset_dt += timedelta(days=1)
                    offset_timestamp = offset_dt.timestamp()

                # Update the selected sleep period or create new one
                self.parent._update_selected_sleep_period(onset_timestamp, offset_timestamp)

            elif onset_timestamp and not offset_text:
                # Only onset provided and offset is empty - start new period
                self.parent._update_selected_sleep_period_onset(onset_timestamp)

            elif offset_timestamp and not onset_text:
                # Only offset provided and onset is empty - shouldn't happen normally
                logger.warning("Offset time provided without onset - ignoring")
                return

            elif onset_timestamp:
                # Onset provided, check if we should update existing period
                selected_period = (
                    self.parent.plot_widget.get_selected_marker_period() if hasattr(self.parent.plot_widget, "get_selected_marker_period") else None
                )
                if selected_period and selected_period.offset_timestamp:
                    # Update only the onset of existing complete period
                    self.parent._update_selected_sleep_period(onset_timestamp, selected_period.offset_timestamp)
                else:
                    # Start new period with just onset
                    self.parent._update_selected_sleep_period_onset(onset_timestamp)

            elif offset_timestamp:
                # Offset provided, check if we have an incomplete period
                selected_period = (
                    self.parent.plot_widget.get_selected_marker_period() if hasattr(self.parent.plot_widget, "get_selected_marker_period") else None
                )
                if selected_period and selected_period.onset_timestamp and not selected_period.offset_timestamp:
                    # Complete the incomplete period
                    self.parent._update_selected_sleep_period(selected_period.onset_timestamp, offset_timestamp)

        except Exception as e:
            logger.exception("Error setting manual sleep times: %s", e)
        finally:
            # Always clear the flag
            self.parent._updating_from_fields = False
