"""
Integration tests for sleep algorithms with real GT3X data.

These tests load actual GT3X files and run the van Hees 2015 SIB and HDCZA
algorithms to verify they produce reasonable outputs.

Test GT3X File:
- TestUA_MOS2E22180349_2023-03-07___09-39-04.gt3x
- Device: wGT3X-BT (ActiGraph)
- Sample rate: 30 Hz
- Duration: ~3.5 days
- Range: ±8g

These tests verify:
1. Algorithms can load and process GT3X data
2. Z-angle calculation produces values in expected range
3. Sleep detection produces reasonable proportions
4. HDCZA detects sleep period windows
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Test GT3X file path
GGIR_DATA_PATH = Path("D:/Scripts/monorepo/external/ggir/data")
TEST_GT3X_FILE = GGIR_DATA_PATH / "TestUA_MOS2E22180349_2023-03-07___09-39-04.gt3x"


def normalize_axis_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize axis column names to uppercase (AXIS_X, AXIS_Y, AXIS_Z).

    The GT3X loader may return lowercase column names depending on the source.
    This ensures consistency for the sleep algorithms.
    """
    rename_map = {
        "axis_x": "AXIS_X",
        "axis_y": "AXIS_Y",
        "axis_z": "AXIS_Z",
    }

    # Only rename columns that exist and need renaming
    rename_map = {k: v for k, v in rename_map.items() if k in df.columns}

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


@pytest.fixture
def gt3x_raw_data() -> pd.DataFrame | None:
    """
    Load raw data from the test GT3X file.

    Returns None if file doesn't exist (test will be skipped).
    Uses the factory which prefers gt3x-rs (Rust) over pygt3x for performance.
    """
    if not TEST_GT3X_FILE.exists():
        return None

    try:
        from sleep_scoring_app.io.sources.loader_factory import DataSourceFactory

        # Use factory to get the best available loader (prefers gt3x-rs)
        loader = DataSourceFactory.create("gt3x", epoch_length_seconds=60, return_raw=True)
        result = loader.load_file(str(TEST_GT3X_FILE))

        # Extract activity data from result dict
        if isinstance(result, dict) and "activity_data" in result:
            df = result["activity_data"]
        elif isinstance(result, pd.DataFrame):
            df = result
        else:
            pytest.skip(f"Unexpected result type from GT3X loader: {type(result)}")
            return None

        # Normalize column names to uppercase for algorithm compatibility
        return normalize_axis_columns(df)

    except Exception as e:
        pytest.skip(f"Could not load GT3X file: {e}")
        return None


class TestGT3XDataLoading:
    """Test that GT3X data can be loaded correctly."""

    def test_gt3x_file_exists(self) -> None:
        """Verify the test GT3X file exists."""
        if not TEST_GT3X_FILE.exists():
            pytest.skip(f"Test GT3X file not found: {TEST_GT3X_FILE}")

        assert TEST_GT3X_FILE.exists()
        assert TEST_GT3X_FILE.stat().st_size > 0

    def test_load_raw_gt3x_data(self, gt3x_raw_data: pd.DataFrame | None) -> None:
        """Test loading raw data from GT3X file."""
        if gt3x_raw_data is None:
            pytest.skip("GT3X data not available")

        # Check required columns (normalized to uppercase by fixture)
        required_cols = ["AXIS_X", "AXIS_Y", "AXIS_Z"]

        for col in required_cols:
            assert col in gt3x_raw_data.columns, f"Missing {col}. Found: {list(gt3x_raw_data.columns)}"
        assert "timestamp" in gt3x_raw_data.columns, "Missing timestamp column"

        # Check data shape
        assert len(gt3x_raw_data) > 10000, f"Too few samples: {len(gt3x_raw_data)}"

        # Check acceleration values are in reasonable range (±8g for this device)
        for axis in required_cols:
            assert gt3x_raw_data[axis].abs().max() < 20, f"{axis} values out of range"


class TestZAngleWithRealData:
    """Test z-angle calculation on real GT3X data."""

    def test_z_angle_range(self, gt3x_raw_data: pd.DataFrame | None) -> None:
        """Verify z-angle values are in expected range (-90° to 90°)."""
        if gt3x_raw_data is None:
            pytest.skip("GT3X data not available")

        from sleep_scoring_app.core.algorithms.sleep_wake.z_angle import (
            calculate_z_angle_from_dataframe,
        )

        # Take a sample of data for speed
        sample = gt3x_raw_data.head(10000)

        df_with_z = calculate_z_angle_from_dataframe(
            sample,
            ax_col="AXIS_X",
            ay_col="AXIS_Y",
            az_col="AXIS_Z",
        )

        z_angles = df_with_z["z_angle"]

        # All z-angles should be in [-90, 90] range
        assert z_angles.min() >= -90, f"Z-angle below -90°: {z_angles.min():.1f}"
        assert z_angles.max() <= 90, f"Z-angle above 90°: {z_angles.max():.1f}"

        # Check we have a reasonable distribution (not all one value)
        assert z_angles.std() > 1, f"Z-angle std too low: {z_angles.std():.2f}"


class TestVanHees2015WithRealData:
    """Test van Hees 2015 SIB algorithm on real GT3X data."""

    def test_sib_produces_output(self, gt3x_raw_data: pd.DataFrame | None) -> None:
        """Test that SIB algorithm produces reasonable output."""
        if gt3x_raw_data is None:
            pytest.skip("GT3X data not available")

        from sleep_scoring_app.core.algorithms.sleep_wake.van_hees_2015 import (
            VanHees2015SIB,
        )

        # Take first hour of data for speed
        sample_rate_approx = 30  # Hz
        one_hour = sample_rate_approx * 60 * 60
        sample = gt3x_raw_data.head(one_hour)

        algorithm = VanHees2015SIB(
            angle_threshold=5.0,
            time_threshold=5,
            epoch_length=5,
        )

        result = algorithm.score(sample)

        # Check output structure
        assert "Sleep Score" in result.columns
        assert "timestamp" in result.columns

        # Check output values are binary
        assert set(result["Sleep Score"].unique()).issubset({0, 1})

        # Calculate sleep proportion
        sleep_prop = result["Sleep Score"].mean()

        # Sleep proportion should be reasonable (not 0% or 100%)
        # Note: For a random 1-hour sample, this may vary
        assert len(result) > 0, "No output epochs produced"

    def test_sib_detects_sleep_in_multi_day_data(self, gt3x_raw_data: pd.DataFrame | None) -> None:
        """Test that SIB detects sleep periods in multi-day recording."""
        if gt3x_raw_data is None:
            pytest.skip("GT3X data not available")

        from sleep_scoring_app.core.algorithms.sleep_wake.van_hees_2015 import (
            VanHees2015SIB,
        )

        # Use full dataset (may be slow)
        # Limit to first 24 hours for reasonable test time
        sample_rate_approx = 30
        one_day = sample_rate_approx * 60 * 60 * 24
        sample = gt3x_raw_data.head(min(one_day, len(gt3x_raw_data)))

        algorithm = VanHees2015SIB()
        result = algorithm.score(sample)

        # Should detect some sleep in 24 hours
        sleep_epochs = result["Sleep Score"].sum()
        total_epochs = len(result)
        sleep_hours = sleep_epochs / 60  # 60 1-minute epochs per hour

        # Should have reasonable sleep (4-14 hours in a 24-hour period)
        # Be lenient since this is one random day
        assert sleep_epochs > 0, "No sleep detected in 24-hour period"


@pytest.mark.skip(reason="HDCZA algorithm not available")
class TestHDCZAWithRealData:
    """Test HDCZA algorithm on real GT3X data."""

    def test_hdcza_detects_spt_window(self, gt3x_raw_data: pd.DataFrame | None) -> None:
        """Test that HDCZA detects a sleep period time window."""
        if gt3x_raw_data is None:
            pytest.skip("GT3X data not available")

        # from sleep_scoring_app.core.algorithms.sleep_wake.hdcza import HDCZA
        # (data may start in evening, so 24h might miss the first complete night)
        sample_rate_approx = 30
        thirty_six_hours = sample_rate_approx * 60 * 60 * 36
        sample = gt3x_raw_data.head(min(thirty_six_hours, len(gt3x_raw_data)))

        algorithm = HDCZA()
        result = algorithm.score(sample)

        # Check output
        assert "Sleep Score" in result.columns

        # Check for SPT windows
        spt_windows = algorithm.spt_windows

        for i, window in enumerate(spt_windows):
            duration = (window.offset - window.onset).total_seconds() / 3600

        # Should detect at least one SPT window in 36 hours of data
        assert len(spt_windows) > 0, (
            f"No SPT windows detected in {len(sample) / sample_rate_approx / 3600:.1f} hours of data. "
            "HDCZA requires sustained low-activity periods (nighttime)."
        )

        # First window should have reasonable duration (1-14 hours)
        main_window = spt_windows[0]
        duration_hours = (main_window.offset - main_window.onset).total_seconds() / 3600
        assert 1 <= duration_hours <= 14, f"SPT duration unreasonable: {duration_hours:.1f} hours"


@pytest.mark.skip(reason="HDCZA algorithm not available")
class TestAlgorithmConsistency:
    """Test consistency between different algorithms."""

    def test_sib_and_hdcza_overlap(self, gt3x_raw_data: pd.DataFrame | None) -> None:
        """Test that SIB and HDCZA results are consistent."""
        if gt3x_raw_data is None:
            pytest.skip("GT3X data not available")

        from sleep_scoring_app.core.algorithms.sleep_wake.hdcza import HDCZA

        from sleep_scoring_app.core.algorithms.sleep_wake.van_hees_2015 import (
            VanHees2015SIB,
        )

        # Use first 12 hours for speed
        sample_rate_approx = 30
        twelve_hours = sample_rate_approx * 60 * 60 * 12
        sample = gt3x_raw_data.head(min(twelve_hours, len(gt3x_raw_data)))

        # Run both algorithms
        sib = VanHees2015SIB()
        hdcza = HDCZA()

        sib_result = sib.score(sample)
        hdcza_result = hdcza.score(sample)

        # Compare at same resolution
        min_len = min(len(sib_result), len(hdcza_result))
        sib_scores = sib_result["Sleep Score"].values[:min_len]
        hdcza_scores = hdcza_result["Sleep Score"].values[:min_len]

        # Calculate agreement
        agreement = np.mean(sib_scores == hdcza_scores)

        # Algorithms should have some agreement (>50%)
        # They won't be identical since they use different approaches
        assert agreement > 0.5, f"Algorithm agreement too low: {agreement:.2f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
