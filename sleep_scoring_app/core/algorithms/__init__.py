"""
Sleep scoring algorithms package - Framework-agnostic implementations.

This package provides pure Python implementations of validated sleep research algorithms
that can be used from any interface (GUI, CLI, web, batch processing) without framework
dependencies.

Algorithms Included:
    - Sadeh (1994): Sleep/wake classification from actigraphy
    - Choi (2011): Nonwear period detection
    - Sleep Rules: Onset/offset identification
    - NWT Correlation: Nonwear sensor correlation analysis

Example Usage (New DataFrame-based API):
    ```python
    import pandas as pd
    from sleep_scoring_app.core.algorithms import (
        sadeh_score,
        choi_detect_nonwear,
        ActivityColumn,
    )

    # Load activity data into DataFrame
    df = pd.read_csv('activity_data.csv')  # Has datetime, Axis1, Vector Magnitude columns

    # Sadeh sleep scoring - NO parameters needed (always uses Axis1)
    df = sadeh_score(df)  # Adds 'Sadeh Score' column to df

    # Choi nonwear detection - specify activity column with enum
    df = choi_detect_nonwear(df, activity_column=ActivityColumn.VECTOR_MAGNITUDE)  # Adds 'Choi Nonwear' column

    # Can also chain operations
    df = choi_detect_nonwear(sadeh_score(df), ActivityColumn.VECTOR_MAGNITUDE)
    ```

Package Structure:
    - types.py: Algorithm type definitions (ActivityColumn enum)
    - protocols.py: Framework-agnostic callback protocols
    - config.py: Algorithm configuration dataclasses (SleepRulesConfig only)
    - sadeh.py: Sadeh algorithm implementation (function-based)
    - choi.py: Choi algorithm implementation (function-based)
    - sleep_rules.py: Sleep onset/offset rules
    - nwt_correlation.py: NWT correlation functions
"""

from __future__ import annotations

from sleep_scoring_app.core.algorithms.auto_score import auto_score_activity_epoch_files
from sleep_scoring_app.core.algorithms.choi import NonwearPeriod, choi_detect_nonwear, detect_nonwear
from sleep_scoring_app.core.algorithms.config import SleepRulesConfig
from sleep_scoring_app.core.algorithms.nwt_correlation import (
    NWTCorrelationResult,
    TimeRange,
    calculate_nwt_offset,
    calculate_nwt_onset,
    calculate_total_nwt_overlaps,
    check_time_in_nonwear_periods,
    correlate_sleep_with_nonwear,
    count_overlapping_periods,
)
from sleep_scoring_app.core.algorithms.protocols import CancellationCheck, LogCallback, ProgressCallback
from sleep_scoring_app.core.algorithms.sadeh import sadeh_score, score_activity
from sleep_scoring_app.core.algorithms.sleep_rules import SleepRules, find_sleep_onset_offset
from sleep_scoring_app.core.algorithms.types import ActivityColumn
from sleep_scoring_app.core.legacy_algorithms import ChoiNonwearDetector, SleepScoringAlgorithms

__all__ = [
    "ActivityColumn",
    "CancellationCheck",
    "ChoiNonwearDetector",
    "LogCallback",
    "NWTCorrelationResult",
    # === Algorithm Data Types ===
    "NonwearPeriod",
    # === Callback Protocols ===
    "ProgressCallback",
    # === Sleep Rules ===
    "SleepRules",
    "SleepRulesConfig",
    # === Facade Classes (Validated Wrappers) ===
    "SleepScoringAlgorithms",
    "TimeRange",
    # === Auto-Scoring Orchestration ===
    "auto_score_activity_epoch_files",
    "calculate_nwt_offset",
    "calculate_nwt_onset",
    "calculate_total_nwt_overlaps",
    "check_time_in_nonwear_periods",
    "choi_detect_nonwear",
    # === NWT Correlation Functions ===
    "correlate_sleep_with_nonwear",
    "count_overlapping_periods",
    "detect_nonwear",
    "find_sleep_onset_offset",
    # === New Function-Based API ===
    "sadeh_score",
    # === Core Algorithm Functions ===
    "score_activity",
]

__version__ = "2.0.0"

__author__ = "Sleep Scoring Team"
__description__ = "Framework-agnostic sleep scoring algorithms for research"
