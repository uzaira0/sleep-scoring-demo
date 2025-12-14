"""Debug epoch count: check GT3X file time range vs GGIR output."""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    gt3x_file = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1/P1-1024-A-T1 (2023-07-18).gt3x")
    ggir_anglez_file = Path(__file__).parent / "ggir_reference/P1-1024-A-T1_2023-07-18_anglez.csv"

    # Parse GGIR timestamps
    ggir_df = pd.read_csv(ggir_anglez_file)
    ggir_start = pd.to_datetime(ggir_df["timestamp"].iloc[0])
    ggir_end = pd.to_datetime(ggir_df["timestamp"].iloc[-1])
    ggir_duration = (ggir_end - ggir_start).total_seconds()

    # Load GT3X metadata
    import gt3x_rs

    data = gt3x_rs.parse_gt3x(str(gt3x_file))

    # Check timestamps
    if len(data.timestamps) > 0:
        # Timestamps are in microseconds from epoch
        ts_start = data.timestamps[0] / 1e6  # Convert to seconds
        ts_end = data.timestamps[-1] / 1e6

        # Convert to datetime (assuming Unix epoch)
        dt_start = datetime.utcfromtimestamp(ts_start)
        dt_end = datetime.utcfromtimestamp(ts_end)

    # Load metadata from GT3X
    metadata = gt3x_rs.parse_gt3x_metadata(str(gt3x_file))
    for key in metadata.data:
        if "time" in key.lower() or "date" in key.lower() or "start" in key.lower() or "stop" in key.lower():
            pass

    # Calculate epochs using GGIR's exact formula
    sf = data.sample_rate
    epochsize = 5
    samples_per_epoch = sf * epochsize

    # GGIR formula from averagePerEpoch:
    # x2 = cumsum(c(0, x))  # length = n + 1
    # select = seq(1, length(x2), by = sf * epochsize)  # R 1-indexed
    # Number of epochs = length(select) - 1

    n = len(data.x)
    x2_len = n + 1

    # R's seq(1, x2_len, by=150)
    # In R: seq(1, 100, by=30) gives [1, 31, 61, 91] - 4 elements
    # Number of elements = floor((end - start) / by) + 1
    select_len = ((x2_len - 1) // samples_per_epoch) + 1
    num_epochs = select_len - 1

    # Compare

    # What if GGIR truncates based on end time?
    # GGIR aligns to hour boundaries and may truncate

    # Check first timestamp alignment


if __name__ == "__main__":
    main()
