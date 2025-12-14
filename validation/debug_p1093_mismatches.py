"""Debug P1-1093-A-T1 mismatches (84 epochs with Kappa=0.999180)."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


def load_ggir_calibration(cal_file: Path) -> tuple[list[float], list[float]]:
    df = pd.read_csv(cal_file)
    offset = [df["offset_x"].iloc[0], df["offset_y"].iloc[0], df["offset_z"].iloc[0]]
    scale = [df["scale_x"].iloc[0], df["scale_y"].iloc[0], df["scale_z"].iloc[0]]
    return offset, scale


def load_ggir_sib_reference(sib_file: Path) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(sib_file)
    if df["anglez"].dtype == object:
        df["anglez"] = pd.to_numeric(df["anglez"], errors="coerce")
    return df["anglez"].values, df["sleep_score"].values


def classify_sleep_wake_vanhees2015(anglez: np.ndarray) -> np.ndarray:
    """HASIB/SIB algorithm (van Hees 2015)."""
    n_epochs = len(anglez)
    sleep_scores = np.zeros(n_epochs, dtype=int)

    z_angle_diffs = np.abs(np.diff(anglez))
    posture_changes = np.where((~np.isnan(z_angle_diffs)) & (z_angle_diffs > 5.0))[0]

    if len(posture_changes) < 2:
        if len(posture_changes) < 10:
            sleep_scores[:] = 1
        return sleep_scores

    gaps_between_changes = np.diff(posture_changes)
    large_gaps = np.where(gaps_between_changes > 60)[0]

    if len(large_gaps) == 0:
        return sleep_scores

    for gap_idx in large_gaps:
        start_epoch = posture_changes[gap_idx]
        end_epoch = posture_changes[gap_idx + 1]
        sleep_scores[start_epoch : end_epoch + 1] = 1

    return sleep_scores


def main():
    import gt3x_rs

    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    ggir_batch_dir = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data")

    gt3x_locations = [
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1"),
    ]

    # Just P1-1093-A-T1
    participant_id = "P1-1093-A-T1"
    date = "2024-03-04"

    sib_file = ggir_reference_dir / f"{participant_id}_{date}_sib.csv"
    cal_file = ggir_batch_dir / f"{participant_id} ({date})" / "r_calibration.csv"

    gt3x_file = None
    for loc in gt3x_locations:
        if loc.exists():
            files = list(loc.glob(f"{participant_id}*.gt3x"))
            if files:
                gt3x_file = files[0]
                break

    if not gt3x_file:
        return

    offset, scale = load_ggir_calibration(cal_file)
    ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

    # Get Rust anglez
    rust_anglez, _sr, _ne, _ts, _te, _ng, _sa = gt3x_rs.process_gt3x_ggir_anglez_v3(str(gt3x_file), cal_offset=offset, cal_scale=scale)
    rust_anglez = np.array(rust_anglez)

    # Compute sleep scores
    ggir_sleep_computed = classify_sleep_wake_vanhees2015(ggir_anglez)
    rust_sleep = classify_sleep_wake_vanhees2015(rust_anglez)

    # Verify our algorithm matches GGIR's sleep output
    algo_match = np.sum(ggir_sleep == ggir_sleep_computed)

    # Find mismatches between rust and ggir sleep
    mismatches = np.where(ggir_sleep != rust_sleep)[0]

    # Find posture changes for both
    ggir_diffs = np.abs(np.diff(ggir_anglez))
    rust_diffs = np.abs(np.diff(rust_anglez))

    ggir_posture_changes = np.where((~np.isnan(ggir_diffs)) & (ggir_diffs > 5.0))[0]
    rust_posture_changes = np.where((~np.isnan(rust_diffs)) & (rust_diffs > 5.0))[0]

    # Find posture changes that differ
    ggir_set = set(ggir_posture_changes)
    rust_set = set(rust_posture_changes)

    only_ggir = ggir_set - rust_set
    only_rust = rust_set - ggir_set

    # Look at specific examples where posture changes differ
    if only_ggir:
        for idx in sorted(only_ggir)[:10]:
            g_diff = ggir_diffs[idx]
            r_diff = rust_diffs[idx]

    if only_rust:
        for idx in sorted(only_rust)[:10]:
            g_diff = ggir_diffs[idx]
            r_diff = rust_diffs[idx]

    # Find epochs where the diff is very close to 5.0 (boundary cases)
    boundary_ggir = np.where((ggir_diffs >= 4.99) & (ggir_diffs <= 5.01))[0]
    boundary_rust = np.where((rust_diffs >= 4.99) & (rust_diffs <= 5.01))[0]

    # For each boundary case, check if they agree
    boundary_all = set(boundary_ggir) | set(boundary_rust)
    for idx in sorted(boundary_all)[:20]:
        g_diff = ggir_diffs[idx] if idx < len(ggir_diffs) else np.nan
        r_diff = rust_diffs[idx] if idx < len(rust_diffs) else np.nan
        g_over = g_diff > 5.0
        r_over = r_diff > 5.0
        match = "✓" if g_over == r_over else "✗"


if __name__ == "__main__":
    main()
