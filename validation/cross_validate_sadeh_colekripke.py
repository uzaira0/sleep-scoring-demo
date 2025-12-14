#!/usr/bin/env python3
"""
Cross-validation of Sadeh and Cole-Kripke algorithm variants.

This script compares three implementations of each algorithm:
1. GGIR variant (zero-crossing counts from raw accelerometer)
2. ActiLife variant (Axis1/Y-axis activity counts)
3. Original Paper variant

The goal is to compute Cohen's Kappa between all pairs to understand
inter-method agreement.

References:
    Sadeh, A., et al. (1994). Sleep, 17(3), 201-207.
    Cole, R. J., et al. (1992). Sleep, 15(5), 461-469.

Paper context:
    "Actigraphy Data Processing in ActiLife" vs "GGIR" as described in the
    comparison paper discussing Neishabouri counts vs zero-crossing counts.

"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# Algorithm Variant Definitions
# =============================================================================


@dataclass
class AlgorithmVariant:
    """Describes an algorithm implementation variant."""

    name: str
    source: str  # "GGIR", "ActiLife", "Paper"
    input_type: str  # "zero_crossing", "axis1_counts"
    threshold: float | None = None
    scaling: str | None = None  # "none", "div100_cap300", etc.

    @property
    def identifier(self) -> str:
        return f"{self.name}_{self.source}".lower().replace(" ", "_")


# Define all variants
SADEH_VARIANTS = [
    AlgorithmVariant(
        name="Sadeh1994",
        source="GGIR",
        input_type="zero_crossing",
        threshold=0.0,
        scaling="none",
    ),
    AlgorithmVariant(
        name="Sadeh1994",
        source="ActiLife",
        input_type="axis1_counts",
        threshold=-4.0,
        scaling="cap300",
    ),
    AlgorithmVariant(
        name="Sadeh1994",
        source="Paper",
        input_type="axis1_counts",  # Original used AMI Motionlogger
        threshold=0.0,
        scaling="cap300",
    ),
]

COLEKRIPKE_VARIANTS = [
    AlgorithmVariant(
        name="ColeKripke1992",
        source="GGIR",
        input_type="zero_crossing",
        threshold=1.0,
        scaling="div6",  # Converts to per-10-second
    ),
    AlgorithmVariant(
        name="ColeKripke1992",
        source="ActiLife",
        input_type="axis1_counts",
        threshold=1.0,
        scaling="div100_cap300",
    ),
    AlgorithmVariant(
        name="ColeKripke1992",
        source="Paper",
        input_type="axis1_counts",
        threshold=1.0,
        scaling="none",  # Original paper used raw counts
    ),
]


# =============================================================================
# Sadeh Algorithm Implementations
# =============================================================================


def sadeh_ggir(zc_counts: np.ndarray, epochsize: int = 5) -> np.ndarray:
    """
    GGIR implementation of Sadeh algorithm.

    Uses zero-crossing counts, threshold PS >= 0.

    Args:
        zc_counts: Zero-crossing counts per epoch
        epochsize: Epoch size in seconds (typically 5)

    Returns:
        Sleep/wake classification (1=sleep, 0=wake)

    """
    n = len(zc_counts)
    if n == 0:
        return np.array([], dtype=np.uint8)

    # Aggregate to 1-minute epochs
    epochs_per_min = 60 // epochsize
    n_minutes = n // epochs_per_min

    if n_minutes == 0:
        return np.zeros(n, dtype=np.uint8)

    # Sum to 1-minute epochs
    count_per_min = np.zeros(n_minutes)
    for i in range(n_minutes):
        start = i * epochs_per_min
        end = start + epochs_per_min
        count_per_min[i] = np.sum(zc_counts[start:end])

    # No capping for GGIR (zeroCrossingCount is not capped)

    # Create 11-minute rolling matrix
    ps_scores = np.zeros(n_minutes, dtype=np.uint8)

    for i in range(5, n_minutes):
        # Get 11-minute window centered at i
        start_idx = max(0, i - 5)
        end_idx = min(n_minutes, i + 6)

        # Pad with zeros if needed
        window = np.zeros(11)
        window_start = 5 - (i - start_idx)
        window[window_start : window_start + (end_idx - start_idx)] = count_per_min[start_idx:end_idx]

        # Calculate features
        mean_w5 = np.mean(window)

        # SDlast = sd of last 5 (indices 6-10)
        last5 = window[6:11]
        sd_last = np.std(last5, ddof=1) if len(last5) > 1 else 0.0

        # NAT = count where 50 < x < 100
        nat = np.sum((window > 50) & (window < 100))

        # LOGact = log(current + 1)
        log_act = np.log(window[5] + 1)

        # Sadeh formula
        ps = 7.601 - (0.065 * mean_w5) - (1.08 * nat) - (0.056 * sd_last) - (0.703 * log_act)

        # GGIR: Sleep if PS >= 0
        if ps >= 0:
            ps_scores[i] = 1

    # Expand back to original resolution
    result = np.zeros(n, dtype=np.uint8)
    for i in range(n_minutes):
        start = i * epochs_per_min
        end = min(start + epochs_per_min, n)
        result[start:end] = ps_scores[i]

    return result


def sadeh_actilife(axis1_counts: np.ndarray, threshold: float = -4.0) -> np.ndarray:
    """
    ActiLife implementation of Sadeh algorithm.

    Uses Axis1 counts, caps at 300, threshold PS > -4.
    Uses forward-looking SD (ActiLife-specific behavior).

    Args:
        axis1_counts: Y-axis activity counts (1-minute epochs)
        threshold: Classification threshold (default -4 for ActiLife)

    Returns:
        Sleep/wake classification (1=sleep, 0=wake)

    """
    n = len(axis1_counts)
    if n == 0:
        return np.array([], dtype=np.uint8)

    # Cap at 300
    capped = np.minimum(axis1_counts, 300)

    # Pad with zeros (5 before, 5 after)
    padded = np.pad(capped, pad_width=5, mode="constant", constant_values=0)

    # Pre-compute forward rolling SD (ActiLife uses forward-looking 6-epoch window)
    rolling_sds = np.zeros(n)
    for i in range(n):
        sd_window = padded[i : i + 6]  # 6 epochs starting at i
        if len(sd_window) >= 2:
            rolling_sds[i] = np.std(sd_window, ddof=1)

    ps_scores = np.zeros(n, dtype=np.uint8)

    for i in range(n):
        # 11-minute window
        window = padded[i : i + 11]

        # Features
        mean_w5 = np.mean(window)
        nat = np.sum((window >= 50) & (window < 100))
        sd_last = rolling_sds[i]
        log_act = np.log(capped[i] + 1)

        # Sadeh formula
        ps = 7.601 - (0.065 * mean_w5) - (1.08 * nat) - (0.056 * sd_last) - (0.703 * log_act)

        # ActiLife: Sleep if PS > threshold (default -4)
        if ps > threshold:
            ps_scores[i] = 1

    return ps_scores


def sadeh_paper(axis1_counts: np.ndarray) -> np.ndarray:
    """
    Original Sadeh (1994) paper implementation.

    Uses activity counts, caps at 300, threshold PS > 0.
    Uses centered SD calculation.

    Args:
        axis1_counts: Activity counts (1-minute epochs)

    Returns:
        Sleep/wake classification (1=sleep, 0=wake)

    """
    # Same as ActiLife but with threshold 0
    return sadeh_actilife(axis1_counts, threshold=0.0)


# =============================================================================
# Cole-Kripke Algorithm Implementations
# =============================================================================

# Cole-Kripke weights
CK_WEIGHTS = np.array([106, 54, 58, 76, 230, 74, 67])  # A(t-4) to A(t+2)


def colekripke_ggir(zc_counts: np.ndarray, epochsize: int = 5) -> np.ndarray:
    """
    GGIR implementation of Cole-Kripke algorithm.

    Uses zero-crossing counts, converts to per-10-second.

    Args:
        zc_counts: Zero-crossing counts per epoch
        epochsize: Epoch size in seconds

    Returns:
        Sleep/wake classification (1=sleep, 0=wake)

    """
    n = len(zc_counts)
    if n == 0:
        return np.array([], dtype=np.uint8)

    # Aggregate to 1-minute epochs
    epochs_per_min = 60 // epochsize
    n_minutes = n // epochs_per_min

    if n_minutes == 0:
        return np.zeros(n, dtype=np.uint8)

    # Sum to 1-minute epochs
    count_per_min = np.zeros(n_minutes)
    for i in range(n_minutes):
        start = i * epochs_per_min
        end = start + epochs_per_min
        count_per_min[i] = np.sum(zc_counts[start:end])

    # Convert to per 10 seconds
    count_per_10s = count_per_min / 6.0

    # Pad with zeros (4 before, 2 after for 7-minute window)
    padded = np.pad(count_per_10s, pad_width=(4, 2), mode="constant", constant_values=0)

    ps_scores = np.zeros(n_minutes, dtype=np.uint8)

    for i in range(n_minutes):
        # 7-minute window
        window = padded[i : i + 7]

        # Apply weights
        weighted_sum = np.dot(window, CK_WEIGHTS)
        ps = 0.001 * weighted_sum

        # Sleep if PS < 1
        if ps < 1.0:
            ps_scores[i] = 1

    # Expand back to original resolution
    result = np.zeros(n, dtype=np.uint8)
    for i in range(n_minutes):
        start = i * epochs_per_min
        end = min(start + epochs_per_min, n)
        result[start:end] = ps_scores[i]

    return result


def colekripke_actilife(axis1_counts: np.ndarray) -> np.ndarray:
    """
    ActiLife implementation of Cole-Kripke algorithm.

    Divides by 100, caps at 300, then applies weights.

    Args:
        axis1_counts: Y-axis activity counts (1-minute epochs)

    Returns:
        Sleep/wake classification (1=sleep, 0=wake)

    """
    n = len(axis1_counts)
    if n == 0:
        return np.array([], dtype=np.uint8)

    # ActiLife: divide by 100 and cap at 300
    scaled = np.minimum(axis1_counts / 100.0, 300.0)

    # Pad with zeros (4 before, 2 after)
    padded = np.pad(scaled, pad_width=(4, 2), mode="constant", constant_values=0)

    ps_scores = np.zeros(n, dtype=np.uint8)

    for i in range(n):
        window = padded[i : i + 7]
        weighted_sum = np.dot(window, CK_WEIGHTS)
        ps = 0.001 * weighted_sum

        if ps < 1.0:
            ps_scores[i] = 1

    return ps_scores


def colekripke_paper(axis1_counts: np.ndarray) -> np.ndarray:
    """
    Original Cole-Kripke (1992) paper implementation.

    Uses raw counts without scaling.

    Args:
        axis1_counts: Activity counts (1-minute epochs)

    Returns:
        Sleep/wake classification (1=sleep, 0=wake)

    """
    n = len(axis1_counts)
    if n == 0:
        return np.array([], dtype=np.uint8)

    # No scaling for original paper
    padded = np.pad(axis1_counts, pad_width=(4, 2), mode="constant", constant_values=0)

    ps_scores = np.zeros(n, dtype=np.uint8)

    for i in range(n):
        window = padded[i : i + 7]
        weighted_sum = np.dot(window, CK_WEIGHTS)
        ps = 0.001 * weighted_sum

        if ps < 1.0:
            ps_scores[i] = 1

    return ps_scores


# =============================================================================
# Validation Metrics
# =============================================================================


def cohens_kappa(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate Cohen's Kappa coefficient."""
    n = len(y_true)
    if n == 0:
        return float("nan")

    # Confusion matrix
    tp = np.sum((y_true == 1) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))

    # Observed agreement
    po = (tp + tn) / n

    # Expected agreement
    p_yes_true = (tp + fn) / n
    p_yes_pred = (tp + fp) / n
    p_no_true = (tn + fp) / n
    p_no_pred = (tn + fn) / n

    pe = (p_yes_true * p_yes_pred) + (p_no_true * p_no_pred)

    # Kappa
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0

    return (po - pe) / (1 - pe)


def agreement_percentage(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate percentage agreement."""
    if len(y_true) == 0:
        return float("nan")
    return np.mean(y_true == y_pred) * 100


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate confusion matrix components."""
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    return {
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "total": tp + tn + fp + fn,
    }


# =============================================================================
# Cross-Validation Framework
# =============================================================================


@dataclass
class ComparisonResult:
    """Result of comparing two algorithm variants."""

    variant_a: str
    variant_b: str
    kappa: float
    agreement: float
    n_epochs: int
    confusion: dict


def compare_variants(
    results: dict[str, np.ndarray],
    variant_a: str,
    variant_b: str,
) -> ComparisonResult:
    """Compare two algorithm variants."""
    if variant_a not in results or variant_b not in results:
        msg = f"Missing results for {variant_a} or {variant_b}"
        raise ValueError(msg)

    y_a = results[variant_a]
    y_b = results[variant_b]

    # Ensure same length
    min_len = min(len(y_a), len(y_b))
    y_a = y_a[:min_len]
    y_b = y_b[:min_len]

    return ComparisonResult(
        variant_a=variant_a,
        variant_b=variant_b,
        kappa=cohens_kappa(y_a, y_b),
        agreement=agreement_percentage(y_a, y_b),
        n_epochs=min_len,
        confusion=confusion_matrix(y_a, y_b),
    )


def run_cross_validation(
    zc_counts: np.ndarray | None = None,
    axis1_counts: np.ndarray | None = None,
    epochsize: int = 5,
) -> dict:
    """
    Run cross-validation on all algorithm variants.

    Args:
        zc_counts: Zero-crossing counts (for GGIR variants)
        axis1_counts: Axis1 activity counts (for ActiLife/Paper variants)
        epochsize: Epoch size in seconds for zero-crossing data

    Returns:
        Dictionary with all comparison results

    """
    results = {}

    # Run Sadeh variants
    if zc_counts is not None:
        results["sadeh_ggir"] = sadeh_ggir(zc_counts, epochsize)

    if axis1_counts is not None:
        results["sadeh_actilife"] = sadeh_actilife(axis1_counts)
        results["sadeh_paper"] = sadeh_paper(axis1_counts)

    # Run Cole-Kripke variants
    if zc_counts is not None:
        results["colekripke_ggir"] = colekripke_ggir(zc_counts, epochsize)

    if axis1_counts is not None:
        results["colekripke_actilife"] = colekripke_actilife(axis1_counts)
        results["colekripke_paper"] = colekripke_paper(axis1_counts)

    # Compare all pairs
    comparisons = []

    # Sadeh comparisons
    sadeh_variants = [k for k in results if k.startswith("sadeh_")]
    for i, v1 in enumerate(sadeh_variants):
        for v2 in sadeh_variants[i + 1 :]:
            comparisons.append(compare_variants(results, v1, v2))

    # Cole-Kripke comparisons
    ck_variants = [k for k in results if k.startswith("colekripke_")]
    for i, v1 in enumerate(ck_variants):
        for v2 in ck_variants[i + 1 :]:
            comparisons.append(compare_variants(results, v1, v2))

    return {
        "results": results,
        "comparisons": comparisons,
    }


def print_comparison_report(validation_results: dict) -> None:
    """Print a formatted comparison report."""
    results = validation_results["results"]
    comparisons = validation_results["comparisons"]

    # Summary of what was run
    for arr in results.values():
        n_sleep = np.sum(arr == 1)
        pct_sleep = 100 * n_sleep / len(arr) if len(arr) > 0 else 0

    # Comparison results

    for comp in comparisons:
        cm = comp.confusion

    # Summary table
    for comp in comparisons:
        name = f"{comp.variant_a} vs {comp.variant_b}"


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cross-validate Sadeh and Cole-Kripke algorithm variants")
    parser.add_argument("--zc-file", type=str, help="CSV file with zero-crossing counts (column: 'zc' or 'zero_crossing')")
    parser.add_argument("--axis1-file", type=str, help="CSV file with Axis1 counts (column: 'Axis1' or 'axis1')")
    parser.add_argument("--agd-file", type=str, help="AGD file with epoch data")
    parser.add_argument("--epochsize", type=int, default=5, help="Epoch size in seconds for ZC data (default: 5)")
    parser.add_argument("--demo", action="store_true", help="Run with synthetic demo data")

    args = parser.parse_args()

    if args.demo:
        # Generate synthetic data for demonstration

        np.random.seed(42)
        n_epochs = 1440  # 24 hours at 1-minute epochs

        # Simulate sleep pattern (low activity at night)
        hour = np.arange(n_epochs) // 60 % 24
        is_night = (hour >= 22) | (hour < 7)

        # Generate counts
        base_activity = np.where(is_night, 10, 200)
        noise = np.random.exponential(50, n_epochs)
        axis1_counts = np.maximum(0, base_activity + noise).astype(float)

        # Generate ZC counts (correlated but different)
        zc_base = np.where(is_night, 5, 50)
        zc_noise = np.random.exponential(10, n_epochs)
        zc_counts = np.maximum(0, zc_base + zc_noise)

        # For GGIR, expand to 5-second epochs
        zc_5sec = np.repeat(zc_counts / 12, 12)  # 12 5-sec epochs per minute

        validation_results = run_cross_validation(
            zc_counts=zc_5sec,
            axis1_counts=axis1_counts,
            epochsize=5,
        )

        print_comparison_report(validation_results)

    else:
        pass
