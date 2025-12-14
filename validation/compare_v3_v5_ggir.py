"""Compare v3, v5 and GGIR anglez at boundary epochs."""

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

    # Get v3 (non-chunked)
    v3_anglez, *_ = gt3x_rs.process_gt3x_ggir_anglez_v3(str(gt3x_file), cal_offset=offset, cal_scale=scale)
    v3_anglez = np.array(v3_anglez)

    # Get v5 (chunked)
    v5_anglez, *_ = gt3x_rs.process_gt3x_ggir_anglez_v5(str(gt3x_file), configtz=configtz, cal_offset=offset, cal_scale=scale)
    v5_anglez = np.array(v5_anglez)

    # Compare at first few hour boundaries
    boundaries = [719, 720, 1439, 1440, 2159, 2160, 2879, 2880]

    for idx in boundaries:
        g = ggir_anglez[idx]
        v3 = v3_anglez[idx]
        v5 = v5_anglez[idx]
        d3 = v3 - g
        d5 = v5 - g

    # Check overall stats

    # Are v3 and v5 identical?
    v3_v5_diff = np.abs(v3_anglez - v5_anglez)


if __name__ == "__main__":
    main()
