"""Quick test comparing v3 with the specific file."""

from pathlib import Path

import numpy as np
import pandas as pd


def main():
    # Use the local file as specified
    gt3x_file = Path("D:/Scripts/monorepo/P1-1078-A-T1 (2023-11-08).gt3x")

    if not gt3x_file.exists():
        # Fall back to P1-1024
        gt3x_file = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1/P1-1024-A-T1 (2023-07-18).gt3x")
        ggir_anglez_file = Path(__file__).parent / "ggir_reference/P1-1024-A-T1_2023-07-18_anglez.csv"
        cal_file = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data/P1-1024-A-T1 (2023-07-18)/r_calibration.csv")
        participant = "P1-1024-A-T1"
    else:
        ggir_anglez_file = Path(__file__).parent / "ggir_reference/P1-1078-A-T1_2023-11-08_anglez.csv"
        cal_file = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data/P1-1078-A-T1 (2023-11-08)/r_calibration.csv")
        participant = "P1-1078-A-T1"

    # Load calibration
    cal_df = pd.read_csv(cal_file)
    offset = [cal_df["offset_x"].iloc[0], cal_df["offset_y"].iloc[0], cal_df["offset_z"].iloc[0]]
    scale = [cal_df["scale_x"].iloc[0], cal_df["scale_y"].iloc[0], cal_df["scale_z"].iloc[0]]

    # Load GGIR reference
    ggir_df = pd.read_csv(ggir_anglez_file)
    ggir_anglez = ggir_df["anglez"].values

    import gt3x_rs

    # Test v2 (calibrated, timestamp-based)
    rust_v2, _ts_v2, _sr_v2, _n_v2, _na_v2, _gaps_v2, _added_v2 = gt3x_rs.process_gt3x_ggir_anglez_calibrated(
        str(gt3x_file),
        cal_offset=offset,
        cal_scale=scale,
    )
    rust_v2 = np.array(rust_v2)

    min_len = min(len(rust_v2), len(ggir_anglez))
    valid = ~np.isnan(ggir_anglez[:min_len]) & ~np.isnan(rust_v2[:min_len])
    corr_v2 = np.corrcoef(ggir_anglez[:min_len][valid], rust_v2[:min_len][valid])[0, 1]

    # Test v3 (with truncation)
    rust_v3, _sr_v3, _n_v3, _trunc_start, _trunc_end, _gaps_v3, _added_v3 = gt3x_rs.process_gt3x_ggir_anglez_v3(
        str(gt3x_file),
        cal_offset=offset,
        cal_scale=scale,
    )
    rust_v3 = np.array(rust_v3)

    min_len = min(len(rust_v3), len(ggir_anglez))
    valid = ~np.isnan(ggir_anglez[:min_len]) & ~np.isnan(rust_v3[:min_len])
    corr_v3 = np.corrcoef(ggir_anglez[:min_len][valid], rust_v3[:min_len][valid])[0, 1]

    # Compare first few values
    for i in range(min(10, min_len)):
        g = ggir_anglez[i]
        v2 = rust_v2[i] if i < len(rust_v2) else np.nan
        v3 = rust_v3[i] if i < len(rust_v3) else np.nan


if __name__ == "__main__":
    main()
