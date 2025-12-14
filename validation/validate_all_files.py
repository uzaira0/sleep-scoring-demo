"""
Validate van Hees 2015 SIB algorithm against GGIR reference data.

This script:
1. Processes all GT3X files with our Python implementation
2. Compares against GGIR reference data where available
3. Reports Cohen's Kappa for each file
"""

import glob
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add the app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sleep_scoring_app.core.algorithms.sleep_wake.van_hees_2015 import VanHees2015SIB
from sleep_scoring_app.core.algorithms.sleep_wake.z_angle import calculate_z_angle_from_arrays
from sleep_scoring_app.io.sources.gt3x_rs_loader import Gt3xRsDataSourceLoader


def calculate_cohen_kappa(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate Cohen's Kappa coefficient."""
    # Observed agreement
    po = np.mean(y_true == y_pred)

    # Expected agreement by chance
    p_true_1 = np.mean(y_true)
    p_pred_1 = np.mean(y_pred)
    pe = p_true_1 * p_pred_1 + (1 - p_true_1) * (1 - p_pred_1)

    # Kappa
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def process_gt3x_file(gt3x_path: str, autocalibrate: bool = False) -> pd.DataFrame:
    """Process a GT3X file and return 5-second epoch data with sleep scores."""
    loader = Gt3xRsDataSourceLoader(epoch_length_seconds=60, return_raw=True, autocalibrate=autocalibrate, impute_gaps=True, ism_handling="nan")

    result = loader.load_file(gt3x_path)
    df = result["activity_data"]

    # Calculate z-angle
    ax = df["AXIS_X"].to_numpy()
    ay = df["AXIS_Y"].to_numpy()
    az = df["AXIS_Z"].to_numpy()
    z_angles = calculate_z_angle_from_arrays(ax, ay, az, allow_nan=True)
    df["z_angle"] = z_angles

    # Resample to 5-second epochs using median
    df_indexed = df.set_index("timestamp")
    epoch_z = df_indexed["z_angle"].resample("5s").median()
    epoch_df = epoch_z.reset_index()
    epoch_df.columns = ["timestamp", "anglez"]

    # Run SIB classification
    algo = VanHees2015SIB(angle_threshold=5.0, time_threshold=5, epoch_length=5)
    z_angles_epoch = epoch_df["anglez"].to_numpy()
    timestamps = epoch_df["timestamp"].to_numpy()
    sleep_scores = algo._classify_sleep_wake(z_angles_epoch, timestamps)

    epoch_df["sleep_score"] = sleep_scores

    return epoch_df


def validate_against_ggir(python_df: pd.DataFrame, ggir_df: pd.DataFrame) -> dict:
    """Compare Python results against GGIR reference."""
    # Try to merge on timestamp first
    merged = pd.merge(
        python_df[["timestamp", "anglez", "sleep_score"]],
        ggir_df[["timestamp", "anglez", "sleep_score"]],
        on="timestamp",
        how="inner",
        suffixes=("_python", "_ggir"),
    )

    # If few matches, try aligning by index (both should start at same relative time)
    # This handles timezone offset differences between R and Python
    if len(merged) < min(len(python_df), len(ggir_df)) * 0.5:
        # Use shorter length
        min_len = min(len(python_df), len(ggir_df))
        merged = pd.DataFrame(
            {
                "anglez_python": python_df["anglez"].iloc[:min_len].values,
                "anglez_ggir": ggir_df["anglez"].iloc[:min_len].values,
                "sleep_score_python": python_df["sleep_score"].iloc[:min_len].values,
                "sleep_score_ggir": ggir_df["sleep_score"].iloc[:min_len].values,
            }
        )

    if len(merged) == 0:
        return {"error": "No matching epochs"}

    # Compare sleep scores
    python_scores = merged["sleep_score_python"].to_numpy()
    ggir_scores = merged["sleep_score_ggir"].to_numpy()

    agreement = np.sum(python_scores == ggir_scores)
    total = len(merged)
    accuracy = agreement / total
    kappa = calculate_cohen_kappa(ggir_scores, python_scores)

    # Compare z-angles (non-NaN only)
    valid_mask = ~merged["anglez_python"].isna() & ~merged["anglez_ggir"].isna()
    valid = merged[valid_mask]

    if len(valid) > 0:
        z_diff = valid["anglez_python"] - valid["anglez_ggir"]
        z_corr = valid["anglez_python"].corr(valid["anglez_ggir"])
    else:
        z_diff = pd.Series([0])
        z_corr = np.nan

    return {
        "matched_epochs": total,
        "agreement": agreement,
        "accuracy": accuracy,
        "kappa": kappa,
        "python_sleep_pct": np.mean(python_scores) * 100,
        "ggir_sleep_pct": np.mean(ggir_scores) * 100,
        "z_angle_mean_diff": z_diff.mean(),
        "z_angle_std_diff": z_diff.std(),
        "z_angle_correlation": z_corr,
        "valid_z_epochs": len(valid),
    }


def main():
    # Paths
    gt3x_dir = Path("D:/Scripts/monorepo/external/ggir/data")
    ggir_ref_dir = Path("D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reference")

    # Find all GT3X files
    gt3x_files = sorted(gt3x_dir.glob("*.gt3x"))

    results = []

    for gt3x_file in gt3x_files:
        filename = gt3x_file.name

        # Skip files marked as "DO NOT USE"
        if "DO NOT USE" in filename:
            continue

        try:
            # Process with Python
            python_df = process_gt3x_file(str(gt3x_file), autocalibrate=False)

            n_epochs = len(python_df)
            n_nan = python_df["anglez"].isna().sum()
            n_sleep = python_df["sleep_score"].sum()
            sleep_pct = 100 * n_sleep / n_epochs

            # Check for GGIR reference
            # Try different naming patterns
            file_stem = gt3x_file.stem
            # Convert filename to match R script output format
            # e.g., "P3-3079 (2025-08-06)" -> "P3-3079_2025-08-06"
            file_stem_clean = file_stem.replace(" ", "_").replace("(", "").replace(")", "")
            ggir_patterns = [
                ggir_ref_dir / f"{file_stem_clean}_sib.csv",
                ggir_ref_dir / f"{file_stem}_sib.csv",
                ggir_ref_dir / "ggir_sib_vanHees2015.csv",  # The existing reference file
            ]

            ggir_file = None
            for pattern in ggir_patterns:
                if pattern.exists():
                    ggir_file = pattern
                    break

            if ggir_file and ggir_file.name == "ggir_sib_vanHees2015.csv":
                # This is the TestUA reference file - only valid for that file
                if "MOS2E22180349" not in filename:
                    ggir_file = None

            if ggir_file:
                # Load GGIR reference
                ggir_df = pd.read_csv(ggir_file)
                ggir_df["timestamp"] = pd.to_datetime(ggir_df["timestamp"], format="mixed")

                # Validate
                validation = validate_against_ggir(python_df, ggir_df)

                if "error" in validation:
                    pass
                else:
                    results.append(
                        {
                            "file": filename,
                            "status": "VALIDATED",
                            "kappa": validation["kappa"],
                            "accuracy": validation["accuracy"],
                            "epochs": validation["matched_epochs"],
                        }
                    )
            else:
                results.append(
                    {
                        "file": filename,
                        "status": "NO_REFERENCE",
                        "kappa": None,
                        "accuracy": None,
                        "epochs": n_epochs,
                    }
                )

        except Exception as e:
            import traceback

            traceback.print_exc()
            results.append(
                {
                    "file": filename,
                    "status": "ERROR",
                    "kappa": None,
                    "accuracy": None,
                    "epochs": 0,
                }
            )

    # Summary

    validated = [r for r in results if r["status"] == "VALIDATED"]
    no_ref = [r for r in results if r["status"] == "NO_REFERENCE"]
    errors = [r for r in results if r["status"] == "ERROR"]

    if validated:
        for r in validated:
            kappa_str = f"{r['kappa']:.4f}" if r["kappa"] is not None else "N/A"

        # Overall stats
        kappas = [r["kappa"] for r in validated if r["kappa"] is not None]
        if kappas:
            pass

    if no_ref:
        for r in no_ref:
            pass


if __name__ == "__main__":
    main()
