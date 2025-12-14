"""Debug P1-1093-A-T1 - check if mismatches are at time gap boundaries."""

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

    _offset, _scale = load_ggir_calibration(cal_file)

    # Parse GT3X to get raw data info
    data = gt3x_rs.parse_gt3x(str(gt3x_file))

    timestamps = np.array(data.timestamps)

    # Check for time gaps in raw data
    TIME_UNIT = 100.0  # GGIR timestamps in hundredths of seconds
    ts_seconds = timestamps / TIME_UNIT
    ts_diffs = np.diff(ts_seconds)

    # Find gaps >= 0.25 seconds
    gaps = np.where(ts_diffs >= 0.25)[0]

    if len(gaps) > 0:
        for i, gap_idx in enumerate(gaps[:20]):
            gap_size = ts_diffs[gap_idx]
            # Convert sample index to epoch index (sample / sample_rate / epoch_seconds)
            epoch_idx = int(gap_idx / data.sample_rate / 5)

    # The problematic epochs from previous output
    problem_epochs = [69120, 86399, 138239, 172798, 190078, 190079, 207358, 207359]

    for epoch in problem_epochs:
        # Convert epoch to approximate sample index
        sample_start = epoch * 5 * int(data.sample_rate)
        sample_end = sample_start + 5 * int(data.sample_rate)

        # Check if any gaps fall within this epoch's samples
        gaps_in_epoch = [g for g in gaps if sample_start <= g < sample_end]

        # Also check gaps just before or after
        nearby_gaps = [g for g in gaps if sample_start - 150 <= g < sample_end + 150]

        # Convert epoch to time
        hours = epoch * 5 / 3600
        days = hours / 24

        if nearby_gaps:
            for g in nearby_gaps[:3]:
                pass


if __name__ == "__main__":
    main()
