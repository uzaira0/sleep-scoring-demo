"""
Sleep Algorithm Validation Script.

Compares Python implementations of van Hees 2015 (SIB) and HDCZA algorithms
against GGIR R package reference output.

Validation metrics:
- Cohen's Kappa (epoch-by-epoch agreement for SIB)
- ICC (Intraclass Correlation Coefficient)
- Sensitivity, Specificity, Accuracy
- SPT onset/offset difference in minutes (for HDCZA)

Usage:
    1. First run run_ggir_sleep.R to generate reference data
    2. Then run this script: python validate_sleep_algorithms.py

References:
- van Hees VT, et al. (2015). PLoS ONE.
- van Hees VT, et al. (2018). Scientific Reports.

"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy import stats

# Add the app to path
APP_PATH = Path(__file__).parent.parent
sys.path.insert(0, str(APP_PATH))

# Validation data paths
GGIR_PATH = Path("D:/Scripts/monorepo/external/ggir")
VALIDATION_DATA_PATH = GGIR_PATH / "output" / "sleep_validation" / "validation_data"
GT3X_DATA_PATH = GGIR_PATH / "data"
TEST_FILE = "TestUA_MOS2E22180349_2023-03-07___09-39-04.gt3x"


def calculate_cohens_kappa(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate Cohen's Kappa for inter-rater agreement.

    Args:
        y_true: Reference labels (0=wake, 1=sleep)
        y_pred: Predicted labels (0=wake, 1=sleep)

    Returns:
        Cohen's Kappa coefficient (-1 to 1, 1 = perfect agreement)

    """
    # Ensure same length
    min_len = min(len(y_true), len(y_pred))
    y_true = y_true[:min_len]
    y_pred = y_pred[:min_len]

    # Calculate confusion matrix
    n = len(y_true)
    tp = np.sum((y_true == 1) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))

    # Observed agreement
    po = (tp + tn) / n

    # Expected agreement by chance
    p_true_1 = (tp + fn) / n
    p_pred_1 = (tp + fp) / n
    p_true_0 = (tn + fp) / n
    p_pred_0 = (tn + fn) / n
    pe = (p_true_1 * p_pred_1) + (p_true_0 * p_pred_0)

    # Kappa
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def calculate_icc(y1: np.ndarray, y2: np.ndarray) -> tuple[float, float, float]:
    """
    Calculate Intraclass Correlation Coefficient (ICC 2,1).

    Args:
        y1: First measurement series
        y2: Second measurement series

    Returns:
        Tuple of (ICC, lower 95% CI, upper 95% CI)

    """
    # Ensure same length
    min_len = min(len(y1), len(y2))
    y1 = y1[:min_len].astype(float)
    y2 = y2[:min_len].astype(float)

    n = len(y1)

    # Stack measurements
    data = np.column_stack([y1, y2])

    # Calculate means
    grand_mean = np.mean(data)
    row_means = np.mean(data, axis=1)
    col_means = np.mean(data, axis=0)

    # Calculate sum of squares
    ss_total = np.sum((data - grand_mean) ** 2)
    ss_rows = 2 * np.sum((row_means - grand_mean) ** 2)  # k=2 raters
    ss_cols = n * np.sum((col_means - grand_mean) ** 2)
    ss_error = ss_total - ss_rows - ss_cols

    # Mean squares
    k = 2  # number of raters
    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))

    # ICC(2,1) - Two-way random, single measures
    icc = (ms_rows - ms_error) / (ms_rows + (k - 1) * ms_error + (k / n) * (ms_cols - ms_error))

    # Confidence intervals (approximate)
    # Using F-distribution for confidence interval
    f_value = ms_rows / ms_error
    df1 = n - 1
    df2 = (n - 1) * (k - 1)

    f_lower = f_value / stats.f.ppf(0.975, df1, df2)
    f_upper = f_value / stats.f.ppf(0.025, df1, df2)

    icc_lower = (f_lower - 1) / (f_lower + k - 1)
    icc_upper = (f_upper - 1) / (f_upper + k - 1)

    return icc, icc_lower, icc_upper


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Calculate comprehensive classification metrics.

    Args:
        y_true: Reference labels (0=wake, 1=sleep)
        y_pred: Predicted labels (0=wake, 1=sleep)

    Returns:
        Dictionary of metrics

    """
    # Ensure same length
    min_len = min(len(y_true), len(y_pred))
    y_true = y_true[:min_len]
    y_pred = y_pred[:min_len]

    # Confusion matrix
    tp = np.sum((y_true == 1) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))

    n = len(y_true)

    # Metrics
    accuracy = (tp + tn) / n
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1 = 2 * (precision * sensitivity) / (precision + sensitivity) if (precision + sensitivity) > 0 else 0

    # Kappa
    kappa = calculate_cohens_kappa(y_true, y_pred)

    # ICC
    icc, icc_lower, icc_upper = calculate_icc(y_true, y_pred)

    return {
        "n_epochs": n,
        "accuracy": accuracy,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "f1_score": f1,
        "kappa": kappa,
        "icc": icc,
        "icc_95ci": (icc_lower, icc_upper),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "mismatches": fp + fn,
    }


def load_ggir_reference_data() -> dict:
    """Load GGIR reference data from CSV files."""
    data = {}

    # Load SIB results
    sib_path = VALIDATION_DATA_PATH / "r_sib_vanHees2015.csv"
    if sib_path.exists():
        data["sib"] = pd.read_csv(sib_path)

    # Load angle-z data
    anglez_path = VALIDATION_DATA_PATH / "r_anglez_5sec.csv"
    if anglez_path.exists():
        data["anglez"] = pd.read_csv(anglez_path)

    # Load HDCZA SPT results
    hdcza_path = VALIDATION_DATA_PATH / "r_hdcza_spt.csv"
    if hdcza_path.exists():
        data["hdcza_spt"] = pd.read_csv(hdcza_path)

    # Load HDCZA crude SPT
    hdcza_crude_path = VALIDATION_DATA_PATH / "r_hdcza_spt_crude.csv"
    if hdcza_crude_path.exists():
        data["hdcza_crude"] = pd.read_csv(hdcza_crude_path)

    return data


def run_python_sib(anglez: np.ndarray, ws3: int = 5) -> np.ndarray:
    """
    Run Python van Hees 2015 SIB algorithm.

    Args:
        anglez: Z-angle values at 5-second epochs
        ws3: Epoch size in seconds (default: 5)

    Returns:
        Array of sleep/wake classifications (1=sleep, 0=wake)

    """
    from sleep_scoring_app.core.algorithms.sleep_wake.z_angle import (
        calculate_z_angle_change,
    )

    angle_threshold = 5.0  # degrees
    time_threshold = 5  # minutes

    # Number of epochs for time threshold
    epochs_per_window = int(time_threshold * 60 / ws3)  # 60 epochs for 5 min with 5s epochs

    n = len(anglez)
    sib_scores = np.zeros(n, dtype=int)

    # For each position, check if angle change in the window is below threshold
    # GGIR's vanHees2015 looks for periods where angle doesn't change by more than
    # threshold degrees for at least time_threshold minutes

    # Calculate absolute differences
    angle_diff = np.abs(np.diff(anglez))

    # Find posture changes (where angle changes by more than threshold)
    posture_changes = np.where(angle_diff > angle_threshold)[0]

    # If no posture changes, classify all as sleep
    if len(posture_changes) == 0:
        return np.ones(n, dtype=int)

    # Find gaps between posture changes that are longer than time_threshold
    # (i.e., periods with no significant posture change)
    for i in range(len(posture_changes) - 1):
        gap = posture_changes[i + 1] - posture_changes[i]
        if gap > epochs_per_window:  # Gap longer than time threshold
            # Mark this period as sleep (no posture change)
            start_idx = posture_changes[i]
            end_idx = posture_changes[i + 1]
            sib_scores[start_idx : end_idx + 1] = 1

    return sib_scores


def run_python_hdcza(anglez: np.ndarray, timestamps: np.ndarray, ws3: int = 5) -> tuple:
    """
    Run Python HDCZA algorithm.

    Args:
        anglez: Z-angle values at 5-second epochs
        timestamps: Timestamp array
        ws3: Epoch size in seconds

    Returns:
        Tuple of (spt_start_idx, spt_end_idx, threshold)

    """
    from sleep_scoring_app.core.algorithms.sleep_wake.hdcza import HDCZAAlgorithm

    # Create a DataFrame with the required structure
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(timestamps),
            "anglez": anglez,
        }
    )

    # Create HDCZA algorithm instance
    hdcza = HDCZAAlgorithm()

    # Run the algorithm
    try:
        result_df = hdcza.score(df)

        # Get SPT windows
        spt_windows = hdcza.spt_windows

        if spt_windows and len(spt_windows) > 0:
            # Get the main (longest) SPT window
            main_spt = max(spt_windows, key=lambda w: (w.offset - w.onset).total_seconds())

            # Find indices
            onset_idx = df[df["timestamp"] >= main_spt.onset].index[0] if len(df[df["timestamp"] >= main_spt.onset]) > 0 else None
            offset_idx = df[df["timestamp"] <= main_spt.offset].index[-1] if len(df[df["timestamp"] <= main_spt.offset]) > 0 else None

            return onset_idx, offset_idx, hdcza._threshold

        return None, None, None
    except Exception as e:
        return None, None, None


def validate_sib():
    """Validate van Hees 2015 SIB algorithm."""
    # Load reference data
    ref_data = load_ggir_reference_data()

    if "sib" not in ref_data:
        return None

    sib_ref = ref_data["sib"]
    anglez = sib_ref["anglez"].values
    r_sib = sib_ref["sib_T5A5"].values

    # Run Python implementation
    py_sib = run_python_sib(anglez)

    # Calculate metrics
    metrics = calculate_metrics(r_sib, py_sib)

    # Check if we meet the 1.0 kappa target
    if metrics["kappa"] >= 0.99:
        pass
    else:
        # Show first few mismatches for debugging
        mismatches = np.where(r_sib != py_sib)[0]
        if len(mismatches) > 0:
            for idx in mismatches[:10]:
                pass

    return metrics


def validate_hdcza():
    """Validate HDCZA algorithm."""
    # Load reference data
    ref_data = load_ggir_reference_data()

    if "hdcza_spt" not in ref_data or "anglez" not in ref_data:
        return

    hdcza_ref = ref_data["hdcza_spt"]
    anglez_df = ref_data["anglez"]

    r_start = hdcza_ref["SPTE_start_idx"].values[0]
    r_end = hdcza_ref["SPTE_end_idx"].values[0]
    r_threshold = hdcza_ref["tib_threshold"].values[0]

    anglez = anglez_df["anglez"].values
    timestamps = anglez_df["timestamp"].values

    # Run Python implementation
    py_start, py_end, py_threshold = run_python_hdcza(anglez, timestamps)

    # Calculate differences
    if py_start is not None and py_end is not None:
        start_diff = abs(py_start - r_start) * 5 / 60  # Convert epochs to minutes
        end_diff = abs(py_end - r_end) * 5 / 60

        if py_threshold is not None:
            threshold_diff = abs(py_threshold - r_threshold)

        # Check if within tolerance (e.g., 5 minutes)
        if start_diff <= 5 and end_diff <= 5:
            pass
        else:
            pass
    else:
        pass

    # Also validate epoch-level crude SPT estimate if available
    if "hdcza_crude" in ref_data:
        crude_ref = ref_data["hdcza_crude"]["spt_crude"].values
        # Note: Values are 0=none, 1=potential SPT, 2=final SPT
        n_spt = np.sum(crude_ref == 2)


def main():
    """Main validation function."""
    # Check if validation data exists
    if not VALIDATION_DATA_PATH.exists():
        return

    # List available files
    for f in VALIDATION_DATA_PATH.glob("*.csv"):
        pass

    # Run validations
    sib_metrics = validate_sib()
    validate_hdcza()


if __name__ == "__main__":
    main()
