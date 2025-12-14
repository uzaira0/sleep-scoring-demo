"""Debug epoch count calculation difference between GGIR and Rust."""

from pathlib import Path

import numpy as np
import pandas as pd


def main():
    # Test file: P1-1024-A-T1
    gt3x_file = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1/P1-1024-A-T1 (2023-07-18).gt3x")
    ggir_sib_file = Path(__file__).parent / "ggir_reference/P1-1024-A-T1_2023-07-18_sib.csv"
    ggir_anglez_file = Path(__file__).parent / "ggir_reference/P1-1024-A-T1_2023-07-18_anglez.csv"

    # Load GGIR reference
    ggir_sib = pd.read_csv(ggir_sib_file)

    if ggir_anglez_file.exists():
        ggir_anglez = pd.read_csv(ggir_anglez_file)

    # Load with gt3x-rs and check raw sample counts
    import gt3x_rs

    # First, load raw data without anglez processing
    data = gt3x_rs.load_gt3x_ggir_compat(str(gt3x_file))

    # Check imputation
    imputed = gt3x_rs.impute_timegaps_ggir_compat(
        data.x,
        data.y,
        data.z,
        [t / 1e6 for t in data.timestamps],  # Convert to seconds
        float(data.sample_rate),
    )

    # Calculate expected epochs using GGIR formula
    sf = float(data.sample_rate)
    epochsize = 5.0
    samples_per_epoch = sf * epochsize

    # GGIR: floor(num_samples / samples_per_epoch)
    n_samples = len(imputed.x)
    ggir_expected_epochs = n_samples // int(samples_per_epoch)

    # Now check what Rust's compute_anglez_timestamp_epochs produces
    cal_file = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data/P1-1024-A-T1 (2023-07-18)/r_calibration.csv")
    cal_df = pd.read_csv(cal_file)
    offset = [cal_df["offset_x"].iloc[0], cal_df["offset_y"].iloc[0], cal_df["offset_z"].iloc[0]]
    scale = [cal_df["scale_x"].iloc[0], cal_df["scale_y"].iloc[0], cal_df["scale_z"].iloc[0]]

    _rust_anglez, _timestamps, _sample_rate, _num_epochs, _num_na, _num_gaps, _samples_added = gt3x_rs.process_gt3x_ggir_anglez_calibrated(
        str(gt3x_file),
        cal_offset=offset,
        cal_scale=scale,
    )

    # Check the timestamp-based calculation
    ts = np.array(imputed.timestamps)
    start_time = ts[0]
    end_time = ts[-1]
    total_duration = end_time - start_time

    # Rust's calculation (WRONG):
    rust_epoch_calc = int(total_duration // epochsize) + 1

    # GGIR sample-based calculation

    # Difference


if __name__ == "__main__":
    main()
