#!/usr/bin/env python3
"""Simple participant extraction - extracts participant info from filenames."""

from __future__ import annotations

import logging
import re

from sleep_scoring_app.core.constants import ParticipantGroup, ParticipantTimepoint
from sleep_scoring_app.core.dataclasses import ParticipantInfo

logger = logging.getLogger(__name__)


def _get_global_config():
    """Get config from ConfigManager if available (lazy import to avoid circular deps)."""
    try:
        from sleep_scoring_app.utils.config import ConfigManager

        config_manager = ConfigManager()
        return config_manager.config
    except Exception:
        return None


def extract_participant_info(input_string: str, config=None) -> ParticipantInfo:
    """
    Extract participant info from input string.

    Args:
        input_string: Filename or string to extract from
        config: Optional AppConfig with patterns and defaults. If not provided,
                attempts to load from global ConfigManager.

    Returns:
        ParticipantInfo with extracted data

    """
    if not input_string:
        # Return defaults for empty input
        return ParticipantInfo(numerical_id="UNKNOWN", timepoint=ParticipantTimepoint.T1, group=ParticipantGroup.GROUP_1)

    input_string = str(input_string).strip()

    # If no config provided, try to get from global ConfigManager
    if config is None:
        config = _get_global_config()

    # Get configured patterns if available
    id_patterns_from_config = []
    if config and hasattr(config, "study_participant_id_patterns") and config.study_participant_id_patterns:
        id_patterns_from_config = config.study_participant_id_patterns

    # Hardcoded defaults
    default_group = "G1"
    default_timepoint = "T1"

    # Try configured patterns first
    for pattern_str in id_patterns_from_config:
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            match = pattern.search(input_string)

            if match:
                groups = match.groups()

                # The first capture group is always the participant ID
                if len(groups) >= 1:
                    numerical_id = groups[0]

                    # Try to extract timepoint from the string
                    timepoint_match = re.search(r"\b(T\d+)\b", input_string, re.IGNORECASE)
                    if timepoint_match:
                        timepoint = timepoint_match.group(1).upper()
                    else:
                        timepoint = default_timepoint

                    # If there are more capture groups, use them for group/timepoint
                    if len(groups) >= 2:
                        second = groups[1]
                        if second and second.upper().startswith("T"):
                            timepoint = second.upper()

                    # Convert timepoint string to enum
                    timepoint_enum = _timepoint_to_enum(timepoint)

                    # Check for group in string
                    group_enum, group_str = _extract_group(input_string)

                    logger.debug("Extracted participant ID '%s' using configured pattern '%s'", numerical_id, pattern_str)
                    return ParticipantInfo(
                        numerical_id=numerical_id,
                        timepoint=timepoint_enum,
                        group=group_enum,
                        full_id=f"{numerical_id} {timepoint} {group_str}",
                    )
        except Exception:
            continue  # Try next pattern

    # Fallback: hardcoded patterns for legacy support
    fallback_patterns = [
        r"(P1-\d{4})",  # P1-1001 format
        r"^(\d{4})$",  # Pure numeric format like 4002, 4000, 4006
    ]

    for id_pattern in fallback_patterns:
        match = re.search(id_pattern, input_string, re.IGNORECASE)
        if match:
            numerical_id = match.group(1)

            # For pure numeric IDs, convert to P1-XXXX format for consistency
            if id_pattern == r"^(\d{4})$":
                numerical_id = f"P1-{numerical_id}"

            # Try to find timepoint T1, T2, or T3
            timepoint_match = re.search(r"T[123]", input_string, re.IGNORECASE)
            timepoint = timepoint_match.group(0).upper() if timepoint_match else "T1"

            timepoint_enum = _timepoint_to_enum(timepoint)
            group_enum, group_str = _extract_group(input_string)

            return ParticipantInfo(
                numerical_id=numerical_id,
                timepoint=timepoint_enum,
                group=group_enum,
                full_id=f"{numerical_id} {timepoint} {group_str}",
            )

    return ParticipantInfo(numerical_id="UNKNOWN", timepoint=ParticipantTimepoint.T1, group=ParticipantGroup.GROUP_1, full_id="UNKNOWN T1 G1")


def _timepoint_to_enum(timepoint: str) -> ParticipantTimepoint:
    """Convert timepoint string to enum."""
    timepoint = timepoint.upper()
    if timepoint == "T1":
        return ParticipantTimepoint.T1
    if timepoint == "T2":
        return ParticipantTimepoint.T2
    if timepoint == "T3":
        return ParticipantTimepoint.T3
    return ParticipantTimepoint.T1


def _extract_group(input_string: str) -> tuple[ParticipantGroup, str]:
    """Extract group from string, return (enum, string)."""
    group_match = re.search(r"(ISSUE|IGNORE)", input_string, re.IGNORECASE)
    if group_match:
        return ParticipantGroup.ISSUE, "ISSUE"
    return ParticipantGroup.GROUP_1, "G1"
