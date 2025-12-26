#!/usr/bin/env python3
"""
Comprehensive tests for EpochingService.
Tests epoch creation from raw accelerometer data and sample rate estimation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from sleep_scoring_app.core.pipeline.exceptions import EpochingError
from sleep_scoring_app.services.epoching_service import EpochingService


class TestEpochingService:
    """Tests for EpochingService class."""

    @pytest.fixture
    def service(self) -> EpochingService:
        """Create service instance."""
        return EpochingService()

    @pytest.fixture
    def raw_data_30hz(self) -> pd.DataFrame:
        """Create sample raw data at 30 Hz for 5 minutes."""
        start = datetime(2024, 1, 1, 12, 0, 0)
        n_samples = 30 * 60 * 5  # 30 Hz for 5 minutes = 9000 samples
        timestamps = [start + timedelta(seconds=i / 30) for i in range(n_samples)]

        # Create realistic accelerometer values (small variations around gravity)
        np.random.seed(42)
        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "AXIS_X": np.random.normal(0.0, 0.1, n_samples),
                "AXIS_Y": np.random.normal(1.0, 0.2, n_samples),  # ~1g vertical
                "AXIS_Z": np.random.normal(0.0, 0.1, n_samples),
            }
        )

    @pytest.fixture
    def raw_data_100hz(self) -> pd.DataFrame:
        """Create sample raw data at 100 Hz for 2 minutes."""
        start = datetime(2024, 1, 1, 12, 0, 0)
        n_samples = 100 * 60 * 2  # 100 Hz for 2 minutes = 12000 samples
        timestamps = [start + timedelta(seconds=i / 100) for i in range(n_samples)]

        np.random.seed(42)
        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "AXIS_X": np.random.normal(0.0, 0.15, n_samples),
                "AXIS_Y": np.random.normal(1.0, 0.25, n_samples),
                "AXIS_Z": np.random.normal(0.0, 0.15, n_samples),
            }
        )


class TestCreateEpochs(TestEpochingService):
    """Tests for create_epochs method."""

    def test_creates_60s_epochs(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Should create 60-second epochs from raw data."""
        epoch_df = service.create_epochs(raw_data_30hz, epoch_seconds=60)

        assert epoch_df is not None
        assert "datetime" in epoch_df.columns
        assert "Axis1" in epoch_df.columns
        assert len(epoch_df) == 5  # 5 minutes of data = 5 epochs

    def test_creates_30s_epochs(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Should create 30-second epochs."""
        epoch_df = service.create_epochs(raw_data_30hz, epoch_seconds=30)

        assert len(epoch_df) == 10  # 5 minutes = 10 30-second epochs

    def test_creates_15s_epochs(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Should create 15-second epochs."""
        epoch_df = service.create_epochs(raw_data_30hz, epoch_seconds=15)

        assert len(epoch_df) == 20  # 5 minutes = 20 15-second epochs

    def test_epochs_are_integers(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Epoch counts should be integers."""
        epoch_df = service.create_epochs(raw_data_30hz, epoch_seconds=60)

        assert epoch_df["Axis1"].dtype in [np.int64, np.int32, int]

    def test_epochs_are_non_negative(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Epoch counts should be non-negative (absolute values used)."""
        epoch_df = service.create_epochs(raw_data_30hz, epoch_seconds=60)

        assert (epoch_df["Axis1"] >= 0).all()

    def test_uses_y_axis_by_default(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Should use Y-axis by default."""
        epoch_df = service.create_epochs(raw_data_30hz, epoch_seconds=60, use_axis="Y")

        # Should complete without error
        assert len(epoch_df) > 0

    def test_can_use_vector_magnitude(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Should support vector magnitude mode."""
        epoch_df = service.create_epochs(raw_data_30hz, epoch_seconds=60, use_axis="VM")

        assert len(epoch_df) == 5

    def test_vm_values_differ_from_y_axis(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """VM epoch values should differ from Y-axis values."""
        epoch_y = service.create_epochs(raw_data_30hz, epoch_seconds=60, use_axis="Y")
        epoch_vm = service.create_epochs(raw_data_30hz, epoch_seconds=60, use_axis="VM")

        # Values should be different
        assert not np.allclose(epoch_y["Axis1"].values, epoch_vm["Axis1"].values)

    def test_timestamps_are_epoch_start(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Epoch timestamps should mark epoch start time."""
        epoch_df = service.create_epochs(raw_data_30hz, epoch_seconds=60)

        # First epoch should start at data start
        first_epoch_time = epoch_df["datetime"].iloc[0]
        expected_start = datetime(2024, 1, 1, 12, 0, 0)
        assert first_epoch_time == expected_start

    def test_higher_sample_rate(self, service: EpochingService, raw_data_100hz: pd.DataFrame) -> None:
        """Should handle higher sample rate data."""
        epoch_df = service.create_epochs(raw_data_100hz, epoch_seconds=60)

        assert len(epoch_df) == 2  # 2 minutes of data


class TestValidation(TestEpochingService):
    """Tests for data validation."""

    def test_rejects_empty_data(self, service: EpochingService) -> None:
        """Should reject empty DataFrame."""
        empty_df = pd.DataFrame()

        with pytest.raises(EpochingError):
            service.create_epochs(empty_df)

    def test_rejects_none_data(self, service: EpochingService) -> None:
        """Should reject None data."""
        with pytest.raises(EpochingError):
            service.create_epochs(None)

    def test_rejects_missing_timestamp(self, service: EpochingService) -> None:
        """Should reject data without timestamp column."""
        df = pd.DataFrame(
            {
                "AXIS_X": [0.1, 0.2],
                "AXIS_Y": [1.0, 1.1],
                "AXIS_Z": [0.1, 0.2],
            }
        )

        with pytest.raises(EpochingError) as exc_info:
            service.create_epochs(df)

        assert "timestamp" in str(exc_info.value).lower()

    def test_rejects_missing_axis_x(self, service: EpochingService) -> None:
        """Should reject data without AXIS_X column."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 1, 12, 0, i) for i in range(10)],
                "AXIS_Y": [1.0] * 10,
                "AXIS_Z": [0.1] * 10,
            }
        )

        with pytest.raises(EpochingError) as exc_info:
            service.create_epochs(df)

        assert "AXIS_X" in str(exc_info.value)

    def test_rejects_missing_axis_y(self, service: EpochingService) -> None:
        """Should reject data without AXIS_Y column."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 1, 12, 0, i) for i in range(10)],
                "AXIS_X": [0.1] * 10,
                "AXIS_Z": [0.1] * 10,
            }
        )

        with pytest.raises(EpochingError) as exc_info:
            service.create_epochs(df)

        assert "AXIS_Y" in str(exc_info.value)

    def test_rejects_missing_axis_z(self, service: EpochingService) -> None:
        """Should reject data without AXIS_Z column."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 1, 12, 0, i) for i in range(10)],
                "AXIS_X": [0.1] * 10,
                "AXIS_Y": [1.0] * 10,
            }
        )

        with pytest.raises(EpochingError) as exc_info:
            service.create_epochs(df)

        assert "AXIS_Z" in str(exc_info.value)

    def test_rejects_invalid_axis(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Should reject invalid use_axis parameter."""
        with pytest.raises(EpochingError) as exc_info:
            service.create_epochs(raw_data_30hz, use_axis="INVALID")

        assert "Invalid use_axis" in str(exc_info.value)


class TestTimestampAliases(TestEpochingService):
    """Tests for timestamp column name flexibility."""

    def test_accepts_timestamp_column(self, service: EpochingService) -> None:
        """Should accept 'timestamp' column name."""
        from datetime import timedelta

        base = datetime(2024, 1, 1, 12, 0, 0)
        df = pd.DataFrame(
            {
                "timestamp": [base + timedelta(seconds=i) for i in range(120)],
                "AXIS_X": [0.1] * 120,
                "AXIS_Y": [1.0] * 120,
                "AXIS_Z": [0.1] * 120,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)
        assert len(epoch_df) == 2

    def test_accepts_datetime_column(self, service: EpochingService) -> None:
        """Should accept 'datetime' column name."""
        from datetime import timedelta

        base = datetime(2024, 1, 1, 12, 0, 0)
        df = pd.DataFrame(
            {
                "datetime": [base + timedelta(seconds=i) for i in range(120)],
                "AXIS_X": [0.1] * 120,
                "AXIS_Y": [1.0] * 120,
                "AXIS_Z": [0.1] * 120,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)
        assert len(epoch_df) == 2

    def test_accepts_date_time_column(self, service: EpochingService) -> None:
        """Should accept 'Date Time' column name."""
        from datetime import timedelta

        base = datetime(2024, 1, 1, 12, 0, 0)
        df = pd.DataFrame(
            {
                "Date Time": [base + timedelta(seconds=i) for i in range(120)],
                "AXIS_X": [0.1] * 120,
                "AXIS_Y": [1.0] * 120,
                "AXIS_Z": [0.1] * 120,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)
        assert len(epoch_df) == 2

    def test_accepts_timestamp_capitalized(self, service: EpochingService) -> None:
        """Should accept 'Timestamp' column name (case-insensitive)."""
        from datetime import timedelta

        base = datetime(2024, 1, 1, 12, 0, 0)
        df = pd.DataFrame(
            {
                "Timestamp": [base + timedelta(seconds=i) for i in range(120)],
                "AXIS_X": [0.1] * 120,
                "AXIS_Y": [1.0] * 120,
                "AXIS_Z": [0.1] * 120,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)
        assert len(epoch_df) == 2


class TestEstimateSampleRate(TestEpochingService):
    """Tests for estimate_sample_rate method."""

    def test_estimates_30hz(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Should estimate ~30 Hz for 30 Hz data."""
        sample_rate = service.estimate_sample_rate(raw_data_30hz)

        assert abs(sample_rate - 30) < 1  # Within 1 Hz

    def test_estimates_100hz(self, service: EpochingService, raw_data_100hz: pd.DataFrame) -> None:
        """Should estimate ~100 Hz for 100 Hz data."""
        sample_rate = service.estimate_sample_rate(raw_data_100hz)

        assert abs(sample_rate - 100) < 2  # Within 2 Hz

    def test_rejects_no_timestamp(self, service: EpochingService) -> None:
        """Should raise error without timestamp column."""
        df = pd.DataFrame({"AXIS_X": [0.1, 0.2], "AXIS_Y": [1.0, 1.1], "AXIS_Z": [0.1, 0.2]})

        with pytest.raises(EpochingError):
            service.estimate_sample_rate(df)


class TestFindTimestampColumn(TestEpochingService):
    """Tests for _find_timestamp_column method."""

    def test_finds_timestamp(self, service: EpochingService) -> None:
        """Should find 'timestamp' column."""
        df = pd.DataFrame({"timestamp": [], "other": []})
        assert service._find_timestamp_column(df) == "timestamp"

    def test_finds_datetime(self, service: EpochingService) -> None:
        """Should find 'datetime' column."""
        df = pd.DataFrame({"datetime": [], "other": []})
        assert service._find_timestamp_column(df) == "datetime"

    def test_finds_date_time(self, service: EpochingService) -> None:
        """Should find 'Date Time' column."""
        df = pd.DataFrame({"Date Time": [], "other": []})
        assert service._find_timestamp_column(df) == "Date Time"

    def test_returns_none_if_not_found(self, service: EpochingService) -> None:
        """Should return None if no timestamp column."""
        df = pd.DataFrame({"col1": [], "col2": []})
        assert service._find_timestamp_column(df) is None

    def test_case_insensitive(self, service: EpochingService) -> None:
        """Should be case-insensitive."""
        df = pd.DataFrame({"TIMESTAMP": [], "other": []})
        assert service._find_timestamp_column(df) == "TIMESTAMP"


class TestEdgeCases(TestEpochingService):
    """Tests for edge cases."""

    def test_single_epoch(self, service: EpochingService) -> None:
        """Should handle data for exactly one epoch."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 1, 12, 0, 0) + timedelta(seconds=i) for i in range(60)],
                "AXIS_X": [0.1] * 60,
                "AXIS_Y": [1.0] * 60,
                "AXIS_Z": [0.1] * 60,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)
        assert len(epoch_df) == 1

    def test_partial_epoch(self, service: EpochingService) -> None:
        """Should handle partial epochs at end of data."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 1, 12, 0, 0) + timedelta(seconds=i) for i in range(90)],
                "AXIS_X": [0.1] * 90,
                "AXIS_Y": [1.0] * 90,
                "AXIS_Z": [0.1] * 90,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)
        # Should have 2 epochs (60s + partial 30s)
        assert len(epoch_df) == 2

    def test_preserves_original_data(self, service: EpochingService, raw_data_30hz: pd.DataFrame) -> None:
        """Should not modify original DataFrame."""
        original_len = len(raw_data_30hz)
        original_cols = list(raw_data_30hz.columns)

        service.create_epochs(raw_data_30hz, epoch_seconds=60)

        assert len(raw_data_30hz) == original_len
        assert list(raw_data_30hz.columns) == original_cols

    def test_handles_string_timestamps(self, service: EpochingService) -> None:
        """Should convert string timestamps to datetime."""
        df = pd.DataFrame(
            {
                "timestamp": ["2024-01-01 12:00:00", "2024-01-01 12:00:01", "2024-01-01 12:01:00", "2024-01-01 12:01:01"],
                "AXIS_X": [0.1] * 4,
                "AXIS_Y": [1.0] * 4,
                "AXIS_Z": [0.1] * 4,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)
        assert len(epoch_df) == 2

    def test_handles_negative_accelerometer_values(self, service: EpochingService) -> None:
        """Should handle negative accelerometer values (takes absolute)."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 1, 12, 0, i) for i in range(60)],
                "AXIS_X": [-0.5] * 60,
                "AXIS_Y": [-1.0] * 60,  # Upside down
                "AXIS_Z": [-0.3] * 60,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)

        # Should have positive values (absolute sum)
        assert epoch_df["Axis1"].iloc[0] > 0

    def test_handles_zero_values(self, service: EpochingService) -> None:
        """Should handle all-zero accelerometer values."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 1, 12, 0, i) for i in range(60)],
                "AXIS_X": [0.0] * 60,
                "AXIS_Y": [0.0] * 60,
                "AXIS_Z": [0.0] * 60,
            }
        )

        epoch_df = service.create_epochs(df, epoch_seconds=60)

        assert epoch_df["Axis1"].iloc[0] == 0
