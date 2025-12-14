"""
Validate HASIB using Rust-computed calibrated anglez vs GGIR reference.

This is the END-TO-END validation:
1. Load GT3X with Rust (gt3x-rs)
2. Apply GGIR calibration coefficients
3. Compute anglez (rolling median + epoch averaging)
4. Run HASIB/SIB algorithm
5. Compare against GGIR's sleep_score (target: Kappa = 1.0)
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


def load_ggir_calibration(cal_file: Path) -> tuple[list[float], list[float]]:
    """Load GGIR calibration coefficients from r_calibration.csv."""
    df = pd.read_csv(cal_file)
    # Format: scale_x, scale_y, scale_z, offset_x, offset_y, offset_z, cal_error
    offset = [df["offset_x"].iloc[0], df["offset_y"].iloc[0], df["offset_z"].iloc[0]]
    scale = [df["scale_x"].iloc[0], df["scale_y"].iloc[0], df["scale_z"].iloc[0]]
    return offset, scale


def load_ggir_sib_reference(sib_file: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load GGIR anglez and sleep_score from SIB CSV."""
    df = pd.read_csv(sib_file)

    # Handle NA values
    if df["anglez"].dtype == object:
        df["anglez"] = pd.to_numeric(df["anglez"], errors="coerce")

    return df["anglez"].values, df["sleep_score"].values


def classify_sleep_wake_vanhees2015(
    anglez: np.ndarray,
    angle_threshold: float = 5.0,
    time_threshold_minutes: int = 5,
    epoch_seconds: int = 5,
) -> np.ndarray:
    """
    Classify sleep/wake using van Hees 2015 HASIB algorithm.

    This matches GGIR's HASIB implementation exactly.
    """
    n_epochs = len(anglez)
    min_gap_epochs = int(time_threshold_minutes * (60 / epoch_seconds))

    # Initialize all as wake
    sleep_scores = np.zeros(n_epochs, dtype=int)

    # Step 1: Find posture changes (abs(diff(anglez)) > threshold)
    z_angle_diffs = np.abs(np.diff(anglez))

    # NaN diffs should NOT count as posture changes
    posture_changes = np.where((~np.isnan(z_angle_diffs)) & (z_angle_diffs > angle_threshold))[0]

    if len(posture_changes) < 2:
        if len(posture_changes) < 10:
            sleep_scores[:] = 1
        return sleep_scores

    # Step 2: Find gaps between consecutive posture changes > time_threshold
    gaps_between_changes = np.diff(posture_changes)
    large_gaps = np.where(gaps_between_changes > min_gap_epochs)[0]

    if len(large_gaps) == 0:
        return sleep_scores

    # Step 3: Mark epochs within large gaps as sleep
    for gap_idx in large_gaps:
        start_epoch = posture_changes[gap_idx]
        end_epoch = posture_changes[gap_idx + 1]
        sleep_scores[start_epoch : end_epoch + 1] = 1

    return sleep_scores


def find_matching_files(
    ggir_reference_dir: Path,
    ggir_batch_dir: Path,
    gt3x_dir: Path,
) -> list[dict]:
    """Find matching GT3X files, GGIR calibration, and GGIR SIB reference."""
    matches = []

    # Find all SIB reference files
    sib_files = sorted(ggir_reference_dir.glob("P1-*_sib.csv"))

    for sib_file in sib_files:
        # Parse filename: P1-1024-A-T1_2023-07-18_sib.csv
        name = sib_file.stem.replace("_sib", "")
        parts = name.split("_")
        if len(parts) != 2:
            continue

        participant_id = parts[0]  # P1-1024-A-T1
        date = parts[1]  # 2023-07-18

        # Find calibration file in GGIR batch output
        cal_dir_pattern = f"{participant_id} ({date})"
        cal_dirs = list(ggir_batch_dir.glob(cal_dir_pattern))

        if not cal_dirs:
            continue

        cal_file = cal_dirs[0] / "r_calibration.csv"
        if not cal_file.exists():
            continue

        # Find GT3X file
        gt3x_pattern = f"{participant_id}*.gt3x"
        gt3x_files = list(gt3x_dir.glob(gt3x_pattern))

        if not gt3x_files:
            continue

        matches.append(
            {
                "participant_id": participant_id,
                "date": date,
                "sib_file": sib_file,
                "cal_file": cal_file,
                "gt3x_file": gt3x_files[0],
            }
        )

    return matches


def validate_single_file(
    gt3x_file: Path,
    cal_file: Path,
    sib_file: Path,
) -> dict:
    """Validate Rust anglez + HASIB against GGIR reference for a single file."""
    import gt3x_rs

    # Load calibration
    offset, scale = load_ggir_calibration(cal_file)

    # Load GGIR reference
    ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

    # Process with Rust (calibrated anglez)
    try:
        rust_anglez, _timestamps, _sample_rate, _num_epochs, num_na, _num_gaps, _samples_added = gt3x_rs.process_gt3x_ggir_anglez_calibrated(
            str(gt3x_file),
            cal_offset=offset,
            cal_scale=scale,
            impute_k=0.25,
            epoch_seconds=5.0,
        )
        rust_anglez = np.array(rust_anglez)
    except Exception as e:
        return {
            "error": str(e),
            "kappa": np.nan,
        }

    # Run HASIB on Rust anglez
    rust_sleep = classify_sleep_wake_vanhees2015(rust_anglez)

    # Align lengths (use minimum)
    min_len = min(len(ggir_sleep), len(rust_sleep), len(ggir_anglez), len(rust_anglez))

    ggir_anglez_aligned = ggir_anglez[:min_len]
    ggir_sleep_aligned = ggir_sleep[:min_len]
    rust_anglez_aligned = rust_anglez[:min_len]
    rust_sleep_aligned = rust_sleep[:min_len]

    # Create valid mask (exclude NaN epochs)
    valid_mask = ~np.isnan(ggir_anglez_aligned) & ~np.isnan(rust_anglez_aligned)
    n_valid = valid_mask.sum()

    if n_valid < 100:
        return {
            "error": "Too few valid epochs",
            "n_valid": n_valid,
            "kappa": np.nan,
        }

    # Calculate anglez comparison
    anglez_corr = np.corrcoef(ggir_anglez_aligned[valid_mask], rust_anglez_aligned[valid_mask])[0, 1]
    anglez_mae = np.mean(np.abs(ggir_anglez_aligned[valid_mask] - rust_anglez_aligned[valid_mask]))

    # Calculate HASIB kappa
    ggir_valid = ggir_sleep_aligned[valid_mask].astype(int)
    rust_valid = rust_sleep_aligned[valid_mask].astype(int)

    kappa = cohen_kappa_score(ggir_valid, rust_valid)
    agreement = np.mean(ggir_valid == rust_valid)

    # Count mismatches
    mismatches = np.where(ggir_valid != rust_valid)[0]

    return {
        "n_epochs_ggir": len(ggir_sleep),
        "n_epochs_rust": len(rust_sleep),
        "n_valid": n_valid,
        "n_na_rust": num_na,
        "anglez_correlation": anglez_corr,
        "anglez_mae": anglez_mae,
        "ggir_sleep_epochs": int(ggir_valid.sum()),
        "rust_sleep_epochs": int(rust_valid.sum()),
        "kappa": kappa,
        "agreement": agreement,
        "n_mismatches": len(mismatches),
    }


def main():
    """Main validation: Rust anglez + HASIB vs GGIR reference."""
    # Paths
    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    ggir_batch_dir = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data")
    gt3x_dir = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1")

    # Check paths
    if not ggir_reference_dir.exists():
        return 1

    if not ggir_batch_dir.exists():
        return 1

    if not gt3x_dir.exists():
        # Try T2, T3
        for t in ["T2", "T3"]:
            alt_dir = gt3x_dir.parent / t
            if alt_dir.exists():
                gt3x_dir = alt_dir
                break

    # Find matching files
    matches = find_matching_files(ggir_reference_dir, ggir_batch_dir, gt3x_dir)

    if not matches:
        # Fall back to direct SIB file validation with manual GT3X search
        sib_files = sorted(ggir_reference_dir.glob("P1-*_sib.csv"))[:5]

        for sib_file in sib_files:
            name = sib_file.stem.replace("_sib", "")
            parts = name.split("_")
            if len(parts) != 2:
                continue

            participant_id = parts[0]
            date = parts[1]

            # Search for GT3X in multiple locations
            gt3x_locations = [
                Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1"),
                Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T2"),
                Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T3"),
            ]

            gt3x_file = None
            for loc in gt3x_locations:
                if loc.exists():
                    files = list(loc.glob(f"{participant_id}*.gt3x"))
                    if files:
                        gt3x_file = files[0]
                        break

            if gt3x_file:
                cal_dir_pattern = f"{participant_id} ({date})"
                cal_dirs = list(ggir_batch_dir.glob(cal_dir_pattern))
                if cal_dirs:
                    cal_file = cal_dirs[0] / "r_calibration.csv"
                    if cal_file.exists():
                        matches.append(
                            {
                                "participant_id": participant_id,
                                "date": date,
                                "sib_file": sib_file,
                                "cal_file": cal_file,
                                "gt3x_file": gt3x_file,
                            }
                        )

    if not matches:
        return 1

    # Validate each file
    results = []

    for match in matches:
        result = validate_single_file(
            match["gt3x_file"],
            match["cal_file"],
            match["sib_file"],
        )
        result["participant_id"] = match["participant_id"]
        result["date"] = match["date"]
        results.append(result)

        if "error" in result:
            pass
        else:
            kappa = result["kappa"]
            corr = result["anglez_correlation"]
            status = "PASS" if kappa == 1.0 else "FAIL"

    # Summary
    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        kappas = [r["kappa"] for r in valid_results]
        corrs = [r["anglez_correlation"] for r in valid_results]

        if all(k == 1.0 for k in kappas):
            return 0
        # Show details for failures
        for r in valid_results:
            if r["kappa"] != 1.0:
                pass
        return 1
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
