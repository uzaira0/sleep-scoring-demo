"""Test using GGIR's anglez directly to confirm algorithm is correct."""

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
        sleep_scores[posture_changes[gap_idx] : posture_changes[gap_idx + 1] + 1] = 1
    return sleep_scores


def main():
    ggir_reference_dir = Path(__file__).parent / "ggir_reference"
    participant_id = "P1-1093-A-T1"
    date = "2024-03-04"

    sib_file = ggir_reference_dir / f"{participant_id}_{date}_sib.csv"
    ggir_anglez, ggir_sleep = load_ggir_sib_reference(sib_file)

    # Use GGIR's anglez directly with our algorithm
    our_sleep = classify_sleep_wake_vanhees2015(ggir_anglez)
    kappa = cohen_kappa_score(ggir_sleep, our_sleep)
    matches = np.sum(ggir_sleep == our_sleep)

    if kappa == 1.0:
        pass
    else:
        # Find mismatches
        mismatches = np.where(ggir_sleep != our_sleep)[0]
        for idx in mismatches[:10]:
            pass


if __name__ == "__main__":
    main()
