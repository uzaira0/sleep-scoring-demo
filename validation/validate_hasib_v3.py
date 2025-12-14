"""
Validate HASIB using Rust v3 anglez (with GGIR-compatible truncation).

Target: Kappa = 1.0 for all files with matching data.
"""

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


def validate_file(gt3x_file: Path, cal_file: Path, sib_file: Path, participant_id: str) -> dict:
    import gt3x_rs

    offset, scale = load_ggir_calibration(cal_file)
    ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

    try:
        rust_anglez, _sample_rate, _num_epochs, trunc_start, trunc_end, _num_gaps, _samples_added = gt3x_rs.process_gt3x_ggir_anglez_v3(
            str(gt3x_file),
            cal_offset=offset,
            cal_scale=scale,
        )
        rust_anglez = np.array(rust_anglez)
    except Exception as e:
        return {"participant_id": participant_id, "error": str(e), "kappa": np.nan}

    # Check if epoch counts match
    epochs_match = len(rust_anglez) == len(ggir_anglez)

    if not epochs_match:
        min_len = min(len(rust_anglez), len(ggir_anglez))
        g = ggir_anglez[:min_len]
        r = rust_anglez[:min_len]
        gs = ggir_sleep[:min_len]
    else:
        g = ggir_anglez
        r = rust_anglez
        gs = ggir_sleep

    valid = ~np.isnan(g) & ~np.isnan(r)
    n_valid = valid.sum()

    if n_valid < 100:
        return {"participant_id": participant_id, "error": "Too few valid epochs", "kappa": np.nan}

    corr = np.corrcoef(g[valid], r[valid])[0, 1]
    mae = np.mean(np.abs(g[valid] - r[valid]))

    rs = classify_sleep_wake_vanhees2015(r)
    kappa = cohen_kappa_score(gs[valid].astype(int), rs[valid].astype(int))
    agreement = np.mean(gs[valid] == rs[valid])

    return {
        "participant_id": participant_id,
        "n_epochs_ggir": len(ggir_anglez),
        "n_epochs_rust": len(rust_anglez),
        "epochs_match": epochs_match,
        "n_valid": n_valid,
        "anglez_corr": corr,
        "anglez_mae": mae,
        "kappa": kappa,
        "agreement": agreement,
        "trunc_start": trunc_start,
        "trunc_end": trunc_end,
    }


def main():
    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    ggir_batch_dir = Path("D:/Scripts/monorepo/external/ggir/output/batch_r/validation_data")

    gt3x_locations = [
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1"),
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T2"),
        Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T3"),
    ]

    sib_files = sorted(ggir_reference_dir.glob("P1-*_sib.csv"))

    results = []

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

        result = validate_file(gt3x_file, cal_file, sib_file, participant_id)
        results.append(result)

        if "error" in result:
            pass
        else:
            match = "YES" if result["epochs_match"] else "NO"

    # Summary for files where epochs match
    matched = [r for r in results if r.get("epochs_match", False)]

    if matched:
        kappas = [r["kappa"] for r in matched]
        corrs = [r["anglez_corr"] for r in matched]

        if all(k == 1.0 for k in kappas):
            return 0

    # Show unmatched
    unmatched = [r for r in results if not r.get("epochs_match", False) and "error" not in r]
    if unmatched:
        for r in unmatched:
            pass

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
