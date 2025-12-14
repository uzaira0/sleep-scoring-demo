"""Debug v5 anglez differences."""

from pathlib import Path

import gt3x_rs
import numpy as np
import pandas as pd


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

    offset, scale = load_ggir_calibration(cal_file)
    ggir_anglez, _ = load_ggir_sib_reference(sib_file)

    v5_anglez, *_ = gt3x_rs.process_gt3x_ggir_anglez_v5(str(gt3x_file), configtz=configtz, cal_offset=offset, cal_scale=scale)
    v5_anglez = np.array(v5_anglez)

    diff = np.abs(ggir_anglez - v5_anglez)
    large_diff_idx = np.where(diff > 0.1)[0]

    epochs_per_hour = 720  # 3600 / 5
    epochs_per_day = 17280  # 86400 / 5

    for idx in large_diff_idx[:50]:
        hour_boundary = idx % epochs_per_hour
        day = idx // epochs_per_day
        pos_in_day = idx % epochs_per_day


if __name__ == "__main__":
    main()
