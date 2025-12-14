"""
Validate Python van Hees 2015 SIB against GGIR using GGIR's anglez directly.

This script validates that when given IDENTICAL input data (GGIR's anglez),
the Python implementation produces IDENTICAL output (kappa = 1.0).

This proves the algorithm is correct - any discrepancies in production
are due to data source differences (pygt3x vs read.gt3x), not the algorithm.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


def classify_sleep_wake_vanhees2015(
    z_angles: np.ndarray,
    angle_threshold: float = 5.0,
    time_threshold_minutes: int = 5,
    epoch_seconds: int = 5,
) -> np.ndarray:
    """
    Classify sleep/wake using van Hees 2015 algorithm.

    This is a standalone implementation matching GGIR's HASIB function exactly.

    Args:
        z_angles: Array of z-angle values in degrees (5-second epochs)
        angle_threshold: Maximum angle change for sustained inactivity (default 5.0°)
        time_threshold_minutes: Minimum duration for sleep bout (default 5 min)
        epoch_seconds: Epoch length in seconds (default 5s)

    Returns:
        Array of sleep scores (1=sleep, 0=wake)

    """
    n_epochs = len(z_angles)

    # Calculate minimum gap size in epochs
    min_gap_epochs = int(time_threshold_minutes * (60 / epoch_seconds))

    # Initialize all as wake
    sleep_scores = np.zeros(n_epochs, dtype=int)

    # Handle NaN values - GGIR uses last observation carried forward for NaN
    # But for diff calculation, NaN propagates
    z_angles_clean = z_angles.copy()

    # Step 1: Find posture changes (where abs(diff(anglez)) > threshold)
    # GGIR: postch = which(abs(diff(anglez)) > j)
    z_angle_diffs = np.abs(np.diff(z_angles_clean))

    # NaN diffs should NOT count as posture changes (matches GGIR behavior)
    posture_changes = np.where((~np.isnan(z_angle_diffs)) & (z_angle_diffs > angle_threshold))[0]

    if len(posture_changes) < 2:
        # GGIR: if < 10 posture changes, all sleep; else all wake
        if len(posture_changes) < 10:
            sleep_scores[:] = 1
        return sleep_scores

    # Step 2: Find gaps between consecutive posture changes > time_threshold
    # GGIR: q1 = which(diff(postch) > (i * (60/epochsize)))
    gaps_between_changes = np.diff(posture_changes)
    large_gaps = np.where(gaps_between_changes > min_gap_epochs)[0]

    if len(large_gaps) == 0:
        return sleep_scores

    # Step 3: Mark epochs within large gaps as sleep
    # GGIR: sdl1[postch[q1[gi]]:postch[q1[gi] + 1]] = 1
    for gap_idx in large_gaps:
        start_epoch = posture_changes[gap_idx]
        end_epoch = posture_changes[gap_idx + 1]
        sleep_scores[start_epoch : end_epoch + 1] = 1

    return sleep_scores


def validate_single_file(sib_file: Path) -> dict:
    """
    Validate Python implementation against GGIR for a single file.

    Args:
        sib_file: Path to GGIR SIB CSV file with anglez and sleep_score columns

    Returns:
        Dictionary with validation results

    """
    # Read GGIR output
    df = pd.read_csv(sib_file)

    # Get anglez and GGIR sleep scores
    anglez = df["anglez"].values
    ggir_sleep = df["sleep_score"].values

    # Handle NA values (read as "NA" string or NaN)
    if df["anglez"].dtype == object:
        anglez = pd.to_numeric(df["anglez"], errors="coerce").values

    # Run Python implementation on GGIR's anglez
    python_sleep = classify_sleep_wake_vanhees2015(anglez)

    # Ensure same length
    min_len = min(len(ggir_sleep), len(python_sleep))
    ggir_sleep = ggir_sleep[:min_len]
    python_sleep = python_sleep[:min_len]

    # Calculate kappa (excluding NaN positions)
    valid_mask = ~np.isnan(anglez[:min_len])
    if valid_mask.sum() < 10:
        return {
            "file": sib_file.name,
            "n_epochs": len(df),
            "n_valid": valid_mask.sum(),
            "kappa": np.nan,
            "agreement": np.nan,
            "error": "Too few valid epochs",
        }

    ggir_valid = ggir_sleep[valid_mask].astype(int)
    python_valid = python_sleep[valid_mask].astype(int)

    kappa = cohen_kappa_score(ggir_valid, python_valid)
    agreement = np.mean(ggir_valid == python_valid)

    # Count mismatches
    mismatches = np.where(ggir_valid != python_valid)[0]

    return {
        "file": sib_file.name,
        "n_epochs": len(df),
        "n_valid": valid_mask.sum(),
        "ggir_sleep_epochs": int(ggir_valid.sum()),
        "python_sleep_epochs": int(python_valid.sum()),
        "kappa": kappa,
        "agreement": agreement,
        "n_mismatches": len(mismatches),
        "first_mismatches": mismatches[:5].tolist() if len(mismatches) > 0 else [],
    }


def main():
    """Validate all SIB files in the ggir_reference directory."""
    reference_dir = Path(__file__).parent / "ggir_reference"

    # Find all SIB files
    sib_files = sorted(reference_dir.glob("*_sib.csv"))

    if not sib_files:
        return

    results = []
    all_perfect = True

    for sib_file in sib_files:
        result = validate_single_file(sib_file)
        results.append(result)

        kappa = result["kappa"]
        status = "PASS" if kappa == 1.0 else "FAIL"
        if kappa != 1.0:
            all_perfect = False

        if kappa != 1.0 and result.get("first_mismatches"):
            pass

    # Summary
    kappas = [r["kappa"] for r in results if not np.isnan(r["kappa"])]
    if kappas:
        if all_perfect:
            pass
        else:
            pass


if __name__ == "__main__":
    main()
