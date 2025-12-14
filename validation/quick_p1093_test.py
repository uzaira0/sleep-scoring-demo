"""Quick test of just P1-1093 files with v4."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


def load_ggir_calibration(cal_file: Path) -> tuple[list[float], list[float]]:
    df = pd.read_csv(cal_file)
    offset = [df["offset_x"].iloc[0], df["offset_y"].iloc[0], df["offset_z"].iloc[0]]
    scale = [df["scale_x"].iloc[0], df["scale_y"].iloc[0], df["scale_z"].iloc[0]]
    return offset, scale


def load_ggir_sib_reference(sib_file: Path) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(sib_file)
    if df["anglez"].dtype == object:
        df["anglez"] = pd.to_numeric(df["anglez"], errors="coerce")
    return df["anglez"].values, df["sleep_score"].values


def classify_sleep_wake_vanhees2015(anglez: np.ndarray) -> np.ndarray:
    """HASIB/SIB algorithm (van Hees 2015)."""
    n_epochs = len(anglez)
    sleep_scores = np.zeros(n_epochs, dtype=int)

    z_angle_diffs = np.abs(np.diff(anglez))
    posture_changes = np.where((~np.isnan(z_angle_diffs)) & (z_angle_diffs > 5.0))[0]

    if len(posture_changes) < 2:
        if len(posture_changes) < 10:
            sleep_scores[:] = 1
        return sleep_scores

    gaps_between_changes = np.diff(posture_changes)
    large_gaps = np.where(gaps_between_changes > 60)[0]

    if len(large_gaps) == 0:
        return sleep_scores

    for gap_idx in large_gaps:
        start_epoch = posture_changes[gap_idx]
        end_epoch = posture_changes[gap_idx + 1]
        sleep_scores[start_epoch : end_epoch + 1] = 1

    return sleep_scores


def main():
    import gt3x_rs

    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    ggir_batch_dir = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data")

    gt3x_locations = [
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1"),
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T2"),
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T3"),
    ]

    # Only P1-1093 files
    sib_files = sorted(ggir_reference_dir.glob("P1-1093*_sib.csv"))

    for sib_file in sib_files:
        name = sib_file.stem.replace("_sib", "")
        parts = name.split("_")
        if len(parts) != 2:
            continue

        participant_id = parts[0]
        date = parts[1]

        cal_dir = ggir_batch_dir / f"{participant_id} ({date})"
        cal_file = cal_dir / "r_calibration.csv"
        if not cal_file.exists():
            continue

        gt3x_file = None
        for loc in gt3x_locations:
            if loc.exists():
                files = list(loc.glob(f"{participant_id}*.gt3x"))
                if files:
                    gt3x_file = files[0]
                    break

        if not gt3x_file:
            continue

        offset, scale = load_ggir_calibration(cal_file)
        ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

        # v3 (no DST)
        try:
            rust_anglez_v3, sr, ne, ts, te, ng, sa = gt3x_rs.process_gt3x_ggir_anglez_v3(str(gt3x_file), cal_offset=offset, cal_scale=scale)
            rust_anglez_v3 = np.array(rust_anglez_v3)

            epochs_match_v3 = len(rust_anglez_v3) == len(ggir_anglez)

            if not epochs_match_v3:
                min_len = min(len(rust_anglez_v3), len(ggir_anglez))
                g3 = ggir_anglez[:min_len]
                r3 = rust_anglez_v3[:min_len]
                gs3 = ggir_sleep[:min_len]
            else:
                g3 = ggir_anglez
                r3 = rust_anglez_v3
                gs3 = ggir_sleep

            valid3 = ~np.isnan(g3) & ~np.isnan(r3)
            rs3 = classify_sleep_wake_vanhees2015(r3)
            kappa_v3 = cohen_kappa_score(gs3[valid3].astype(int), rs3[valid3].astype(int))

        except Exception as e:
            kappa_v3 = None

        # v4 (with DST)
        try:
            rust_anglez_v4, _sr, _ne, _ts, _te, _ng, _sa, _dst = gt3x_rs.process_gt3x_ggir_anglez_v4(
                str(gt3x_file), configtz="America/Chicago", cal_offset=offset, cal_scale=scale
            )
            rust_anglez_v4 = np.array(rust_anglez_v4)

            epochs_match_v4 = len(rust_anglez_v4) == len(ggir_anglez)

            if not epochs_match_v4:
                min_len = min(len(rust_anglez_v4), len(ggir_anglez))
                g4 = ggir_anglez[:min_len]
                r4 = rust_anglez_v4[:min_len]
                gs4 = ggir_sleep[:min_len]
            else:
                g4 = ggir_anglez
                r4 = rust_anglez_v4
                gs4 = ggir_sleep

            valid4 = ~np.isnan(g4) & ~np.isnan(r4)
            rs4 = classify_sleep_wake_vanhees2015(r4)
            kappa_v4 = cohen_kappa_score(gs4[valid4].astype(int), rs4[valid4].astype(int))

        except Exception as e:
            kappa_v4 = None

        # Compare anglez values directly
        if kappa_v3 is not None and kappa_v3 < 1.0:
            # Find mismatches
            mismatches = np.where(gs3[valid3] != rs3[valid3])[0]
            if len(mismatches) > 0 and len(mismatches) < 20:
                pass

            # Check anglez correlation
            corr = np.corrcoef(g3[valid3], r3[valid3])[0, 1]
            mae = np.mean(np.abs(g3[valid3] - r3[valid3]))


if __name__ == "__main__":
    main()
