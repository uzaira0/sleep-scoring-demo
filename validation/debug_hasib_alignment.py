"""
Debug HASIB alignment issues between Rust and GGIR anglez.

Investigates:
1. Epoch count differences
2. Offset alignment
3. NA epoch handling
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


def load_ggir_calibration(cal_file: Path) -> tuple[list[float], list[float]]:
    """Load GGIR calibration coefficients."""
    df = pd.read_csv(cal_file)
    offset = [df["offset_x"].iloc[0], df["offset_y"].iloc[0], df["offset_z"].iloc[0]]
    scale = [df["scale_x"].iloc[0], df["scale_y"].iloc[0], df["scale_z"].iloc[0]]
    return offset, scale


def load_ggir_sib_reference(sib_file: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load GGIR anglez and sleep_score from SIB CSV."""
    df = pd.read_csv(sib_file)
    if df["anglez"].dtype == object:
        df["anglez"] = pd.to_numeric(df["anglez"], errors="coerce")
    return df["anglez"].values, df["sleep_score"].values


def classify_sleep_wake_vanhees2015(anglez: np.ndarray) -> np.ndarray:
    """HASIB algorithm."""
    n_epochs = len(anglez)
    sleep_scores = np.zeros(n_epochs, dtype=int)

    z_angle_diffs = np.abs(np.diff(anglez))
    posture_changes = np.where((~np.isnan(z_angle_diffs)) & (z_angle_diffs > 5.0))[0]

    if len(posture_changes) < 2:
        if len(posture_changes) < 10:
            sleep_scores[:] = 1
        return sleep_scores

    gaps_between_changes = np.diff(posture_changes)
    large_gaps = np.where(gaps_between_changes > 60)[0]  # 5 min = 60 epochs at 5s

    if len(large_gaps) == 0:
        return sleep_scores

    for gap_idx in large_gaps:
        start_epoch = posture_changes[gap_idx]
        end_epoch = posture_changes[gap_idx + 1]
        sleep_scores[start_epoch : end_epoch + 1] = 1

    return sleep_scores


def find_best_offset(ggir_anglez: np.ndarray, rust_anglez: np.ndarray, max_offset: int = 10) -> dict:
    """Find the offset that maximizes correlation."""
    best_offset = 0
    best_corr = -1

    for offset in range(-max_offset, max_offset + 1):
        if offset < 0:
            g = ggir_anglez[-offset:]
            r = rust_anglez[: len(g)]
        elif offset > 0:
            r = rust_anglez[offset:]
            g = ggir_anglez[: len(r)]
        else:
            g = ggir_anglez
            r = rust_anglez

        min_len = min(len(g), len(r))
        g = g[:min_len]
        r = r[:min_len]

        valid = ~np.isnan(g) & ~np.isnan(r)
        if valid.sum() < 100:
            continue

        corr = np.corrcoef(g[valid], r[valid])[0, 1]
        if corr > best_corr:
            best_corr = corr
            best_offset = offset

    return {"offset": best_offset, "correlation": best_corr}


def debug_file(participant_id: str, date: str):
    """Debug a specific file."""
    import gt3x_rs

    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    ggir_batch_dir = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data")

    # Find files
    sib_file = ggir_reference_dir / f"{participant_id}_{date}_sib.csv"
    cal_dir = ggir_batch_dir / f"{participant_id} ({date})"
    cal_file = cal_dir / "r_calibration.csv"

    # Find GT3X
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

    if not gt3x_file:
        return

    # Load data
    offset, scale = load_ggir_calibration(cal_file)
    ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

    # Process with Rust
    rust_anglez, _timestamps, _sample_rate, _num_epochs, _num_na, _num_gaps, _samples_added = gt3x_rs.process_gt3x_ggir_anglez_calibrated(
        str(gt3x_file),
        cal_offset=offset,
        cal_scale=scale,
    )
    rust_anglez = np.array(rust_anglez)

    # Count NA in GGIR
    ggir_na = np.isnan(ggir_anglez).sum()

    # Find best alignment
    alignment = find_best_offset(ggir_anglez, rust_anglez)

    # Apply offset and compute kappa
    offset_val = alignment["offset"]
    if offset_val < 0:
        g = ggir_anglez[-offset_val:]
        r = rust_anglez[: len(g)]
        gs = ggir_sleep[-offset_val:]
    elif offset_val > 0:
        r = rust_anglez[offset_val:]
        g = ggir_anglez[: len(r)]
        gs = ggir_sleep[: len(r)]
    else:
        g = ggir_anglez
        r = rust_anglez
        gs = ggir_sleep

    min_len = min(len(g), len(r), len(gs))
    g = g[:min_len]
    r = r[:min_len]
    gs = gs[:min_len]

    # Run HASIB on aligned Rust anglez
    rs = classify_sleep_wake_vanhees2015(r)

    valid = ~np.isnan(g) & ~np.isnan(r)

    kappa = cohen_kappa_score(gs[valid].astype(int), rs[valid].astype(int))
    agreement = np.mean(gs[valid] == rs[valid])

    # Show first few differences
    mismatches = np.where(gs[valid] != rs[valid])[0]
    if len(mismatches) > 0:
        for i in mismatches[:10]:
            pass

    # Compare with no offset
    min_len = min(len(ggir_anglez), len(rust_anglez))
    g_raw = ggir_anglez[:min_len]
    r_raw = rust_anglez[:min_len]
    gs_raw = ggir_sleep[:min_len]
    rs_raw = classify_sleep_wake_vanhees2015(r_raw)

    valid_raw = ~np.isnan(g_raw) & ~np.isnan(r_raw)

    kappa_raw = cohen_kappa_score(gs_raw[valid_raw].astype(int), rs_raw[valid_raw].astype(int))
    corr_raw = np.corrcoef(g_raw[valid_raw], r_raw[valid_raw])[0, 1]

    # Check if using GGIR anglez directly gives kappa=1
    python_sleep_on_ggir = classify_sleep_wake_vanhees2015(ggir_anglez)
    valid_ggir = ~np.isnan(ggir_anglez)
    kappa_sanity = cohen_kappa_score(ggir_sleep[valid_ggir].astype(int), python_sleep_on_ggir[valid_ggir].astype(int))


def main():
    # Debug the file with lower correlation
    debug_file("P1-1024-A-T1", "2023-07-18")

    debug_file("P1-1078-A-T1", "2023-11-08")


if __name__ == "__main__":
    main()
