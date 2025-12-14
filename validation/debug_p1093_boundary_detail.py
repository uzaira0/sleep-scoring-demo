"""Debug P1-1093-A-T1 - examine anglez values around day boundaries in detail."""

from pathlib import Path

import numpy as np
import pandas as pd


def load_ggir_sib_reference(sib_file: Path) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(sib_file)
    if df["anglez"].dtype == object:
        df["anglez"] = pd.to_numeric(df["anglez"], errors="coerce")
    return df["anglez"].values, df["sleep_score"].values


def load_ggir_calibration(cal_file: Path) -> tuple[list[float], list[float]]:
    df = pd.read_csv(cal_file)
    offset = [df["offset_x"].iloc[0], df["offset_y"].iloc[0], df["offset_z"].iloc[0]]
    scale = [df["scale_x"].iloc[0], df["scale_y"].iloc[0], df["scale_z"].iloc[0]]
    return offset, scale


def main():
    import gt3x_rs

    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    ggir_batch_dir = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data")

    gt3x_locations = [
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1"),
    ]

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
    ggir_anglez, _ = load_ggir_sib_reference(sib_file)

    # Get Rust anglez
    rust_anglez, _sr, _ne, _ts, _te, _ng, _sa = gt3x_rs.process_gt3x_ggir_anglez_v3(str(gt3x_file), cal_offset=offset, cal_scale=scale)
    rust_anglez = np.array(rust_anglez)

    # Calculate epochs per day
    epochs_per_day = 24 * 60 * 60 // 5  # 17280 epochs per day

    # Problem epochs and their day positions
    problem_epochs = [69120, 86399, 138239, 172798, 190078, 190079, 207358, 207359]

    for epoch in problem_epochs:
        day = epoch // epochs_per_day
        epoch_in_day = epoch % epochs_per_day

        # Show context around the epoch
        start = max(0, epoch - 3)
        end = min(len(ggir_anglez), epoch + 4)

        for i in range(start, end):
            g = ggir_anglez[i]
            r = rust_anglez[i]
            diff = g - r
            flag = "***" if abs(diff) > 0.1 else ""
            marker = " <--" if i == epoch else ""

    # Look for pattern: are all mismatches at specific epoch positions within days?

    diff = np.abs(ggir_anglez - rust_anglez)
    large_diff_idx = np.where(diff > 0.5)[0]

    if len(large_diff_idx) > 0:
        epoch_in_day_positions = [idx % epochs_per_day for idx in large_diff_idx]
        unique_positions = sorted(set(epoch_in_day_positions))

        for idx in large_diff_idx[:30]:
            day = idx // epochs_per_day
            pos = idx % epochs_per_day
            g = ggir_anglez[idx]
            r = rust_anglez[idx]

    # Check if the problem is at the LAST epoch of each "chunk" (if GGIR processes in chunks)

    # GGIR might process in ws2 chunks (900 seconds = 180 epochs)
    ws2_epochs = 900 // 5  # 180 epochs

    # Or ws (3600 seconds = 720 epochs)
    ws_epochs = 3600 // 5  # 720 epochs

    for idx in large_diff_idx[:20]:
        mod_180 = idx % ws2_epochs
        mod_720 = idx % ws_epochs


if __name__ == "__main__":
    main()
