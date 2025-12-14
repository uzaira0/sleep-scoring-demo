"""Debug z-angle calculation differences between Python and GGIR."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from sleep_scoring_app.core.algorithms.sleep_wake.z_angle import (
    calculate_z_angle_from_dataframe,
    resample_to_epochs,
)
from sleep_scoring_app.io.sources.gt3x_loader import GT3XDataSourceLoader


def main():
    # Load GGIR reference z-angle
    ggir_anglez_file = Path(__file__).parent / "ggir_reference" / "ggir_anglez_5sec.csv"
    ggir_df = pd.read_csv(ggir_anglez_file)

    # Load GT3X with Python
    gt3x_file = Path("D:/Scripts/monorepo/external/ggir/data/TestUA_MOS2E22180349_2023-03-07___09-39-04.gt3x")
    loader = GT3XDataSourceLoader(epoch_length_seconds=60, return_raw=True)
    result = loader.load_file(str(gt3x_file))

    if isinstance(result, dict) and "activity_data" in result:
        raw_df = result["activity_data"]
    else:
        raw_df = result

    # Normalize column names
    rename_map = {"axis_x": "AXIS_X", "axis_y": "AXIS_Y", "axis_z": "AXIS_Z"}
    raw_df = raw_df.rename(columns={k: v for k, v in rename_map.items() if k in raw_df.columns})

    # Calculate z-angle with Python
    df_with_z = calculate_z_angle_from_dataframe(
        raw_df,
        ax_col="AXIS_X",
        ay_col="AXIS_Y",
        az_col="AXIS_Z",
    )

    # Resample to 5-second epochs
    python_5sec = resample_to_epochs(
        df_with_z,
        timestamp_col="timestamp",
        value_col="z_angle",
        epoch_seconds=5,
        aggregation="median",
    )

    # Compare first 100 epochs
    min_len = min(len(ggir_df), len(python_5sec), 100)
    ggir_z = ggir_df["anglez"].values[:min_len]
    python_z = python_5sec["z_angle"].values[:min_len]

    diff = ggir_z - python_z

    # Correlation
    corr = np.corrcoef(ggir_z, python_z)[0, 1]

    # Print first 10 values
    for i in range(10):
        pass

    # Now check the SIB detection logic difference

    # Load GGIR SIB results
    ggir_sib_file = Path(__file__).parent / "ggir_reference" / "ggir_sib_vanHees2015.csv"
    ggir_sib_df = pd.read_csv(ggir_sib_file)

    # Compare z-angle change patterns
    ggir_z_full = ggir_df["anglez"].values
    python_z_full = python_5sec["z_angle"].values[: len(ggir_z_full)]

    # Calculate z-angle changes
    ggir_changes = np.abs(np.diff(ggir_z_full))
    python_changes = np.abs(np.diff(python_z_full))

    # Count epochs where change <= 5 degrees
    ggir_stable = np.sum(ggir_changes <= 5)
    python_stable = np.sum(python_changes <= 5)

    # Check GGIR SIB scores
    ggir_sleep = ggir_sib_df["sleep_score"].values

    # Export detailed comparison for analysis
    comparison_len = min(len(ggir_df), len(python_5sec))
    detailed_df = pd.DataFrame(
        {
            "ggir_anglez": ggir_df["anglez"].values[:comparison_len],
            "python_anglez": python_5sec["z_angle"].values[:comparison_len],
            "ggir_sleep": ggir_sib_df["sleep_score"].values[:comparison_len],
        }
    )
    detailed_df["z_diff"] = detailed_df["ggir_anglez"] - detailed_df["python_anglez"]

    output_file = Path(__file__).parent / "ggir_reference" / "z_angle_comparison.csv"
    detailed_df.to_csv(output_file, index=False)


if __name__ == "__main__":
    main()
