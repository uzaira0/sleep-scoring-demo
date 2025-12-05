"""
Sleep scoring algorithms package - Framework-agnostic implementations.

This package provides pure Python implementations of validated sleep research algorithms
that can be used from any interface (GUI, CLI, web, batch processing) without framework
dependencies.

Algorithms Included:
    - Sadeh (1994): Sleep/wake classification from actigraphy
    - Cole-Kripke (1992): Alternative sleep/wake classification algorithm
    - Choi (2011): Nonwear period detection
    - Sleep Rules: Consecutive N/M onset/offset identification
    - Tudor-Locke (2014): Alternative onset/offset detection rules
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
from sleep_scoring_app.core.algorithms.calibration import (
    CalibrationConfig,
    CalibrationResult,
    apply_calibration,
    calibrate,
    extract_calibration_features,
    select_stationary_points,
)
from sleep_scoring_app.core.algorithms.choi import NonwearPeriod, choi_detect_nonwear, detect_nonwear
from sleep_scoring_app.core.algorithms.choi_algorithm import ChoiAlgorithm
from sleep_scoring_app.core.algorithms.cole_kripke import ColeKripkeAlgorithm, cole_kripke_score, score_activity_cole_kripke
from sleep_scoring_app.core.algorithms.config import SleepRulesConfig
from sleep_scoring_app.core.algorithms.csv_datasource import CSVDataSourceLoader
from sleep_scoring_app.core.algorithms.datasource_factory import DataSourceFactory
from sleep_scoring_app.core.algorithms.datasource_protocol import DataSourceLoader
from sleep_scoring_app.core.algorithms.factory import AlgorithmFactory
from sleep_scoring_app.core.algorithms.gt3x_datasource import GT3XDataSourceLoader
from sleep_scoring_app.core.algorithms.imputation import ImputationConfig, ImputationResult, impute_timegaps
from sleep_scoring_app.core.algorithms.nonwear_detection_protocol import NonwearDetectionAlgorithm
from sleep_scoring_app.core.algorithms.nonwear_factory import NonwearAlgorithmFactory
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
from sleep_scoring_app.core.algorithms.onset_offset_factory import OnsetOffsetRuleFactory
from sleep_scoring_app.core.algorithms.onset_offset_protocol import OnsetOffsetRule
from sleep_scoring_app.core.algorithms.protocols import CancellationCheck, LogCallback, ProgressCallback
from sleep_scoring_app.core.algorithms.sadeh import SadehAlgorithm, sadeh_score, score_activity
from sleep_scoring_app.core.algorithms.sleep_rules import SleepRules, find_sleep_onset_offset
from sleep_scoring_app.core.algorithms.sleep_scoring_protocol import SleepScoringAlgorithm
from sleep_scoring_app.core.algorithms.tudor_locke import TudorLockeConfig, TudorLockeRule
from sleep_scoring_app.core.algorithms.types import ActivityColumn

# Note: ChoiNonwearDetector and SleepScoringAlgorithms are deprecated and moved to legacy_algorithms.py
# Import them directly from sleep_scoring_app.core.legacy_algorithms if needed (but use new DI pattern instead)

__all__ = [
    "ActivityColumn",
    # === Algorithm Factory (Dependency Injection) ===
    "AlgorithmFactory",
    # === Data Source Protocol and Factory (Dependency Injection) ===
    "CSVDataSourceLoader",
    # === Calibration ===
    "CalibrationConfig",
    "CalibrationResult",
    "CancellationCheck",
    # === Choi Algorithm (Nonwear Detection) ===
    "ChoiAlgorithm",
    # === Cole-Kripke Algorithm ===
    "ColeKripkeAlgorithm",
    "DataSourceFactory",
    "DataSourceLoader",
    "GT3XDataSourceLoader",
    # === Imputation ===
    "ImputationConfig",
    "ImputationResult",
    "LogCallback",
    "NWTCorrelationResult",
    # === Nonwear Detection Protocol and Factory (Dependency Injection) ===
    "NonwearAlgorithmFactory",
    "NonwearDetectionAlgorithm",
    # === Algorithm Data Types ===
    "NonwearPeriod",
    # === Onset/Offset Rule Protocol and Factory (Dependency Injection) ===
    "OnsetOffsetRule",
    "OnsetOffsetRuleFactory",
    # === Callback Protocols ===
    "ProgressCallback",
    # === Algorithm Protocol Implementation ===
    "SadehAlgorithm",
    # === Sleep Rules ===
    "SleepRules",
    "SleepRulesConfig",
    # === Algorithm Protocol ===
    "SleepScoringAlgorithm",
    "TimeRange",
    # === Tudor-Locke Onset/Offset Rules ===
    "TudorLockeConfig",
    "TudorLockeRule",
    # === Calibration Functions ===
    "apply_calibration",
    # === Auto-Scoring Orchestration ===
    "auto_score_activity_epoch_files",
    "calculate_nwt_offset",
    "calculate_nwt_onset",
    "calculate_total_nwt_overlaps",
    "calibrate",
    "check_time_in_nonwear_periods",
    "choi_detect_nonwear",
    # === Cole-Kripke Function-Based API ===
    "cole_kripke_score",
    # === NWT Correlation Functions ===
    "correlate_sleep_with_nonwear",
    "count_overlapping_periods",
    "detect_nonwear",
    "extract_calibration_features",
    "find_sleep_onset_offset",
    # === Imputation Function-Based API ===
    "impute_timegaps",
    # === Sadeh Function-Based API ===
    "sadeh_score",
    # === Core Algorithm Functions ===
    "score_activity",
    "score_activity_cole_kripke",
    "select_stationary_points",
]

__version__ = "2.0.0"

__author__ = "Sleep Scoring Team"
__description__ = "Framework-agnostic sleep scoring algorithms for research"
