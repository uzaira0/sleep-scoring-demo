"""
Direct 5-second epoch comparison between Python and GGIR.

This script compares sleep scores at the native 5-second resolution
to eliminate any resampling artifacts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add the app to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sleep_scoring_app.core.algorithms.sleep_wake.van_hees_2015 import VanHees2015SIB
from sleep_scoring_app.core.algorithms.sleep_wake.z_angle import (
    calculate_z_angle_from_dataframe,
    resample_to_epochs,
)
from sleep_scoring_app.io.sources.loader_factory import DataSourceFactory


def calculate_cohens_kappa(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate Cohen's Kappa for inter-rater agreement."""
    tp = np.sum((y_true == 1) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))

    n = len(y_true)
    if n == 0:
        return 0.0

    po = (tp + tn) / n
    p_yes = ((tp + fp) / n) * ((tp + fn) / n)
    p_no = ((tn + fn) / n) * ((tn + fp) / n)
    pe = p_yes + p_no

    if (1 - pe) == 0:
        return 1.0 if po == 1.0 else 0.0

    return (po - pe) / (1 - pe)


def main():
    # Paths
    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    gt3x_file = Path("D:/Scripts/monorepo/external/ggir/data/TestUA_MOS2E22180349_2023-03-07___09-39-04.gt3x")

    # Load GGIR reference data (5-second epochs)
    ggir_sib_file = ggir_reference_dir / "ggir_sib_vanHees2015.csv"
    ggir_df = pd.read_csv(ggir_sib_file)
    ggir_df["timestamp"] = pd.to_datetime(ggir_df["timestamp"], format="mixed")

    # Load GT3X file with Python
    loader = DataSourceFactory.create("gt3x")
    loader.return_raw = True
    result = loader.load_file(str(gt3x_file))

    if isinstance(result, dict) and "activity_data" in result:
        raw_df = result["activity_data"]
        metadata = result.get("metadata", {})
    else:
        raw_df = result
        metadata = {}

    # Calculate z-angle from raw data
    df_with_z = calculate_z_angle_from_dataframe(
        raw_df,
        ax_col="AXIS_X",
        ay_col="AXIS_Y",
        az_col="AXIS_Z",
    )

    # Resample to 5-second epochs using median (as GGIR does)
    z_angle_epochs = resample_to_epochs(
        df_with_z,
        timestamp_col="timestamp",
        value_col="z_angle",
        epoch_seconds=5,
        aggregation="median",
    )

    # Compare z-angle values first

    # Merge by timestamp
    merged = pd.merge(
        ggir_df[["timestamp", "anglez", "sleep_score"]],
        z_angle_epochs.rename(columns={"z_angle": "python_anglez"}),
        on="timestamp",
        how="inner",
    )

    # Only compare non-NA values
    valid_mask = merged["anglez"].notna()
    if valid_mask.sum() > 0:
        ggir_angles = merged.loc[valid_mask, "anglez"].values
        python_angles = merged.loc[valid_mask, "python_anglez"].values

        angle_diff = np.abs(ggir_angles - python_angles)

        # If angles are nearly identical (< 0.01 difference), show that
        exact_match = (angle_diff < 0.01).sum()

    # Run Python van Hees 2015 algorithm at 5-second resolution

    # Use the algorithm directly but get 5-second output
    algorithm = VanHees2015SIB(
        angle_threshold=5.0,
        time_threshold=5,
        epoch_length=5,
    )

    # Run internally to get 5-second results
    z_angles = z_angle_epochs["z_angle"].to_numpy()
    timestamps = z_angle_epochs["timestamp"].to_numpy()

    # Call the internal classification method
    python_sleep_5s = algorithm._classify_sleep_wake(z_angles, timestamps)

    # Merge Python results with GGIR
    z_angle_epochs["python_sleep"] = python_sleep_5s
    merged = pd.merge(
        ggir_df[["timestamp", "anglez", "sleep_score"]].rename(columns={"sleep_score": "ggir_sleep"}),
        z_angle_epochs[["timestamp", "z_angle", "python_sleep"]],
        on="timestamp",
        how="inner",
    )

    ggir_sleep = merged["ggir_sleep"].values
    python_sleep = merged["python_sleep"].values

    # Overall agreement
    agreement = np.mean(ggir_sleep == python_sleep)

    # Cohen's Kappa
    kappa = calculate_cohens_kappa(ggir_sleep, python_sleep)

    # Confusion matrix
    tp = np.sum((ggir_sleep == 1) & (python_sleep == 1))
    tn = np.sum((ggir_sleep == 0) & (python_sleep == 0))
    fp = np.sum((ggir_sleep == 0) & (python_sleep == 1))
    fn = np.sum((ggir_sleep == 1) & (python_sleep == 0))

    # Analyze disagreements

    # Where Python says wake but GGIR says sleep (false negatives)
    fn_mask = (ggir_sleep == 1) & (python_sleep == 0)
    if fn_mask.sum() > 0:
        fn_epochs = merged[fn_mask]

    # Where Python says sleep but GGIR says wake (false positives)
    fp_mask = (ggir_sleep == 0) & (python_sleep == 1)
    if fp_mask.sum() > 0:
        fp_epochs = merged[fp_mask]

    # Check if NA anglez values affect the result
    na_mask = merged["anglez"].isna()
    if na_mask.sum() > 0:
        na_disagreement = (ggir_sleep[na_mask] != python_sleep[na_mask]).sum()

    # Summary

    if kappa >= 0.99:
        return 0

    # Suggestions
    if fn_mask.sum() > fp_mask.sum():
        pass
    else:
        pass

    if na_mask.sum() > 0:
        pass

    return 1


if __name__ == "__main__":
    sys.exit(main())
