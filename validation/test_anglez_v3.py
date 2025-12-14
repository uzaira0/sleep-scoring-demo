"""Test the new v3 anglez function with GGIR-compatible truncation."""

from pathlib import Path

import numpy as np
import pandas as pd


def main():
    gt3x_file = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1/P1-1024-A-T1 (2023-07-18).gt3x")
    ggir_anglez_file = Path(__file__).parent / "ggir_reference/P1-1024-A-T1_2023-07-18_anglez.csv"
    cal_file = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data/P1-1024-A-T1 (2023-07-18)/r_calibration.csv")

    # Load calibration
    cal_df = pd.read_csv(cal_file)
    offset = [cal_df["offset_x"].iloc[0], cal_df["offset_y"].iloc[0], cal_df["offset_z"].iloc[0]]
    scale = [cal_df["scale_x"].iloc[0], cal_df["scale_y"].iloc[0], cal_df["scale_z"].iloc[0]]

    # Load GGIR reference
    ggir_df = pd.read_csv(ggir_anglez_file)
    ggir_anglez = ggir_df["anglez"].values

    # Process with Rust v3
    import gt3x_rs

    rust_anglez, _sample_rate, _num_epochs, _trunc_start, _trunc_end, _num_gaps, _samples_added = gt3x_rs.process_gt3x_ggir_anglez_v3(
        str(gt3x_file),
        cal_offset=offset,
        cal_scale=scale,
    )
    rust_anglez = np.array(rust_anglez)

    # Compare

    # If lengths match, compute correlation
    if len(rust_anglez) == len(ggir_anglez):
        valid = ~np.isnan(ggir_anglez) & ~np.isnan(rust_anglez)
        corr = np.corrcoef(ggir_anglez[valid], rust_anglez[valid])[0, 1]
        mae = np.mean(np.abs(ggir_anglez[valid] - rust_anglez[valid]))
        exact_matches = np.sum(np.abs(ggir_anglez[valid] - rust_anglez[valid]) < 0.0001)

    else:
        # Use min length
        min_len = min(len(rust_anglez), len(ggir_anglez))
        g = ggir_anglez[:min_len]
        r = rust_anglez[:min_len]
        valid = ~np.isnan(g) & ~np.isnan(r)
        corr = np.corrcoef(g[valid], r[valid])[0, 1]


if __name__ == "__main__":
    main()
