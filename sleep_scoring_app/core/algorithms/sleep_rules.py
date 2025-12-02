"""
Sleep onset and offset rule application - Framework-agnostic implementation.

This module implements the research-grade rules for identifying precise sleep onset
and offset times based on consecutive sleep minutes detected by the Sadeh algorithm.

Algorithm Details:
    - Onset Rule: FIRST occurrence of 3 consecutive sleep minutes
    - Offset Rule: LAST minute of 5 consecutive sleep minutes before wake
    - Search Extension: Rules search ±5 minutes from user markers
    - Priority: Always selects FIRST onset and LAST offset occurrence
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from sleep_scoring_app.core.algorithms.config import SleepRulesConfig

logger = logging.getLogger(__name__)


class SleepRules:
    """
    Framework-agnostic implementation of sleep onset and offset rules.

    This class applies validated sleep research rules to identify precise
    sleep onset and offset times from Sadeh algorithm results.

    Example usage:
        ```python
        from sleep_scoring_app.core.algorithms import SleepRules, SleepRulesConfig

        # Prepare data
        sadeh_results = [0, 0, 1, 1, 1, ...]  # Sadeh sleep/wake scores
        sleep_start_marker = datetime(2024, 1, 1, 22, 0)  # User marker
        sleep_end_marker = datetime(2024, 1, 2, 7, 0)    # User marker
        timestamps = [...]  # Corresponding timestamps

        # Apply rules
        rules = SleepRules(config=SleepRulesConfig())
        onset_idx, offset_idx = rules.apply_rules(
            sadeh_results=sadeh_results,
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

    def apply_rules(
        self,
        sadeh_results: list[int],
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
            sadeh_results: List of sleep/wake classifications (1=sleep, 0=wake)
            sleep_start_marker: User-provided approximate sleep start time
            sleep_end_marker: User-provided approximate sleep end time
            timestamps: List of timestamps corresponding to sadeh_results

        Returns:
            Tuple of (onset_index, offset_index), or (None, None) if not found

        """
        if not sadeh_results or len(sadeh_results) == 0:
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

        # Find sleep onset: FIRST occurrence of 3 consecutive sleep minutes
        sleep_onset_idx = self._find_sleep_onset(
            sadeh_results=sadeh_results,
            start_idx=start_idx,
            end_idx=end_idx,
        )

        # Find sleep offset: LAST minute of 5 consecutive sleep minutes before wake
        sleep_offset_idx = None
        if sleep_onset_idx is not None:
            sleep_offset_idx = self._find_sleep_offset(
                sadeh_results=sadeh_results,
                start_idx=start_idx,
                end_idx=end_idx,
                onset_idx=sleep_onset_idx,
            )

        return sleep_onset_idx, sleep_offset_idx

    def _find_sleep_onset(
        self,
        sadeh_results: list[int],
        start_idx: int,
        end_idx: int,
    ) -> int | None:
        """
        Find sleep onset: FIRST occurrence of 3 consecutive sleep minutes.

        Args:
            sadeh_results: List of sleep/wake classifications
            start_idx: Starting index from sleep start marker
            end_idx: Ending index from sleep end marker

        Returns:
            Index of sleep onset, or None if not found

        """
        # Extend search by configured minutes
        extended_start = max(0, start_idx - self.config.search_extension_minutes)
        extended_end = min(len(sadeh_results) - 1, end_idx + self.config.search_extension_minutes)

        # Find ALL instances of N consecutive sleep minutes, then choose the FIRST one
        sleep_onset_candidates = []

        # Ensure we don't go beyond available data - need space for consecutive minutes
        safe_end = min(extended_end, len(sadeh_results) - self.config.onset_consecutive_minutes)

        for i in range(extended_start, safe_end + 1):
            # Check if we have N consecutive sleep minutes starting at position i
            if all(sadeh_results[i + offset] == 1 for offset in range(self.config.onset_consecutive_minutes)):
                sleep_onset_candidates.append(i)

        # Filter to unique values only
        sleep_onset_candidates = list(set(sleep_onset_candidates))

        # Choose the FIRST occurrence (earliest time)
        if sleep_onset_candidates:
            return min(sleep_onset_candidates)

        return None

    def _find_sleep_offset(
        self,
        sadeh_results: list[int],
        start_idx: int,
        end_idx: int,
        onset_idx: int,
    ) -> int | None:
        """
        Find sleep offset: LAST minute of 5 consecutive sleep minutes before wake.

        Args:
            sadeh_results: List of sleep/wake classifications
            start_idx: Starting index from sleep start marker
            end_idx: Ending index from sleep end marker
            onset_idx: Index of identified sleep onset

        Returns:
            Index of sleep offset, or None if not found

        """
        # Extend search by configured minutes
        extended_start = max(0, start_idx - self.config.search_extension_minutes)
        extended_end = min(len(sadeh_results) - 1, end_idx + self.config.search_extension_minutes)

        # Search for patterns of N consecutive sleep minutes followed by wake
        sleep_offset_candidates = []

        # Ensure we can check the full pattern including the wake minute if required
        consecutive_check = self.config.offset_consecutive_minutes
        if self.config.require_wake_after_offset:
            # Need space for N sleep minutes + 1 wake minute
            safe_end = min(extended_end, len(sadeh_results) - (consecutive_check + 1))
        else:
            # Just need space for N sleep minutes
            safe_end = min(extended_end, len(sadeh_results) - consecutive_check)

        # Start search from a safe position that allows for N minutes of history
        safe_start = max(onset_idx + consecutive_check, consecutive_check)

        for i in range(safe_start, safe_end + 1):
            # Check for N consecutive sleep minutes
            consecutive_sleep = all(sadeh_results[i + offset] == 1 for offset in range(consecutive_check))

            if not consecutive_sleep:
                continue

            # Check if followed by wake (if required)
            if self.config.require_wake_after_offset:
                if i + consecutive_check < len(sadeh_results):
                    followed_by_wake = sadeh_results[i + consecutive_check] == 0
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
    sadeh_results: list[int],
    sleep_start_marker: datetime,
    sleep_end_marker: datetime,
    timestamps: list[datetime],
    config: SleepRulesConfig | None = None,
) -> tuple[int | None, int | None]:
    """
    Convenience function to apply sleep onset/offset rules.

    Args:
        sadeh_results: List of sleep/wake classifications (1=sleep, 0=wake)
        sleep_start_marker: User-provided approximate sleep start time
        sleep_end_marker: User-provided approximate sleep end time
        timestamps: List of timestamps corresponding to sadeh_results
        config: Optional rules configuration

    Returns:
        Tuple of (onset_index, offset_index), or (None, None) if not found

    """
    rules = SleepRules(config=config)
    return rules.apply_rules(sadeh_results, sleep_start_marker, sleep_end_marker, timestamps)
