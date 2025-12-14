"""
Compare Python sleep algorithms against GGIR R reference output.

This script:
1. Loads the GGIR R reference data (angle-z and SIB scores)
2. Runs the Python van Hees 2015 SIB algorithm on the same GT3X file
3. Compares the outputs and calculates Cohen's Kappa and ICC
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add the app to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sleep_scoring_app.core.algorithms.sleep_wake.van_hees_2015 import VanHees2015SIB
from sleep_scoring_app.io.sources.loader_factory import DataSourceFactory


def calculate_cohens_kappa(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate Cohen's Kappa for inter-rater agreement."""
    # Confusion matrix elements
    tp = np.sum((y_true == 1) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))

    n = len(y_true)
    if n == 0:
        return 0.0

    # Observed agreement
    po = (tp + tn) / n

    # Expected agreement
    p_yes = ((tp + fp) / n) * ((tp + fn) / n)
    p_no = ((tn + fn) / n) * ((tn + fp) / n)
    pe = p_yes + p_no

    # Kappa
    if (1 - pe) == 0:
        return 1.0 if po == 1.0 else 0.0

    return (po - pe) / (1 - pe)


def calculate_icc(y1: np.ndarray, y2: np.ndarray) -> float:
    """Calculate Intraclass Correlation Coefficient (ICC 2,1)."""
    n = len(y1)
    if n < 2:
        return 0.0

    # Mean of each rater
    mean1 = np.mean(y1)
    mean2 = np.mean(y2)
    grand_mean = (mean1 + mean2) / 2

    # Between-subjects variance
    subject_means = (y1 + y2) / 2
    ss_between = 2 * np.sum((subject_means - grand_mean) ** 2)

    # Within-subjects variance
    ss_within = np.sum((y1 - subject_means) ** 2) + np.sum((y2 - subject_means) ** 2)

    # Mean squares
    ms_between = ss_between / (n - 1)
    ms_within = ss_within / n

    # ICC(2,1)
    if (ms_between + ms_within) == 0:
        return 1.0

    return (ms_between - ms_within) / (ms_between + ms_within)


def main():
    # Paths
    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    gt3x_file = Path("D:/Scripts/monorepo/external/ggir/data/TestUA_MOS2E22180349_2023-03-07___09-39-04.gt3x")

    # Load GGIR reference data
    ggir_sib_file = ggir_reference_dir / "ggir_sib_vanHees2015.csv"

    if not ggir_sib_file.exists():
        return 1

    ggir_df = pd.read_csv(ggir_sib_file)

    # Load GT3X file with Python (using gt3x-rs if available)
    loader = DataSourceFactory.create("gt3x")

    # Configure for raw data
    loader.return_raw = True
    result = loader.load_file(str(gt3x_file))

    if isinstance(result, dict) and "activity_data" in result:
        raw_df = result["activity_data"]
    else:
        raw_df = result

    # Column names should now be uppercase from DatabaseColumn enum
    # But handle legacy lowercase for backwards compatibility
    rename_map = {"axis_x": "AXIS_X", "axis_y": "AXIS_Y", "axis_z": "AXIS_Z"}
    raw_df = raw_df.rename(columns={k: v for k, v in rename_map.items() if k in raw_df.columns})

    # Check if autocalibration was applied
    if isinstance(result, dict) and "metadata" in result:
        metadata = result["metadata"]
        if metadata.get("autocalibrated"):
            calibration = metadata.get("calibration", {})
            error_before = calibration.get("error_before", 0)
            error_after = calibration.get("error_after", 0)
        else:
            pass

    # Run Python van Hees 2015 algorithm
    algorithm = VanHees2015SIB(
        angle_threshold=5.0,
        time_threshold=5,
        epoch_length=5,  # 5-second epochs to match GGIR
    )

    python_result = algorithm.score(raw_df)

    # Compare z-angle calculations first
    ggir_anglez_file = ggir_reference_dir / "ggir_anglez_5sec.csv"
    if ggir_anglez_file.exists():
        ggir_anglez_df = pd.read_csv(ggir_anglez_file)

        # Get Python z-angle from the result (it's calculated internally but we can recalculate)
        # For now, compare the available data
        if "z_angle" in python_result.columns:
            # Resample Python result to 5-second epochs for comparison
            min_len = min(len(ggir_anglez_df), len(python_result))
            ggir_anglez = ggir_anglez_df["anglez"].values[:min_len]
            # python_anglez = python_result["z_angle"].values[:min_len]

    # Align the two datasets for comparison

    # GGIR outputs 5-second epochs, Python outputs 60-second epochs
    # Need to resample GGIR to 60-second epochs for fair comparison
    ggir_sleep_scores = ggir_df["sleep_score"].values

    # Resample GGIR from 5-sec to 60-sec using majority vote (12 epochs per minute)
    epochs_per_minute = 12
    n_minutes = len(ggir_sleep_scores) // epochs_per_minute

    ggir_60sec = np.zeros(n_minutes, dtype=int)
    for i in range(n_minutes):
        start_idx = i * epochs_per_minute
        end_idx = (i + 1) * epochs_per_minute
        # Majority vote: if >= 50% are sleep, classify as sleep
        ggir_60sec[i] = 1 if np.mean(ggir_sleep_scores[start_idx:end_idx]) >= 0.5 else 0

    python_sleep_scores = python_result["Sleep Score"].values

    # Align lengths
    min_len = min(len(ggir_60sec), len(python_sleep_scores))
    ggir_aligned = ggir_60sec[:min_len]
    python_aligned = python_sleep_scores[:min_len]

    # Calculate agreement metrics

    # Overall agreement
    agreement = np.mean(ggir_aligned == python_aligned)

    # Cohen's Kappa
    kappa = calculate_cohens_kappa(ggir_aligned, python_aligned)

    # ICC
    icc = calculate_icc(ggir_aligned.astype(float), python_aligned.astype(float))

    # Confusion matrix
    tp = np.sum((ggir_aligned == 1) & (python_aligned == 1))
    tn = np.sum((ggir_aligned == 0) & (python_aligned == 0))
    fp = np.sum((ggir_aligned == 0) & (python_aligned == 1))
    fn = np.sum((ggir_aligned == 1) & (python_aligned == 0))

    # Sensitivity and Specificity
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0

    # Export comparison results
    comparison_df = pd.DataFrame(
        {
            "epoch_index": range(min_len),
            "ggir_sleep": ggir_aligned,
            "python_sleep": python_aligned,
            "agreement": (ggir_aligned == python_aligned).astype(int),
        }
    )

    output_file = ggir_reference_dir / "comparison_results.csv"
    comparison_df.to_csv(output_file, index=False)

    # Summary
    if kappa >= 0.8 or kappa >= 0.6 or kappa >= 0.4:
        pass
    else:
        pass

    if kappa >= 0.99:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
