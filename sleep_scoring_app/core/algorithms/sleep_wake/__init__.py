"""
Sleep scoring algorithm implementations.

This package contains implementations of sleep/wake classification algorithms.
All algorithms implement the SleepScoringAlgorithm protocol.

Algorithms:
    - SadehAlgorithm: Sadeh et al. (1994) - 11-minute window algorithm
    - ColeKripkeAlgorithm: Cole-Kripke (1992) - 7-minute weighted window algorithm
    - VanHees2015SIB: Van Hees (2015) Sustained Inactivity Bout algorithm

Exports:
    - SadehAlgorithm: Class implementing Sadeh algorithm
    - ColeKripkeAlgorithm: Class implementing Cole-Kripke algorithm
    - VanHees2015SIB: Class implementing Van Hees 2015 SIB algorithm
    - sadeh_score: Function-based Sadeh algorithm
    - score_activity: Legacy Sadeh function (list-based API)
    - cole_kripke_score: Function-based Cole-Kripke algorithm
    - score_activity_cole_kripke: Legacy Cole-Kripke function (list-based API)
    - find_datetime_column: Utility to find datetime column in DataFrame
    - validate_and_collapse_epochs: Utility to validate and resample epochs

Note:
    HDCZA has been moved to sleep_period module as it is a Sleep Period Time
    boundary detector, not a sleep/wake classifier.

"""

from __future__ import annotations

from .cole_kripke import ColeKripkeAlgorithm, cole_kripke_score, score_activity_cole_kripke
from .factory import AlgorithmFactory
from .protocol import SleepScoringAlgorithm
from .sadeh import SadehAlgorithm, sadeh_score, score_activity
from .utils import find_datetime_column, validate_and_collapse_epochs
from .van_hees_2015 import VanHees2015SIB
from .z_angle import (
    calculate_rolling_median,
    calculate_z_angle_change,
    calculate_z_angle_from_arrays,
    calculate_z_angle_from_dataframe,
    resample_to_epochs,
    split_into_noon_to_noon_days,
    validate_raw_accelerometer_data,
)

__all__ = [
    # Factory
    "AlgorithmFactory",
    "ColeKripkeAlgorithm",
    # Epoch-based algorithm classes
    "SadehAlgorithm",
    # Protocol
    "SleepScoringAlgorithm",
    # Raw data algorithm classes
    "VanHees2015SIB",
    # Z-angle utilities
    "calculate_rolling_median",
    "calculate_z_angle_change",
    "calculate_z_angle_from_arrays",
    "calculate_z_angle_from_dataframe",
    # Cole-Kripke functions
    "cole_kripke_score",
    # General utilities
    "find_datetime_column",
    "resample_to_epochs",
    # Sadeh functions
    "sadeh_score",
    "score_activity",
    "score_activity_cole_kripke",
    "split_into_noon_to_noon_days",
    "validate_and_collapse_epochs",
    "validate_raw_accelerometer_data",
]
