"""Debug chunk alignment - find where GGIR's chunks actually start."""

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

    # Get info about what v5 returns for truncation
    v5_anglez, sr, _ne, trunc_start, _trunc_end, _ng, _sa, _dst = gt3x_rs.process_gt3x_ggir_anglez_v5(
        str(gt3x_file), configtz=configtz, cal_offset=offset, cal_scale=scale
    )
    v5_anglez = np.array(v5_anglez)

    # Calculate where the chunk boundaries should be relative to epochs
    samples_per_epoch = int(sr * 5)  # 5 second epochs
    samples_per_chunk = int(sr * 3600)  # 1 hour chunks
    epochs_per_chunk = 720  # 3600 / 5

    # After truncation, the first sample is at trunc_start
    # So the first chunk boundary in the output is at epoch 0
    # But GGIR's first chunk might not start at the aligned boundary

    # The offset in epochs from the start of the raw data
    epoch_offset = trunc_start // samples_per_epoch

    # So the chunk boundaries in raw data would be at:
    # raw_chunk_boundary = k * epochs_per_chunk (for k = 0, 1, 2, ...)
    # output_chunk_boundary = raw_chunk_boundary - epoch_offset

    # Find where the large differences are
    diff = np.abs(ggir_anglez - v5_anglez)
    large_diff_idx = np.where(diff > 1.0)[0]

    for idx in large_diff_idx[:20]:
        # Check what position this is relative to raw chunk boundaries
        raw_epoch_pos = idx + epoch_offset
        chunk_pos = raw_epoch_pos % epochs_per_chunk


if __name__ == "__main__":
    main()
