"""
Unit tests for van Hees sleep detection algorithms.

Tests cover:
    - Z-angle calculation utilities
    - van Hees 2015 (SIB) algorithm
    - HDCZA (van Hees 2018) algorithm

"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sleep_scoring_app.core.algorithms.sleep_period import HDCZA
from sleep_scoring_app.core.algorithms.sleep_wake import (
    VanHees2015SIB,
    calculate_z_angle_from_arrays,
    calculate_z_angle_from_dataframe,
    resample_to_epochs,
    split_into_noon_to_noon_days,
    validate_raw_accelerometer_data,
)


class TestZAngleCalculation:
    """Test z-angle calculation utilities."""

    def test_calculate_z_angle_horizontal(self):
        """Test z-angle calculation for horizontal orientation (0°)."""
        # When az=0 and ax,ay form horizontal plane, z-angle should be ~0°
        ax = np.array([1.0, 0.0, 0.5])
        ay = np.array([0.0, 1.0, 0.5])
        az = np.array([0.0, 0.0, 0.0])

        z_angle = calculate_z_angle_from_arrays(ax, ay, az)

        # All should be very close to 0°
        assert np.allclose(z_angle, 0.0, atol=0.1)

    def test_calculate_z_angle_vertical_up(self):
        """Test z-angle calculation for vertical up orientation (+90°)."""
        # When az dominates and is positive, z-angle should be ~+90°
        ax = np.array([0.0, 0.0, 0.0])
        ay = np.array([0.0, 0.0, 0.0])
        az = np.array([1.0, 1.0, 1.0])

        z_angle = calculate_z_angle_from_arrays(ax, ay, az)

        # All should be very close to +90°
        assert np.allclose(z_angle, 90.0, atol=0.1)

    def test_calculate_z_angle_vertical_down(self):
        """Test z-angle calculation for vertical down orientation (-90°)."""
        # When az is negative and dominates, z-angle should be ~-90°
        ax = np.array([0.0, 0.0, 0.0])
        ay = np.array([0.0, 0.0, 0.0])
        az = np.array([-1.0, -1.0, -1.0])

        z_angle = calculate_z_angle_from_arrays(ax, ay, az)

        # All should be very close to -90°
        assert np.allclose(z_angle, -90.0, atol=0.1)

    def test_calculate_z_angle_45_degrees(self):
        """Test z-angle calculation for 45° angle."""
        # When az equals horizontal magnitude, angle is 45°
        ax = np.array([0.7071])  # cos(45°)
        ay = np.array([0.0])
        az = np.array([0.7071])  # sin(45°)

        z_angle = calculate_z_angle_from_arrays(ax, ay, az)

        # Should be close to 45°
        assert np.allclose(z_angle, 45.0, atol=1.0)

    def test_calculate_z_angle_invalid_arrays(self):
        """Test z-angle calculation with invalid inputs."""
        # Different lengths
        with pytest.raises(ValueError, match="same length"):
            calculate_z_angle_from_arrays(
                np.array([1.0, 2.0]),
                np.array([1.0]),
                np.array([1.0, 2.0]),
            )

        # Empty arrays
        with pytest.raises(ValueError, match="cannot be empty"):
            calculate_z_angle_from_arrays(
                np.array([]),
                np.array([]),
                np.array([]),
            )

        # NaN values (must set allow_nan=False to raise)
        with pytest.raises(ValueError, match="NaN"):
            calculate_z_angle_from_arrays(
                np.array([1.0, np.nan]),
                np.array([1.0, 1.0]),
                np.array([1.0, 1.0]),
                allow_nan=False,
            )

    def test_calculate_z_angle_from_dataframe(self):
        """Test z-angle calculation from DataFrame."""
        df = pd.DataFrame(
            {
                "AXIS_X": [1.0, 0.0, 0.0],
                "AXIS_Y": [0.0, 1.0, 0.0],
                "AXIS_Z": [0.0, 0.0, 1.0],
            }
        )

        result = calculate_z_angle_from_dataframe(df)

        assert "z_angle" in result.columns
        assert len(result) == 3
        # First row: horizontal, should be ~0°
        assert abs(result["z_angle"].iloc[0]) < 1.0
        # Last row: vertical, should be ~90°
        assert abs(result["z_angle"].iloc[2] - 90.0) < 1.0

    def test_calculate_z_angle_from_dataframe_missing_columns(self):
        """Test z-angle calculation with missing columns."""
        df = pd.DataFrame(
            {
                "AXIS_X": [1.0, 0.0],
                "AXIS_Y": [0.0, 1.0],
                # Missing AXIS_Z
            }
        )

        with pytest.raises(ValueError, match="missing required columns"):
            calculate_z_angle_from_dataframe(df)


class TestResamplingUtilities:
    """Test data resampling utilities."""

    def test_resample_to_epochs_median(self):
        """Test resampling to epochs using median aggregation."""
        # Create 100 samples at 1Hz (100 seconds)
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="1s"),
                "value": np.random.randn(100) + 50.0,
            }
        )

        # Resample to 10-second epochs
        result = resample_to_epochs(df, "timestamp", "value", 10, "median")

        # Should have 10 epochs
        assert len(result) == 10
        assert "timestamp" in result.columns
        assert "value" in result.columns

    def test_resample_to_epochs_mean(self):
        """Test resampling to epochs using mean aggregation."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=60, freq="1s"),
                "value": np.ones(60) * 10.0,
            }
        )

        result = resample_to_epochs(df, "timestamp", "value", 5, "mean")

        # Should have 12 five-second epochs
        assert len(result) == 12
        # All values should be 10.0 (mean of constant values)
        assert np.allclose(result["value"], 10.0)

    def test_resample_invalid_aggregation(self):
        """Test resampling with invalid aggregation method."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=60, freq="1s"),
                "value": np.ones(60),
            }
        )

        with pytest.raises(ValueError, match="Invalid aggregation"):
            resample_to_epochs(df, "timestamp", "value", 5, "invalid_method")


class TestNoonToNoonSplit:
    """Test noon-to-noon day splitting."""

    def test_split_into_noon_to_noon_days(self):
        """Test splitting multi-day recording into noon-to-noon segments."""
        # Create 72 hours of data (3 days)
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01 08:00", periods=72, freq="1h"),
                "value": range(72),
            }
        )

        days = split_into_noon_to_noon_days(df, "timestamp")

        # Should have multiple day segments
        assert len(days) > 0
        assert all(isinstance(day, pd.DataFrame) for day in days)

        # Each segment should have data
        assert all(len(day) > 0 for day in days)

    def test_split_single_day(self):
        """Test splitting single day of data."""
        # Create 24 hours starting at midnight
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01 00:00", periods=24, freq="1h"),
                "value": range(24),
            }
        )

        days = split_into_noon_to_noon_days(df, "timestamp")

        # Should have at least one segment
        assert len(days) >= 1


class TestRawDataValidation:
    """Test raw accelerometer data validation."""

    def test_validate_valid_raw_data(self):
        """Test validation of valid raw accelerometer data."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=1000, freq="0.1s"),
                "AXIS_X": np.random.randn(1000) * 0.5,
                "AXIS_Y": np.random.randn(1000) * 0.5,
                "AXIS_Z": np.random.randn(1000) * 0.5 + 1.0,  # Gravity
            }
        )

        is_valid, errors = validate_raw_accelerometer_data(df)

        assert is_valid
        assert len(errors) == 0

    def test_validate_missing_columns(self):
        """Test validation with missing columns."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="0.1s"),
                "AXIS_X": np.random.randn(100),
                # Missing AXIS_Y and AXIS_Z
            }
        )

        is_valid, errors = validate_raw_accelerometer_data(df)

        assert not is_valid
        assert any("missing" in err.lower() for err in errors)

    def test_validate_unreasonable_values(self):
        """Test validation with unreasonable acceleration values."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="0.1s"),
                "AXIS_X": np.ones(100) * 50.0,  # Unreasonably high
                "AXIS_Y": np.ones(100),
                "AXIS_Z": np.ones(100),
            }
        )

        is_valid, errors = validate_raw_accelerometer_data(df)

        # Should warn about unreasonable values
        assert not is_valid or len(errors) > 0

    def test_validate_insufficient_data(self):
        """Test validation with insufficient data."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="1s"),
                "AXIS_X": np.ones(10),
                "AXIS_Y": np.ones(10),
                "AXIS_Z": np.ones(10),
            }
        )

        is_valid, errors = validate_raw_accelerometer_data(df)

        assert not is_valid
        assert any("insufficient" in err.lower() for err in errors)


class TestVanHees2015SIB:
    """Test van Hees 2015 (SIB) algorithm."""

    def test_algorithm_properties(self):
        """Test algorithm properties."""
        algorithm = VanHees2015SIB()

        assert algorithm.name == "van Hees (2015) SIB"
        assert algorithm.identifier == "van_hees_2015_sib"
        assert algorithm.requires_axis == "raw_triaxial"
        assert algorithm.data_source_type == "raw"

    def test_algorithm_parameters(self):
        """Test getting and setting parameters."""
        algorithm = VanHees2015SIB(angle_threshold=10.0, time_threshold=3)

        params = algorithm.get_parameters()
        assert params["angle_threshold"] == 10.0
        assert params["time_threshold"] == 3

        # Update parameters
        algorithm.set_parameters(angle_threshold=7.5)
        assert algorithm.get_parameters()["angle_threshold"] == 7.5

    def test_score_rejects_epoch_data(self):
        """Test that algorithm rejects pre-aggregated epoch data."""
        algorithm = VanHees2015SIB()

        # Create DataFrame that looks like epoch data (missing raw data columns)
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="60s"),
                "Axis1": np.random.randint(0, 100, 100),
                "Activity": np.random.randint(0, 100, 100),
            }
        )

        # Should raise ValueError about missing columns or invalid data
        with pytest.raises(ValueError, match="(Invalid raw accelerometer data|Missing required columns)"):
            algorithm.score(df)

    def test_score_valid_raw_data(self):
        """Test scoring with valid raw accelerometer data."""
        algorithm = VanHees2015SIB()

        # Create synthetic raw accelerometer data (30 minutes at 10Hz)
        n_samples = 30 * 60 * 10  # 18000 samples
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01 22:00", periods=n_samples, freq="0.1s"),
                "AXIS_X": np.random.randn(n_samples) * 0.1,
                "AXIS_Y": np.random.randn(n_samples) * 0.1,
                "AXIS_Z": np.random.randn(n_samples) * 0.1 + 1.0,  # Mostly vertical
            }
        )

        result = algorithm.score(df)

        # Check output structure
        assert "timestamp" in result.columns
        assert "Sleep Score" in result.columns
        assert len(result) > 0
        assert result["Sleep Score"].dtype == np.int64
        assert set(result["Sleep Score"].unique()).issubset({0, 1})

    def test_score_array_not_supported(self):
        """Test that score_array raises NotImplementedError."""
        algorithm = VanHees2015SIB()

        with pytest.raises(NotImplementedError, match="RAW tri-axial"):
            algorithm.score_array([1, 2, 3])


class TestHDCZA:
    """Test HDCZA (van Hees 2018) algorithm."""

    def test_algorithm_properties(self):
        """Test algorithm properties."""
        algorithm = HDCZA()

        assert algorithm.name == "HDCZA (van Hees 2018)"
        assert algorithm.identifier == "hdcza_2018"
        assert algorithm.requires_axis == "raw_triaxial"
        assert algorithm.data_source_type == "raw"

    def test_algorithm_parameters(self):
        """Test getting and setting parameters."""
        algorithm = HDCZA(
            angle_threshold_multiplier=20.0,
            percentile=15.0,
            min_block_duration=45,
        )

        params = algorithm.get_parameters()
        assert params["angle_threshold_multiplier"] == 20.0
        assert params["percentile"] == 15.0
        assert params["min_block_duration"] == 45

        # Update parameters
        algorithm.set_parameters(min_block_duration=30)
        assert algorithm.get_parameters()["min_block_duration"] == 30

    def test_score_rejects_epoch_data(self):
        """Test that algorithm rejects pre-aggregated epoch data."""
        algorithm = HDCZA()

        # Create DataFrame that looks like epoch data (missing raw data columns)
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="60s"),
                "Axis1": np.random.randint(0, 100, 100),
            }
        )

        # Should raise ValueError about missing columns or invalid data
        with pytest.raises(ValueError, match="(Invalid raw accelerometer data|Missing required columns)"):
            algorithm.score(df)

    def test_score_valid_raw_data(self):
        """Test scoring with valid raw accelerometer data."""
        algorithm = HDCZA()

        # Create synthetic raw accelerometer data (24 hours at 10Hz)
        # This is a full day to test noon-to-noon splitting
        n_samples = 24 * 60 * 60 * 10  # 864000 samples
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01 12:00", periods=n_samples, freq="0.1s"),
                "AXIS_X": np.random.randn(n_samples) * 0.1,
                "AXIS_Y": np.random.randn(n_samples) * 0.1,
                "AXIS_Z": np.random.randn(n_samples) * 0.1 + 1.0,
            }
        )

        result = algorithm.score(df)

        # Check output structure
        assert "timestamp" in result.columns
        assert "Sleep Score" in result.columns
        assert len(result) > 0
        assert result["Sleep Score"].dtype == np.int64
        assert set(result["Sleep Score"].unique()).issubset({0, 1})

    def test_spt_windows_property(self):
        """Test that SPT windows are accessible after scoring."""
        algorithm = HDCZA()

        # Create synthetic data
        n_samples = 24 * 60 * 60 * 10
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01 12:00", periods=n_samples, freq="0.1s"),
                "AXIS_X": np.random.randn(n_samples) * 0.1,
                "AXIS_Y": np.random.randn(n_samples) * 0.1,
                "AXIS_Z": np.random.randn(n_samples) * 0.1 + 1.0,
            }
        )

        algorithm.score(df)

        # Check that SPT windows were detected
        windows = algorithm.spt_windows
        assert isinstance(windows, list)
        # Note: May or may not detect windows depending on synthetic data

    def test_score_array_not_supported(self):
        """Test that score_array raises NotImplementedError."""
        algorithm = HDCZA()

        with pytest.raises(NotImplementedError, match="RAW tri-axial"):
            algorithm.score_array([1, 2, 3])


class TestAlgorithmIntegration:
    """Integration tests for algorithm interoperability."""

    def test_both_algorithms_produce_compatible_output(self):
        """Test that both algorithms produce compatible output format."""
        # Create test data
        n_samples = 30 * 60 * 10  # 30 minutes at 10Hz
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01 22:00", periods=n_samples, freq="0.1s"),
                "AXIS_X": np.random.randn(n_samples) * 0.1,
                "AXIS_Y": np.random.randn(n_samples) * 0.1,
                "AXIS_Z": np.random.randn(n_samples) * 0.1 + 1.0,
            }
        )

        # Test van Hees 2015
        sib = VanHees2015SIB()
        result_sib = sib.score(df.copy())

        # Test HDCZA
        hdcza = HDCZA()
        result_hdcza = hdcza.score(df.copy())

        # Both should have same columns
        assert "timestamp" in result_sib.columns
        assert "Sleep Score" in result_sib.columns
        assert "timestamp" in result_hdcza.columns
        assert "Sleep Score" in result_hdcza.columns

        # Both should have values in {0, 1}
        assert set(result_sib["Sleep Score"].unique()).issubset({0, 1})
        assert set(result_hdcza["Sleep Score"].unique()).issubset({0, 1})
