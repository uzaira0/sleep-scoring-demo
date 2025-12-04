"""
Tudor-Locke (2014) sleep onset/offset detection rules - Framework-agnostic implementation.

This module implements the Tudor-Locke algorithm for detecting sleep periods from
actigraphy data that has already been scored by a sleep/wake classification algorithm
(e.g., Sadeh or Cole-Kripke).

References:
    Tudor-Locke, C., Barreira, T. V., Schuna Jr, J. M., Mire, E. F., Chaput, J. P.,
    Fogelholm, M., ... & Katzmarzyk, P. T. (2014). Improving wear time compliance
    with a 24-hour waist-worn accelerometer protocol in the International Study of
    Childhood Obesity, Lifestyle and the Environment (ISCOLE). International Journal
    of Behavioral Nutrition and Physical Activity, 11(1), 1-9.

Algorithm Details:
    - Onset (Bedtime): FIRST occurrence of N consecutive sleep minutes (default: 5)
    - Offset (Wake Time): FIRST occurrence of M consecutive wake minutes after sleep (default: 10)
    - Minimum Sleep Period: 160 minutes (optional validation)
    - Maximum Sleep Period: 1440 minutes (24 hours, optional validation)

Key Difference from Consecutive N/M Rules:
    - Tudor-Locke finds offset by looking for consecutive WAKE minutes
    - The standard consecutive rules find offset by looking for consecutive SLEEP minutes followed by wake
    - Tudor-Locke offset is the LAST sleep minute before the consecutive wake period begins

This class implements the OnsetOffsetRule protocol for dependency injection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TudorLockeConfig:
    """
    Configuration for Tudor-Locke onset/offset detection rules.

    Attributes:
        onset_consecutive_minutes: Consecutive sleep minutes for onset detection (default: 5)
        offset_consecutive_wake_minutes: Consecutive wake minutes for offset detection (default: 10)
        search_extension_minutes: Minutes to extend search window (default: 5)
        min_sleep_period_minutes: Minimum valid sleep period length (default: 160)
        max_sleep_period_minutes: Maximum valid sleep period length (default: 1440)

    """

    onset_consecutive_minutes: int = 5
    offset_consecutive_wake_minutes: int = 10
    search_extension_minutes: int = 5
    min_sleep_period_minutes: int = 160
    max_sleep_period_minutes: int = 1440


class TudorLockeRule:
    """
    Tudor-Locke (2014) sleep onset/offset detection rules - Protocol implementation.

    This class implements the OnsetOffsetRule protocol for dependency injection,
    applying the Tudor-Locke algorithm for detecting sleep periods from sleep/wake
    classification data.

    Key Algorithm Details:
        - Onset: First occurrence of N consecutive sleep minutes (default: 5)
        - Offset: Last sleep minute BEFORE M consecutive wake minutes (default: 10)

    The main difference from the standard consecutive rules is how offset is detected:
        - Standard: Looks for N consecutive sleep minutes followed by wake
        - Tudor-Locke: Looks for M consecutive wake minutes, offset is just before

    Example usage:
        ```python
        from sleep_scoring_app.core.algorithms import TudorLockeRule, TudorLockeConfig

        # Prepare data
        sleep_scores = [0, 0, 1, 1, 1, 1, 1, 1, ...]  # Sleep/wake scores (1=sleep, 0=wake)
        sleep_start_marker = datetime(2024, 1, 1, 22, 0)  # User marker
        sleep_end_marker = datetime(2024, 1, 2, 7, 0)    # User marker
        timestamps = [...]  # Corresponding timestamps

        # Apply rules
        rules = TudorLockeRule()
        onset_idx, offset_idx = rules.apply_rules(
            sleep_scores=sleep_scores,
            sleep_start_marker=sleep_start_marker,
            sleep_end_marker=sleep_end_marker,
            timestamps=timestamps
        )
        ```

    References:
        Tudor-Locke, C., et al. (2014). Fully automated waist-worn accelerometer
        algorithm for detecting children's sleep-period time separate from 24-h
        physical activity or sedentary behaviors. Applied Physiology, Nutrition,
        and Metabolism, 39(1), 53-57.

    """

    def __init__(self, config: TudorLockeConfig | None = None) -> None:
        """
        Initialize Tudor-Locke rules with optional configuration.

        Args:
            config: Rules configuration (uses defaults if None)

        """
        self.config = config or TudorLockeConfig()

    # === Protocol Properties ===

    @property
    def name(self) -> str:
        """Human-readable rule name."""
        return f"Tudor-Locke ({self.config.onset_consecutive_minutes}/{self.config.offset_consecutive_wake_minutes})"

    @property
    def identifier(self) -> str:
        """Unique identifier for storage."""
        return "tudor_locke_2014"

    @property
    def description(self) -> str:
        """Brief description of rule logic."""
        return (
            f"Onset: First {self.config.onset_consecutive_minutes} consecutive S (Sleep) epochs. "
            f"Offset: Last S epoch before {self.config.offset_consecutive_wake_minutes} consecutive W (Wake) epochs. "
            f"Search extension: ±{self.config.search_extension_minutes} minutes."
        )

    # === Protocol Methods ===

    def get_parameters(self) -> dict[str, Any]:
        """Get current rule parameters."""
        return {
            "onset_consecutive_minutes": self.config.onset_consecutive_minutes,
            "offset_consecutive_wake_minutes": self.config.offset_consecutive_wake_minutes,
            "search_extension_minutes": self.config.search_extension_minutes,
            "min_sleep_period_minutes": self.config.min_sleep_period_minutes,
            "max_sleep_period_minutes": self.config.max_sleep_period_minutes,
        }

    def set_parameters(self, **kwargs: Any) -> None:
        """
        Update rule parameters.

        Note: TudorLockeConfig is frozen, so this creates a new config instance.

        Args:
            **kwargs: Parameter name-value pairs

        Raises:
            ValueError: If parameter name is invalid
        """
        valid_params = {
            "onset_consecutive_minutes",
            "offset_consecutive_wake_minutes",
            "search_extension_minutes",
            "min_sleep_period_minutes",
            "max_sleep_period_minutes",
        }
        invalid_params = set(kwargs.keys()) - valid_params
        if invalid_params:
            msg = f"Invalid parameters: {invalid_params}. Valid: {valid_params}"
            raise ValueError(msg)

        self.config = replace(self.config, **kwargs)

    def get_marker_labels(self, onset_time: str, offset_time: str) -> tuple[str, str]:
        """
        Get UI marker label text.

        Args:
            onset_time: Onset time in HH:MM format
            offset_time: Offset time in HH:MM format

        Returns:
            Tuple of (onset_label, offset_label) for display in UI
        """
        onset_label = f"Sleep Onset at {onset_time}\nTudor-Locke: {self.config.onset_consecutive_minutes} consecutive S"
        offset_label = f"Sleep Offset at {offset_time}\nTudor-Locke: {self.config.offset_consecutive_wake_minutes} consecutive W"
        return onset_label, offset_label

    # === Core Rule Application ===

    def apply_rules(
        self,
        sleep_scores: list[int],
        sleep_start_marker: datetime,
        sleep_end_marker: datetime,
        timestamps: list[datetime],
    ) -> tuple[int | None, int | None]:
        """
        Apply Tudor-Locke sleep onset and offset rules.

        This method searches for:
        - Onset: FIRST occurrence of N consecutive sleep minutes
        - Offset: LAST sleep minute before M consecutive wake minutes

        Args:
            sleep_scores: List of sleep/wake classifications (1=sleep, 0=wake)
            sleep_start_marker: User-provided approximate sleep start time
            sleep_end_marker: User-provided approximate sleep end time
            timestamps: List of timestamps corresponding to sleep_scores

        Returns:
            Tuple of (onset_index, offset_index), or (None, None) if not found

        """
        if not sleep_scores or len(sleep_scores) == 0:
            return None, None

        # Find corresponding indices for markers in the data
        start_idx = None
        end_idx = None

        for i, timestamp in enumerate(timestamps):
            if start_idx is None and timestamp >= sleep_start_marker:
                start_idx = i
            if timestamp <= sleep_end_marker:
                end_idx = i

        if start_idx is None or end_idx is None:
            return None, None

        # Find sleep onset: FIRST occurrence of N consecutive sleep minutes
        sleep_onset_idx = self._find_sleep_onset(
            sleep_scores=sleep_scores,
            start_idx=start_idx,
            end_idx=end_idx,
        )

        # Find sleep offset: Last sleep minute before M consecutive wake minutes
        sleep_offset_idx = None
        if sleep_onset_idx is not None:
            sleep_offset_idx = self._find_sleep_offset(
                sleep_scores=sleep_scores,
                start_idx=start_idx,
                end_idx=end_idx,
                onset_idx=sleep_onset_idx,
            )

        return sleep_onset_idx, sleep_offset_idx

    def _find_sleep_onset(
        self,
        sleep_scores: list[int],
        start_idx: int,
        end_idx: int,
    ) -> int | None:
        """
        Find sleep onset: FIRST occurrence of N consecutive sleep minutes.

        This is the same logic as the standard consecutive rules.

        Args:
            sleep_scores: List of sleep/wake classifications
            start_idx: Starting index from sleep start marker
            end_idx: Ending index from sleep end marker

        Returns:
            Index of sleep onset, or None if not found

        """
        # Extend search by configured minutes
        extended_start = max(0, start_idx - self.config.search_extension_minutes)
        extended_end = min(len(sleep_scores) - 1, end_idx + self.config.search_extension_minutes)

        # Find FIRST instance of N consecutive sleep minutes
        consecutive_required = self.config.onset_consecutive_minutes
        safe_end = min(extended_end, len(sleep_scores) - consecutive_required)

        for i in range(extended_start, safe_end + 1):
            if all(sleep_scores[i + offset] == 1 for offset in range(consecutive_required)):
                return i

        return None

    def _find_sleep_offset(
        self,
        sleep_scores: list[int],
        start_idx: int,
        end_idx: int,
        onset_idx: int,
    ) -> int | None:
        """
        Find sleep offset: Last sleep minute BEFORE M consecutive wake minutes.

        This is the key difference from the standard consecutive rules:
        - Standard: Looks for N consecutive sleep, offset is last sleep minute
        - Tudor-Locke: Looks for M consecutive wake, offset is minute BEFORE wake begins

        Args:
            sleep_scores: List of sleep/wake classifications
            start_idx: Starting index from sleep start marker
            end_idx: Ending index from sleep end marker
            onset_idx: Index of identified sleep onset

        Returns:
            Index of sleep offset, or None if not found

        """
        # Extend search by configured minutes
        extended_end = min(len(sleep_scores) - 1, end_idx + self.config.search_extension_minutes)

        # Search for M consecutive wake minutes AFTER the onset
        consecutive_wake_required = self.config.offset_consecutive_wake_minutes

        # Start searching after onset
        search_start = onset_idx + self.config.onset_consecutive_minutes

        # Need room for M consecutive wake minutes
        safe_end = min(extended_end, len(sleep_scores) - consecutive_wake_required)

        for i in range(search_start, safe_end + 1):
            # Check if we have M consecutive wake minutes starting at position i
            if all(sleep_scores[i + offset] == 0 for offset in range(consecutive_wake_required)):
                # Found consecutive wake period
                # The offset is the minute BEFORE this wake period begins
                # But we need to verify there was sleep before the wake
                if i > onset_idx and sleep_scores[i - 1] == 1:
                    return i - 1

        # If no consecutive wake period found, look for the last sleep minute in the search window
        # This handles edge cases where the data ends during sleep
        last_sleep_idx = None
        for i in range(extended_end, onset_idx, -1):
            if i < len(sleep_scores) and sleep_scores[i] == 1:
                last_sleep_idx = i
                break

        return last_sleep_idx
