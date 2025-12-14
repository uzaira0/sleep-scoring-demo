"""Test v3 on all available files to identify which ones match."""

from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    ggir_batch_dir = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data")

    gt3x_locations = [
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1"),
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T2"),
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T3"),
    ]

    # Also check local monorepo for test files
    local_gt3x = Path("D:/Scripts/monorepo")

    sib_files = sorted(ggir_reference_dir.glob("P1-*_sib.csv"))

    import gt3x_rs

    for sib_file in sib_files:
        name = sib_file.stem.replace("_sib", "")
        parts = name.split("_")
        if len(parts) != 2:
            continue

        participant_id = parts[0]
        date = parts[1]

        # Find anglez file
        anglez_file = ggir_reference_dir / f"{participant_id}_{date}_anglez.csv"
        if not anglez_file.exists():
            continue

        # Find calibration
        cal_dir = ggir_batch_dir / f"{participant_id} ({date})"
        cal_file = cal_dir / "r_calibration.csv"
        if not cal_file.exists():
            continue

        # Find GT3X - check local first, then remote
        gt3x_file = None

        # Check local monorepo
        local_files = list(local_gt3x.glob(f"{participant_id}*.gt3x"))
        if local_files:
            gt3x_file = local_files[0]

        # Check remote locations
        if not gt3x_file:
            for loc in gt3x_locations:
                if loc.exists():
                    files = list(loc.glob(f"{participant_id}*.gt3x"))
                    if files:
                        gt3x_file = files[0]
                        break

        if not gt3x_file:
            continue

        # Load data
        cal_df = pd.read_csv(cal_file)
        offset = [cal_df["offset_x"].iloc[0], cal_df["offset_y"].iloc[0], cal_df["offset_z"].iloc[0]]
        scale = [cal_df["scale_x"].iloc[0], cal_df["scale_y"].iloc[0], cal_df["scale_z"].iloc[0]]

        ggir_df = pd.read_csv(anglez_file)
        ggir_anglez = ggir_df["anglez"].values

        try:
            rust_anglez, _sr, _n_epochs, _trunc_start, _trunc_end, _gaps, _added = gt3x_rs.process_gt3x_ggir_anglez_v3(
                str(gt3x_file),
                cal_offset=offset,
                cal_scale=scale,
            )
            rust_anglez = np.array(rust_anglez)
        except Exception as e:
            continue

        diff = len(rust_anglez) - len(ggir_anglez)

        min_len = min(len(rust_anglez), len(ggir_anglez))
        valid = ~np.isnan(ggir_anglez[:min_len]) & ~np.isnan(rust_anglez[:min_len])
        if valid.sum() > 0:
            corr = np.corrcoef(ggir_anglez[:min_len][valid], rust_anglez[:min_len][valid])[0, 1]
        else:
            corr = np.nan

        if diff == 0 and corr > 0.999:
            status = "MATCH"
        elif corr > 0.999:
            status = "CLOSE"
        else:
            status = "MISMATCH"


if __name__ == "__main__":
    main()
