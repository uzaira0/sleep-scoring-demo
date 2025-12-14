"""Quick investigation of P1-1093 Kappa issues."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score


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
    ggir_reference_dir = Path(__file__).parent / "ggir_reference"

    # Find all P1-1093 SIB files
    sib_files = sorted(ggir_reference_dir.glob("P1-1093*_sib.csv"))

    for sib_file in sib_files:
        ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

        # Check for NaN values
        nan_count = np.sum(np.isnan(ggir_anglez))

        # Run our algorithm on GGIR's anglez (should give perfect Kappa if algorithm is correct)
        our_sleep = classify_sleep_wake_vanhees2015(ggir_anglez)

        # Check valid values only
        valid = ~np.isnan(ggir_anglez)
        n_valid = valid.sum()

        if n_valid > 100:
            kappa = cohen_kappa_score(ggir_sleep[valid].astype(int), our_sleep[valid].astype(int))
            agreement = np.mean(ggir_sleep[valid] == our_sleep[valid])
            mismatches = np.sum(ggir_sleep[valid] != our_sleep[valid])

            # Find where mismatches occur
            if mismatches > 0 and mismatches < 50:
                mismatch_indices = np.where((ggir_sleep != our_sleep) & valid)[0]

                # Look at some mismatch locations
                for idx in mismatch_indices[:5]:
                    start = max(0, idx - 3)
                    end = min(len(ggir_anglez), idx + 4)

    # Also test the algorithm directly on GGIR anglez from one of the P1-1093 files

    # Use the first P1-1093 file
    if sib_files:
        sib_file = sib_files[0]
        ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

        # Find posture changes as GGIR does
        z_angle_diffs = np.abs(np.diff(ggir_anglez))
        valid_diffs = ~np.isnan(z_angle_diffs)
        posture_changes = np.where(valid_diffs & (z_angle_diffs > 5.0))[0]

        if len(posture_changes) > 1:
            gaps = np.diff(posture_changes)
            large_gaps = np.where(gaps > 60)[0]

            # Show some gap details


if __name__ == "__main__":
    main()
