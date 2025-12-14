"""Test v5 chunk-based processing for P1-1093-A-T1 to verify Kappa=1.0."""

from pathlib import Path

import gt3x_rs
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


def load_ggir_calibration(cal_file: Path) -> tuple[list[float], list[float]]:
    df = pd.read_csv(cal_file)
    return (
        [df["offset_x"].iloc[0], df["offset_y"].iloc[0], df["offset_z"].iloc[0]],
        [df["scale_x"].iloc[0], df["scale_y"].iloc[0], df["scale_z"].iloc[0]],
    )


def load_ggir_sib_reference(sib_file: Path) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(sib_file)
    if df["anglez"].dtype == object:
        df["anglez"] = pd.to_numeric(df["anglez"], errors="coerce")
    return df["anglez"].values, df["sleep_score"].values


def classify_sleep_wake_vanhees2015(anglez: np.ndarray) -> np.ndarray:
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
        sleep_scores[posture_changes[gap_idx] : posture_changes[gap_idx + 1] + 1] = 1
    return sleep_scores


def main():
    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    ggir_batch_dir = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data")
    gt3x_dir = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1")

    participant_id = "P1-1093-A-T1"
    date = "2024-03-04"
    configtz = "America/Chicago"

    sib_file = ggir_reference_dir / f"{participant_id}_{date}_sib.csv"
    cal_file = ggir_batch_dir / f"{participant_id} ({date})" / "r_calibration.csv"
    gt3x_file = next(gt3x_dir.glob(f"{participant_id}*.gt3x"), None)

    if not gt3x_file:
        return

    offset, scale = load_ggir_calibration(cal_file)
    _ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

    # Test v5 (chunked) only
    v5_anglez, *_ = gt3x_rs.process_gt3x_ggir_anglez_v5(str(gt3x_file), configtz=configtz, cal_offset=offset, cal_scale=scale)
    v5_anglez = np.array(v5_anglez)

    v5_sleep = classify_sleep_wake_vanhees2015(v5_anglez)
    v5_kappa = cohen_kappa_score(ggir_sleep, v5_sleep)
    v5_matches = np.sum(ggir_sleep == v5_sleep)

    if v5_kappa == 1.0:
        pass
    else:
        pass


if __name__ == "__main__":
    main()
