"""
Sleep onset and offset rule application - Framework-agnostic implementation.

This module implements the research-grade rules for identifying precise sleep onset
and offset times based on consecutive sleep minutes detected by sleep scoring algorithms.

Algorithm Details:
    - Onset Rule: FIRST occurrence of N consecutive sleep minutes (default: 3)
    - Offset Rule: LAST minute of M consecutive sleep minutes before wake (default: 5)
    - Search Extension: Rules search ±K minutes from user markers (default: 5)
    - Priority: Always selects FIRST onset and LAST offset occurrence

This class implements the OnsetOffsetRule protocol for dependency injection.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from sleep_scoring_app.core.algorithms.config import SleepRulesConfig

logger = logging.getLogger(__name__)


class SleepRules:
    """
    Consecutive N-minute onset/offset detection rules - Protocol implementation.

    This class implements the OnsetOffsetRule protocol for dependency injection,
    applying validated sleep research rules to identify precise sleep onset
    and offset times from sleep scoring algorithm results.

    Rules:
        - Onset: FIRST occurrence of N consecutive sleep minutes
        - Offset: LAST minute of M consecutive sleep minutes before wake
        - Search Extension: ±K minutes from user markers

    This is the original implementation used in the application and serves as
    the default rule set.

    Example usage:
        ```python
        from sleep_scoring_app.core.algorithms import SleepRules, SleepRulesConfig

        # Prepare data
        sleep_scores = [0, 0, 1, 1, 1, ...]  # Sleep/wake scores (1=sleep, 0=wake)
        sleep_start_marker = datetime(2024, 1, 1, 22, 0)  # User marker
        sleep_end_marker = datetime(2024, 1, 2, 7, 0)    # User marker
        timestamps = [...]  # Corresponding timestamps

        # Apply rules
        rules = SleepRules(config=SleepRulesConfig())
        onset_idx, offset_idx = rules.apply_rules(
            sleep_scores=sleep_scores,
            sleep_start_marker=sleep_start_marker,
            sleep_end_marker=sleep_end_marker,
            timestamps=timestamps
        )
        ```
    """

    def __init__(self, config: SleepRulesConfig | None = None) -> None:
        """
        Initialize sleep rules with optional configuration.

        Args:
            config: Rules configuration (uses defaults if None)

        """
        from sleep_scoring_app.core.algorithms.config import SleepRulesConfig

        self.config = config or SleepRulesConfig()

    # === Protocol Properties ===

    @property
    def name(self) -> str:
        """Human-readable rule name."""
        return f"Consecutive {self.config.onset_consecutive_minutes}/{self.config.offset_consecutive_minutes} Minutes"

    @property
    def identifier(self) -> str:
        """Unique identifier for storage."""
        return f"consecutive_{self.config.onset_consecutive_minutes}_{self.config.offset_consecutive_minutes}"

    @property
    def description(self) -> str:
        """Brief description of rule logic."""
        return (
            f"Onset: First {self.config.onset_consecutive_minutes} consecutive S (Sleep) epochs. "
            f"Offset: Last S epoch of {self.config.offset_consecutive_minutes} consecutive S epochs before W (Wake). "
            f"Search extension: ±{self.config.search_extension_minutes} minutes."
        )

    # === Protocol Methods ===

    def get_parameters(self) -> dict[str, Any]:
        """Get current rule parameters."""
        return {
            "onset_consecutive_minutes": self.config.onset_consecutive_minutes,
            "offset_consecutive_minutes": self.config.offset_consecutive_minutes,
            "search_extension_minutes": self.config.search_extension_minutes,
            "require_wake_after_offset": self.config.require_wake_after_offset,
        }

    def set_parameters(self, **kwargs: Any) -> None:
        """
        Update rule parameters.

        Note: SleepRulesConfig is frozen, so this creates a new config instance.

        Args:
            **kwargs: Parameter name-value pairs

        Raises:
            ValueError: If parameter name is invalid
        """
        # Only accept valid parameters
        valid_params = {
            "onset_consecutive_minutes",
            "offset_consecutive_minutes",
            "search_extension_minutes",
            "require_wake_after_offset",
        }
        invalid_params = set(kwargs.keys()) - valid_params
        if invalid_params:
            msg = f"Invalid parameters: {invalid_params}. Valid: {valid_params}"
            raise ValueError(msg)

        # Create new config with updated values
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
        onset_label = f"Sleep Onset at {onset_time}\n{self.config.onset_consecutive_minutes} consecutive S epochs"
        offset_label = f"Sleep Offset at {offset_time}\n{self.config.offset_consecutive_minutes} consecutive S before W"
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
        Apply sleep onset and offset rules to identify precise sleep times.

        This method searches for the FIRST occurrence of consecutive sleep minutes
        for onset and the LAST occurrence for offset, within an extended search
        window around the user-provided markers.

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

        # Find sleep offset: LAST minute of M consecutive sleep minutes before wake
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

        # Find ALL instances of N consecutive sleep minutes, then choose the FIRST one
        sleep_onset_candidates = []

        # Ensure we don't go beyond available data - need space for consecutive minutes
        safe_end = min(extended_end, len(sleep_scores) - self.config.onset_consecutive_minutes)

        for i in range(extended_start, safe_end + 1):
            # Check if we have N consecutive sleep minutes starting at position i
            if all(sleep_scores[i + offset] == 1 for offset in range(self.config.onset_consecutive_minutes)):
                sleep_onset_candidates.append(i)

        # Filter to unique values only
        sleep_onset_candidates = list(set(sleep_onset_candidates))

        # Choose the FIRST occurrence (earliest time)
        if sleep_onset_candidates:
            return min(sleep_onset_candidates)

        return None

    def _find_sleep_offset(
        self,
        sleep_scores: list[int],
        start_idx: int,
        end_idx: int,
        onset_idx: int,
    ) -> int | None:
        """
        Find sleep offset: LAST minute of M consecutive sleep minutes before wake.

        Args:
            sleep_scores: List of sleep/wake classifications
            start_idx: Starting index from sleep start marker
            end_idx: Ending index from sleep end marker
            onset_idx: Index of identified sleep onset

        Returns:
            Index of sleep offset, or None if not found

        """
        # Extend search by configured minutes
        extended_start = max(0, start_idx - self.config.search_extension_minutes)
        extended_end = min(len(sleep_scores) - 1, end_idx + self.config.search_extension_minutes)

        # Search for patterns of N consecutive sleep minutes followed by wake
        sleep_offset_candidates = []

        # Ensure we can check the full pattern including the wake minute if required
        consecutive_check = self.config.offset_consecutive_minutes
        if self.config.require_wake_after_offset:
            # Need space for N sleep minutes + 1 wake minute
            safe_end = min(extended_end, len(sleep_scores) - (consecutive_check + 1))
        else:
            # Just need space for N sleep minutes
            safe_end = min(extended_end, len(sleep_scores) - consecutive_check)

        # Start search from a safe position that allows for N minutes of history
        safe_start = max(onset_idx + consecutive_check, consecutive_check)

        for i in range(safe_start, safe_end + 1):
            # Check for N consecutive sleep minutes
            consecutive_sleep = all(sleep_scores[i + offset] == 1 for offset in range(consecutive_check))

            if not consecutive_sleep:
                continue

            # Check if followed by wake (if required)
            if self.config.require_wake_after_offset:
                if i + consecutive_check < len(sleep_scores):
                    followed_by_wake = sleep_scores[i + consecutive_check] == 0
                    if not followed_by_wake:
                        continue
                else:
                    # Can't verify wake after, skip this candidate
                    continue

            # This is a valid N-minute sleep period (possibly followed by wake)
            # The offset is the LAST minute of these N sleep minutes
            candidate_idx = i + (consecutive_check - 1)
            sleep_offset_candidates.append(candidate_idx)

        # Choose the LAST occurrence (latest time)
        if sleep_offset_candidates:
            return max(sleep_offset_candidates)

        return None


def find_sleep_onset_offset(
    sleep_scores: list[int],
    sleep_start_marker: datetime,
    sleep_end_marker: datetime,
    timestamps: list[datetime],
    config: SleepRulesConfig | None = None,
) -> tuple[int | None, int | None]:
    """
    Convenience function to apply sleep onset/offset rules.

    Args:
        sleep_scores: List of sleep/wake classifications (1=sleep, 0=wake)
        sleep_start_marker: User-provided approximate sleep start time
        sleep_end_marker: User-provided approximate sleep end time
        timestamps: List of timestamps corresponding to sleep_scores
        config: Optional rules configuration

    Returns:
        Tuple of (onset_index, offset_index), or (None, None) if not found

    """
    rules = SleepRules(config=config)
    return rules.apply_rules(sleep_scores, sleep_start_marker, sleep_end_marker, timestamps)
