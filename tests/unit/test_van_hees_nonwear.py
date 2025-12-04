"""
Unit tests for van Hees (2023) nonwear detection algorithm.

Tests the van Hees algorithm implementation for raw accelerometer data.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from sleep_scoring_app.core.algorithms.nonwear_detection_protocol import NonwearDetectionAlgorithm
from sleep_scoring_app.core.algorithms.van_hees import VanHeesNonwearAlgorithm


class TestVanHeesAlgorithmCreation:
    """Tests for van Hees algorithm instantiation."""

    def test_create_with_defaults(self) -> None:
        """Test creating algorithm with default parameters."""
        algorithm = VanHeesNonwearAlgorithm()
        assert algorithm is not None
        assert algorithm.name == "van Hees (2023)"
        assert algorithm.identifier == "van_hees_2023"

    def test_create_with_custom_parameters(self) -> None:
        """Test creating algorithm with custom parameters."""
        algorithm = VanHeesNonwearAlgorithm(
            sd_criterion=0.020,
            range_criterion=0.20,
            medium_epoch_sec=600,
            sample_freq=50.0,
        )
        params = algorithm.get_parameters()
        assert params["sd_criterion"] == 0.020
        assert params["range_criterion"] == 0.20
        assert params["medium_epoch_sec"] == 600
        assert params["sample_freq"] == 50.0

    def test_implements_protocol(self) -> None:
        """Test that algorithm implements NonwearDetectionAlgorithm protocol."""
        algorithm = VanHeesNonwearAlgorithm()
        assert isinstance(algorithm, NonwearDetectionAlgorithm)


class TestVanHeesAlgorithmProperties:
    """Tests for algorithm properties."""

    def test_name_property(self) -> None:
        """Test name property returns correct value."""
        algorithm = VanHeesNonwearAlgorithm()
        assert algorithm.name == "van Hees (2023)"

    def test_identifier_property(self) -> None:
        """Test identifier property returns correct value."""
        algorithm = VanHeesNonwearAlgorithm()
        assert algorithm.identifier == "van_hees_2023"


class TestVanHeesAlgorithmParameters:
    """Tests for algorithm parameter management."""

    def test_get_parameters_returns_dict(self) -> None:
        """Test get_parameters returns dictionary."""
        algorithm = VanHeesNonwearAlgorithm()
        params = algorithm.get_parameters()
        assert isinstance(params, dict)

    def test_get_parameters_has_all_params(self) -> None:
        """Test get_parameters includes all parameters."""
        algorithm = VanHeesNonwearAlgorithm()
        params = algorithm.get_parameters()
        assert "sd_criterion" in params
        assert "range_criterion" in params
        assert "medium_epoch_sec" in params
        assert "sample_freq" in params

    def test_get_parameters_default_values(self) -> None:
        """Test get_parameters returns correct default values."""
        algorithm = VanHeesNonwearAlgorithm()
        params = algorithm.get_parameters()
        assert params["sd_criterion"] == 0.013
        assert params["range_criterion"] == 0.15
        assert params["medium_epoch_sec"] == 900
        assert params["sample_freq"] == 100.0

    def test_set_parameters_updates_values(self) -> None:
        """Test set_parameters updates parameter values."""
        algorithm = VanHeesNonwearAlgorithm()
        algorithm.set_parameters(sd_criterion=0.020, range_criterion=0.25)
        params = algorithm.get_parameters()
        assert params["sd_criterion"] == 0.020
        assert params["range_criterion"] == 0.25

    def test_set_parameters_invalid_name_raises(self) -> None:
        """Test set_parameters raises ValueError for invalid parameter name."""
        algorithm = VanHeesNonwearAlgorithm()
        with pytest.raises(ValueError, match="Invalid parameter"):
            algorithm.set_parameters(invalid_param=123)

    def test_set_parameters_invalid_sd_criterion_raises(self) -> None:
        """Test set_parameters raises ValueError for invalid sd_criterion."""
        algorithm = VanHeesNonwearAlgorithm()
        with pytest.raises(ValueError, match="sd_criterion must be positive"):
            algorithm.set_parameters(sd_criterion=-0.01)
        with pytest.raises(ValueError, match="sd_criterion must be positive"):
            algorithm.set_parameters(sd_criterion=0)

    def test_set_parameters_invalid_range_criterion_raises(self) -> None:
        """Test set_parameters raises ValueError for invalid range_criterion."""
        algorithm = VanHeesNonwearAlgorithm()
        with pytest.raises(ValueError, match="range_criterion must be positive"):
            algorithm.set_parameters(range_criterion=-0.1)
        with pytest.raises(ValueError, match="range_criterion must be positive"):
            algorithm.set_parameters(range_criterion=0)

    def test_set_parameters_invalid_medium_epoch_sec_raises(self) -> None:
        """Test set_parameters raises ValueError for invalid medium_epoch_sec."""
        algorithm = VanHeesNonwearAlgorithm()
        with pytest.raises(ValueError, match="medium_epoch_sec must be positive"):
            algorithm.set_parameters(medium_epoch_sec=0)
        with pytest.raises(ValueError, match="medium_epoch_sec must be positive"):
            algorithm.set_parameters(medium_epoch_sec=-100)

    def test_set_parameters_invalid_sample_freq_raises(self) -> None:
        """Test set_parameters raises ValueError for invalid sample_freq."""
        algorithm = VanHeesNonwearAlgorithm()
        with pytest.raises(ValueError, match="sample_freq must be positive"):
            algorithm.set_parameters(sample_freq=0)
        with pytest.raises(ValueError, match="sample_freq must be positive"):
            algorithm.set_parameters(sample_freq=-50)


class TestVanHeesAlgorithmDetect:
    """Tests for detect() method."""

    def test_detect_with_none_activity_data_raises(self) -> None:
        """Test detect raises ValueError for None activity data."""
        algorithm = VanHeesNonwearAlgorithm()
        timestamps = [datetime(2000, 1, 1)]
        with pytest.raises(ValueError, match="activity_data cannot be None"):
            algorithm.detect(None, timestamps)

    def test_detect_with_none_timestamps_raises(self) -> None:
        """Test detect raises ValueError for None timestamps."""
        algorithm = VanHeesNonwearAlgorithm()
        data = np.zeros((100, 3))
        with pytest.raises(ValueError, match="timestamps cannot be None"):
            algorithm.detect(data, None)

    def test_detect_with_mismatched_lengths_raises(self) -> None:
        """Test detect raises ValueError for mismatched lengths."""
        algorithm = VanHeesNonwearAlgorithm()
        data = np.zeros((100, 3))
        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i) for i in range(50)]
        with pytest.raises(ValueError, match="Timestamps length.*must match data length"):
            algorithm.detect(data, timestamps)

    def test_detect_with_empty_data_returns_empty_list(self) -> None:
        """Test detect returns empty list for empty data."""
        algorithm = VanHeesNonwearAlgorithm()
        data = np.array([]).reshape(0, 3)
        timestamps = []
        result = algorithm.detect(data, timestamps)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_detect_with_1d_data_creates_synthetic_3axis(self) -> None:
        """Test detect handles 1D data by creating synthetic 3-axis data."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=1.0, medium_epoch_sec=10)
        # Create 20 seconds of data at 1 Hz (20 samples)
        data = np.zeros(20)  # 1D array
        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i) for i in range(20)]

        # Should not raise error
        result = algorithm.detect(data, timestamps)
        assert isinstance(result, list)

    def test_detect_with_invalid_shape_raises(self) -> None:
        """Test detect raises ValueError for invalid data shape."""
        algorithm = VanHeesNonwearAlgorithm()
        data = np.zeros((100, 2))  # Only 2 axes instead of 3
        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i) for i in range(100)]
        with pytest.raises(ValueError, match="Expected 2D array with shape"):
            algorithm.detect(data, timestamps)

    def test_detect_with_wear_data_returns_empty_periods(self) -> None:
        """Test detect returns no periods for data with clear wear (high activity)."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=1.0, medium_epoch_sec=10)
        # Create 20 seconds of high-variability wear data at 1 Hz
        np.random.seed(42)
        data = np.random.randn(20, 3) * 0.5  # High SD and range
        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i) for i in range(20)]

        result = algorithm.detect(data, timestamps)
        assert isinstance(result, list)
        # Should have no nonwear periods due to high variability
        assert len(result) == 0

    def test_detect_with_nonwear_data_returns_periods(self) -> None:
        """Test detect returns periods for data with clear nonwear (low activity)."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=1.0, medium_epoch_sec=10)
        # Create 30 seconds of low-variability nonwear data at 1 Hz
        # All values very similar (low SD and range)
        data = np.ones((30, 3)) * 1.0  # Constant values (SD = 0, range = 0)
        data += np.random.randn(30, 3) * 0.001  # Tiny noise (SD < 0.013, range < 0.15)
        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i) for i in range(30)]

        result = algorithm.detect(data, timestamps)
        assert isinstance(result, list)
        # Should detect nonwear periods
        assert len(result) > 0

    def test_detect_returns_nonwear_period_objects(self) -> None:
        """Test detect returns NonwearPeriod objects."""
        from sleep_scoring_app.core.dataclasses import NonwearPeriod

        algorithm = VanHeesNonwearAlgorithm(sample_freq=1.0, medium_epoch_sec=10)
        # Create nonwear data
        data = np.ones((30, 3)) * 1.0
        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i) for i in range(30)]

        result = algorithm.detect(data, timestamps)
        if len(result) > 0:
            assert all(isinstance(p, NonwearPeriod) for p in result)


class TestVanHeesAlgorithmDetectMask:
    """Tests for detect_mask() method."""

    def test_detect_mask_with_none_data_raises(self) -> None:
        """Test detect_mask raises ValueError for None data."""
        algorithm = VanHeesNonwearAlgorithm()
        with pytest.raises(ValueError, match="activity_data cannot be None"):
            algorithm.detect_mask(None)

    def test_detect_mask_with_empty_data_returns_empty_list(self) -> None:
        """Test detect_mask returns empty list for empty data."""
        algorithm = VanHeesNonwearAlgorithm()
        data = np.array([]).reshape(0, 3)
        result = algorithm.detect_mask(data)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_detect_mask_returns_binary_values(self) -> None:
        """Test detect_mask returns only 0 and 1 values."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=1.0, medium_epoch_sec=10)
        data = np.random.randn(100, 3)
        result = algorithm.detect_mask(data)
        assert all(v in [0, 1] for v in result)

    def test_detect_mask_with_wear_data_returns_zeros(self) -> None:
        """Test detect_mask returns zeros for wear data."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=1.0, medium_epoch_sec=10)
        # High variability wear data
        np.random.seed(42)
        data = np.random.randn(100, 3) * 0.5
        result = algorithm.detect_mask(data)
        # Should be mostly wear (0s)
        assert sum(result) < len(result) * 0.5

    def test_detect_mask_with_nonwear_data_returns_ones(self) -> None:
        """Test detect_mask returns ones for nonwear data."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=1.0, medium_epoch_sec=10)
        # Low variability nonwear data
        data = np.ones((100, 3)) * 1.0
        data += np.random.randn(100, 3) * 0.001
        result = algorithm.detect_mask(data)
        # Should be mostly nonwear (1s)
        assert sum(result) > len(result) * 0.5

    def test_detect_mask_handles_1d_data(self) -> None:
        """Test detect_mask handles 1D data."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=1.0, medium_epoch_sec=10)
        data = np.zeros(100)  # 1D array
        result = algorithm.detect_mask(data)
        assert isinstance(result, list)
        assert all(v in [0, 1] for v in result)

    def test_detect_mask_with_invalid_shape_raises(self) -> None:
        """Test detect_mask raises ValueError for invalid shape."""
        algorithm = VanHeesNonwearAlgorithm()
        data = np.zeros((100, 2))  # Only 2 axes
        with pytest.raises(ValueError, match="Expected 2D array with shape"):
            algorithm.detect_mask(data)


class TestVanHeesAlgorithmFactoryIntegration:
    """Tests for factory integration."""

    def test_factory_creates_van_hees_algorithm(self) -> None:
        """Test factory can create van Hees algorithm."""
        from sleep_scoring_app.core.algorithms.nonwear_factory import NonwearAlgorithmFactory

        algorithm = NonwearAlgorithmFactory.create("van_hees_2023")
        assert algorithm is not None
        assert algorithm.name == "van Hees (2023)"
        assert algorithm.identifier == "van_hees_2023"

    def test_factory_returns_van_hees_instance(self) -> None:
        """Test factory returns VanHeesNonwearAlgorithm instance."""
        from sleep_scoring_app.core.algorithms.nonwear_factory import NonwearAlgorithmFactory

        algorithm = NonwearAlgorithmFactory.create("van_hees_2023")
        assert isinstance(algorithm, VanHeesNonwearAlgorithm)

    def test_factory_registered_in_available_algorithms(self) -> None:
        """Test van Hees algorithm is listed in available algorithms."""
        from sleep_scoring_app.core.algorithms.nonwear_factory import NonwearAlgorithmFactory

        available = NonwearAlgorithmFactory.get_available_algorithms()
        assert "van_hees_2023" in available
        assert available["van_hees_2023"] == "van Hees (2023)"

    def test_factory_is_registered_returns_true(self) -> None:
        """Test factory reports van Hees as registered."""
        from sleep_scoring_app.core.algorithms.nonwear_factory import NonwearAlgorithmFactory

        assert NonwearAlgorithmFactory.is_registered("van_hees_2023") is True

    def test_factory_creates_with_default_parameters(self) -> None:
        """Test factory creates algorithm with correct default parameters."""
        from sleep_scoring_app.core.algorithms.nonwear_factory import NonwearAlgorithmFactory

        algorithm = NonwearAlgorithmFactory.create("van_hees_2023")
        params = algorithm.get_parameters()
        assert params["sd_criterion"] == 0.013
        assert params["range_criterion"] == 0.15
        assert params["medium_epoch_sec"] == 900
        assert params["sample_freq"] == 100.0


class TestVanHeesAlgorithmRealistic:
    """Realistic scenario tests with synthetic accelerometer data."""

    def test_realistic_wear_scenario(self) -> None:
        """Test with realistic wear scenario (walking data)."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=100.0, medium_epoch_sec=900)

        # Create 30 minutes of simulated walking data at 100 Hz
        # 30 min * 60 sec/min * 100 Hz = 180,000 samples
        n_samples = 30 * 60 * 100

        # Simulate walking: periodic acceleration with noise
        t = np.arange(n_samples) / 100.0  # Time in seconds
        # Y-axis (vertical): dominant walking signal
        y = np.sin(2 * np.pi * 2.0 * t) * 0.3 + np.random.randn(n_samples) * 0.05
        # X-axis (lateral): smaller variation
        x = np.sin(2 * np.pi * 1.8 * t) * 0.1 + np.random.randn(n_samples) * 0.03
        # Z-axis (forward): smaller variation
        z = np.sin(2 * np.pi * 2.2 * t) * 0.1 + np.random.randn(n_samples) * 0.03

        data = np.column_stack([x, y, z])
        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i / 100.0) for i in range(n_samples)]

        result = algorithm.detect(data, timestamps)

        # Should detect no nonwear periods (high variability = wearing)
        assert len(result) == 0

    def test_realistic_nonwear_scenario(self) -> None:
        """Test with realistic nonwear scenario (device on table)."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=100.0, medium_epoch_sec=900)

        # Create 30 minutes of simulated nonwear data at 100 Hz
        n_samples = 30 * 60 * 100

        # Simulate device on table: gravity + tiny sensor noise
        # Y-axis: ~1g (gravity, device laying flat)
        y = np.ones(n_samples) * 1.0 + np.random.randn(n_samples) * 0.001
        # X-axis: ~0g
        x = np.zeros(n_samples) + np.random.randn(n_samples) * 0.001
        # Z-axis: ~0g
        z = np.zeros(n_samples) + np.random.randn(n_samples) * 0.001

        data = np.column_stack([x, y, z])
        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i / 100.0) for i in range(n_samples)]

        result = algorithm.detect(data, timestamps)

        # Should detect nonwear period (very low variability)
        assert len(result) > 0

    def test_realistic_mixed_scenario(self) -> None:
        """Test with mixed wear and nonwear scenario."""
        algorithm = VanHeesNonwearAlgorithm(sample_freq=100.0, medium_epoch_sec=900)

        # Create 60 minutes: 15 min wear + 30 min nonwear + 15 min wear
        n_samples = 60 * 60 * 100

        # First 15 minutes: wear
        n_wear1 = 15 * 60 * 100
        t1 = np.arange(n_wear1) / 100.0
        y1 = np.sin(2 * np.pi * 2.0 * t1) * 0.3 + np.random.randn(n_wear1) * 0.05
        x1 = np.sin(2 * np.pi * 1.8 * t1) * 0.1 + np.random.randn(n_wear1) * 0.03
        z1 = np.sin(2 * np.pi * 2.2 * t1) * 0.1 + np.random.randn(n_wear1) * 0.03

        # Middle 30 minutes: nonwear
        n_nonwear = 30 * 60 * 100
        y2 = np.ones(n_nonwear) * 1.0 + np.random.randn(n_nonwear) * 0.001
        x2 = np.zeros(n_nonwear) + np.random.randn(n_nonwear) * 0.001
        z2 = np.zeros(n_nonwear) + np.random.randn(n_nonwear) * 0.001

        # Last 15 minutes: wear
        n_wear2 = 15 * 60 * 100
        t3 = np.arange(n_wear2) / 100.0
        y3 = np.sin(2 * np.pi * 2.0 * t3) * 0.3 + np.random.randn(n_wear2) * 0.05
        x3 = np.sin(2 * np.pi * 1.8 * t3) * 0.1 + np.random.randn(n_wear2) * 0.03
        z3 = np.sin(2 * np.pi * 2.2 * t3) * 0.1 + np.random.randn(n_wear2) * 0.03

        # Combine
        x = np.concatenate([x1, x2, x3])
        y = np.concatenate([y1, y2, y3])
        z = np.concatenate([z1, z2, z3])
        data = np.column_stack([x, y, z])

        timestamps = [datetime(2000, 1, 1) + timedelta(seconds=i / 100.0) for i in range(n_samples)]

        result = algorithm.detect(data, timestamps)

        # Should detect at least one nonwear period in the middle
        assert len(result) > 0

        # The nonwear period should be roughly in the middle 30 minutes
        if len(result) > 0:
            # Check that at least one period overlaps with the nonwear section
            nonwear_start_time = timestamps[n_wear1]
            nonwear_end_time = timestamps[n_wear1 + n_nonwear]

            overlaps = any(period.start_time < nonwear_end_time and period.end_time > nonwear_start_time for period in result)
            assert overlaps
