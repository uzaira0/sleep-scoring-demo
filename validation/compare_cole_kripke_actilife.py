from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from sleep_scoring_app.core.algorithms.sleep_wake.cole_kripke import score_activity_cole_kripke


def load_activity_file(filepath: Path) -> pd.DataFrame:
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    header_row = None
    for i, line in enumerate(lines):
        if "Date" in line and "Axis1" in line:
            header_row = i
            break

    if header_row is None:
        msg = f"Could not find header row in {filepath}"
        raise ValueError(msg)

    df = pd.read_csv(filepath, skiprows=header_row)
    df.columns = df.columns.str.strip()
    return df


def load_cole_kripke_file(filepath: Path) -> pd.DataFrame:
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    header_row = None
    for i, line in enumerate(lines):
        if "Date" in line and "Sleep or Awake" in line:
            header_row = i
            break

    if header_row is None:
        msg = f"Could not find header row in {filepath}"
        raise ValueError(msg)

    df = pd.read_csv(filepath, skiprows=header_row)
    df.columns = df.columns.str.strip()
    return df


def compare_single_file(activity_file: Path, cole_kripke_file: Path) -> dict:
    activity_df = load_activity_file(activity_file)
    actilife_df = load_cole_kripke_file(cole_kripke_file)

    if "Axis1" not in activity_df.columns:
        msg = f"Axis1 column not found in {activity_file}"
        raise ValueError(msg)

    axis1_data = activity_df["Axis1"].values

    sleepapp_scores = score_activity_cole_kripke(axis1_data, use_actilife_scaling=True)
    sleepapp_scores = np.array(sleepapp_scores)

    sleep_col = "Sleep or Awake?"
    if sleep_col not in actilife_df.columns:
        msg = f"'{sleep_col}' column not found in {cole_kripke_file}"
        raise ValueError(msg)

    actilife_scores = actilife_df[sleep_col].map({"S": 1, "W": 0}).values

    min_len = min(len(sleepapp_scores), len(actilife_scores))
    if len(sleepapp_scores) != len(actilife_scores):
        pass

    sleepapp_scores = sleepapp_scores[:min_len]
    actilife_scores = actilife_scores[:min_len]

    matches = np.sum(sleepapp_scores == actilife_scores)
    total = len(sleepapp_scores)
    agreement = matches / total if total > 0 else 0

    kappa = calculate_cohens_kappa(sleepapp_scores, actilife_scores)

    mismatch_indices = np.where(sleepapp_scores != actilife_scores)[0]

    return {
        "file": activity_file.stem,
        "total_epochs": total,
        "matches": matches,
        "mismatches": len(mismatch_indices),
        "agreement": agreement,
        "kappa": kappa,
        "mismatch_indices": mismatch_indices[:20].tolist() if len(mismatch_indices) > 0 else [],
        "sleepapp_scores_at_mismatch": sleepapp_scores[mismatch_indices[:20]].tolist() if len(mismatch_indices) > 0 else [],
        "actilife_scores_at_mismatch": actilife_scores[mismatch_indices[:20]].tolist() if len(mismatch_indices) > 0 else [],
    }


def calculate_cohens_kappa(y1: np.ndarray, y2: np.ndarray) -> float:
    if len(y1) != len(y2) or len(y1) == 0:
        return 0.0

    po = np.mean(y1 == y2)

    p1_1 = np.mean(y1 == 1)
    p1_0 = np.mean(y1 == 0)
    p2_1 = np.mean(y2 == 1)
    p2_0 = np.mean(y2 == 0)

    pe = p1_1 * p2_1 + p1_0 * p2_0

    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def find_matching_files(activity_folder: Path, cole_kripke_folder: Path) -> list[tuple[Path, Path]]:
    matches = []
    activity_files = list(activity_folder.glob("*.csv"))

    for activity_file in activity_files:
        base_name = activity_file.stem
        cole_kripke_name = f"{base_name} Cole-Kripke Sleep Epochs.csv"
        cole_kripke_file = cole_kripke_folder / cole_kripke_name

        if cole_kripke_file.exists():
            matches.append((activity_file, cole_kripke_file))
        else:
            pass

    return matches


def main():
    base_folder = Path(r"C:\Users\u248361\Downloads\Calarge Study Files\Data Files")
    activity_folder = base_folder / "60s Activity Epoch csv files"
    cole_kripke_folder = base_folder / "Cole-Kripke Sleep Epoch csv files"

    if not activity_folder.exists():
        return

    if not cole_kripke_folder.exists():
        return

    file_pairs = find_matching_files(activity_folder, cole_kripke_folder)

    if not file_pairs:
        return

    results = []
    for activity_file, cole_kripke_file in file_pairs:
        try:
            result = compare_single_file(activity_file, cole_kripke_file)
            results.append(result)

            if result["mismatches"] > 0:
                if result["mismatch_indices"]:
                    pass
        except Exception as e:
            pass

    if results:
        total_epochs = sum(r["total_epochs"] for r in results)
        total_matches = sum(r["matches"] for r in results)
        total_mismatches = sum(r["mismatches"] for r in results)

        overall_agreement = total_matches / total_epochs if total_epochs > 0 else 0
        avg_kappa = np.mean([r["kappa"] for r in results])

        if total_mismatches == 0:
            pass
        else:
            for r in results:
                if r["mismatches"] > 0:
                    pass


if __name__ == "__main__":
    main()
