"""Quick test of v4 DST handling on P1-1078-A-T1."""

from pathlib import Path

import numpy as np
import pandas as pd


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
    from sklearn.metrics import cohen_kappa_score

    # P1-1078-A-T1 - the DST file (Nov 5, 2023 is when DST ends in America/Chicago)
    gt3x_file = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1/P1-1078-A-T1 (2023-11-08).gt3x")
    sib_file = Path(__file__).parent / "ggir_reference" / "P1-1078-A-T1_2023-11-08_sib.csv"
    cal_file = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data/P1-1078-A-T1 (2023-11-08)/r_calibration.csv")

    if not gt3x_file.exists():
        return 1
    if not sib_file.exists():
        return 1
    if not cal_file.exists():
        return 1

    offset, scale = load_ggir_calibration(cal_file)
    ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

    # Test v3 (no DST handling)
    try:
        (
            rust_anglez_v3,
            sample_rate,
            num_epochs,
            trunc_start,
            trunc_end,
            num_gaps,
            samples_added,
        ) = gt3x_rs.process_gt3x_ggir_anglez_v3(
            str(gt3x_file),
            cal_offset=offset,
            cal_scale=scale,
        )
        rust_anglez_v3 = np.array(rust_anglez_v3)

        # Compute Kappa for v3
        min_len = min(len(rust_anglez_v3), len(ggir_anglez))
        valid = ~np.isnan(ggir_anglez[:min_len]) & ~np.isnan(rust_anglez_v3[:min_len])
        rs_v3 = classify_sleep_wake_vanhees2015(rust_anglez_v3[:min_len])
        kappa_v3 = cohen_kappa_score(ggir_sleep[:min_len][valid].astype(int), rs_v3[valid].astype(int))
    except Exception as e:
        kappa_v3 = None

    # Test v4 (with DST handling)
    try:
        (
            rust_anglez_v4,
            _sample_rate,
            _num_epochs,
            _trunc_start,
            _trunc_end,
            _num_gaps,
            _samples_added,
            _dst_gaps,
        ) = gt3x_rs.process_gt3x_ggir_anglez_v4(
            str(gt3x_file),
            configtz="America/Chicago",
            cal_offset=offset,
            cal_scale=scale,
        )
        rust_anglez_v4 = np.array(rust_anglez_v4)

        # Compute Kappa for v4
        epochs_match = len(rust_anglez_v4) == len(ggir_anglez)
        if epochs_match:
            valid = ~np.isnan(ggir_anglez) & ~np.isnan(rust_anglez_v4)
            rs_v4 = classify_sleep_wake_vanhees2015(rust_anglez_v4)
            kappa_v4 = cohen_kappa_score(ggir_sleep[valid].astype(int), rs_v4[valid].astype(int))
        else:
            min_len = min(len(rust_anglez_v4), len(ggir_anglez))
            valid = ~np.isnan(ggir_anglez[:min_len]) & ~np.isnan(rust_anglez_v4[:min_len])
            rs_v4 = classify_sleep_wake_vanhees2015(rust_anglez_v4[:min_len])
            kappa_v4 = cohen_kappa_score(ggir_sleep[:min_len][valid].astype(int), rs_v4[valid].astype(int))
    except Exception as e:
        import traceback

        traceback.print_exc()
        kappa_v4 = None

    if kappa_v4 == 1.0:
        return 0
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
