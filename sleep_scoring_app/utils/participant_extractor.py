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
        return ParticipantInfo(
            numerical_id="UNKNOWN", timepoint=ParticipantTimepoint.T1, group=ParticipantGroup.GROUP_1, timepoint_str="T1", group_str="G1"
        )

    input_string = str(input_string).strip()

    # If no config provided, try to get from global ConfigManager
    if config is None:
        config = _get_global_config()

    # Get configured patterns if available
    id_patterns_from_config = []
    if config and hasattr(config, "study_participant_id_patterns") and config.study_participant_id_patterns:
        id_patterns_from_config = config.study_participant_id_patterns

    # Get timepoint pattern from config (with fallback to default)
    timepoint_pattern = None
    if config and hasattr(config, "study_timepoint_pattern") and config.study_timepoint_pattern:
        timepoint_pattern = config.study_timepoint_pattern

    # Get group pattern from config (with fallback to default)
    group_pattern = None
    if config and hasattr(config, "study_group_pattern") and config.study_group_pattern:
        group_pattern = config.study_group_pattern

    # Get default values from config valid lists
    default_group = "G1"
    default_timepoint = "T1"
    if config and hasattr(config, "study_valid_groups") and config.study_valid_groups:
        default_group = config.study_valid_groups[0]
    if config and hasattr(config, "study_valid_timepoints") and config.study_valid_timepoints:
        default_timepoint = config.study_valid_timepoints[0]

    # Try configured patterns - if none configured or none match, return UNKNOWN
    if not id_patterns_from_config:
        logger.warning("No participant ID patterns configured. Configure patterns in Study Settings.")
        return ParticipantInfo(
            numerical_id="UNKNOWN",
            timepoint=ParticipantTimepoint.T1,
            group=ParticipantGroup.GROUP_1,
            full_id="UNKNOWN T1 G1",
            timepoint_str=default_timepoint,
            group_str=default_group,
        )

    for pattern_str in id_patterns_from_config:
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            match = pattern.search(input_string)

            if match:
                groups = match.groups()

                # The first capture group is always the participant ID
                if len(groups) >= 1:
                    numerical_id = groups[0]

                    # Extract timepoint using configured pattern
                    timepoint = _extract_timepoint(input_string, timepoint_pattern, default_timepoint)

                    # Extract group using configured pattern
                    group_str = _extract_group(input_string, group_pattern, default_group)

                    # Convert to enums (with flexible mapping)
                    timepoint_enum = _string_to_timepoint_enum(timepoint)
                    group_enum = _string_to_group_enum(group_str)

                    logger.debug("Extracted participant ID '%s' using configured pattern '%s'", numerical_id, pattern_str)
                    return ParticipantInfo(
                        numerical_id=numerical_id,
                        timepoint=timepoint_enum,
                        group=group_enum,
                        full_id=f"{numerical_id} {timepoint} {group_str}",
                        timepoint_str=timepoint,
                        group_str=group_str,
                    )
        except re.error as e:
            logger.exception("Invalid regex pattern '%s': %s", pattern_str, e)
            continue

    # No patterns matched - log which patterns were tried
    logger.warning(
        "No configured patterns matched input '%s'. Configured patterns: %s",
        input_string,
        id_patterns_from_config,
    )
    return ParticipantInfo(
        numerical_id="UNKNOWN",
        timepoint=ParticipantTimepoint.T1,
        group=ParticipantGroup.GROUP_1,
        full_id="UNKNOWN T1 G1",
        timepoint_str=default_timepoint,
        group_str=default_group,
    )


def _extract_timepoint(input_string: str, pattern: str | None, default: str) -> str:
    """Extract timepoint from string using configured pattern."""
    if not pattern or pattern.upper() == "N/A":
        # No pattern configured, use default
        return default

    try:
        regex = re.compile(pattern, re.IGNORECASE)
        match = regex.search(input_string)
        if match:
            # Return the first capture group if present, otherwise the full match
            if match.groups():
                return match.group(1).upper()
            return match.group(0).upper()
    except re.error as e:
        logger.warning("Invalid timepoint regex pattern '%s': %s", pattern, e)

    return default


def _extract_group(input_string: str, pattern: str | None, default: str) -> str:
    """Extract group from string using configured pattern."""
    if not pattern or pattern.upper() == "N/A":
        # No pattern configured, use default
        return default

    try:
        regex = re.compile(pattern, re.IGNORECASE)
        match = regex.search(input_string)
        if match:
            # Return the first capture group if present, otherwise the full match
            if match.groups():
                return match.group(1).upper()
            return match.group(0).upper()
    except re.error as e:
        logger.warning("Invalid group regex pattern '%s': %s", pattern, e)

    return default


def _string_to_timepoint_enum(timepoint: str) -> ParticipantTimepoint:
    """Convert timepoint string to enum with flexible mapping."""
    timepoint = timepoint.upper()
    # Direct enum value match
    if timepoint == "T1":
        return ParticipantTimepoint.T1
    if timepoint == "T2":
        return ParticipantTimepoint.T2
    if timepoint == "T3":
        return ParticipantTimepoint.T3
    # For any other value, return T1 as default but the string will be preserved in full_id
    return ParticipantTimepoint.T1


def _string_to_group_enum(group: str) -> ParticipantGroup:
    """Convert group string to enum with flexible mapping."""
    group = group.upper()
    # Check for known enum values
    if group in ("G1", "GROUP_1", "GROUP1"):
        return ParticipantGroup.GROUP_1
    if group in ("G2", "GROUP_2", "GROUP2"):
        return ParticipantGroup.GROUP_2
    if group in ("G3", "GROUP_3", "GROUP3"):
        return ParticipantGroup.GROUP_3
    if group in ("ISSUE", "IGNORE"):
        return ParticipantGroup.ISSUE
    # For any other value, return GROUP_1 as default but the string will be preserved in full_id
    return ParticipantGroup.GROUP_1
