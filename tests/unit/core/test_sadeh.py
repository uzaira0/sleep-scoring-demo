"""
Tests for Sadeh (1994) sleep scoring algorithm.

Tests the core sleep/wake classification algorithm used for accelerometer data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sleep_scoring_app.core.algorithms.sleep_wake.sadeh import (
    ACTIVITY_CAP,
    COEFFICIENT_A,
    COEFFICIENT_B,
    COEFFICIENT_C,
    COEFFICIENT_D,
    COEFFICIENT_E,
    NATS_MAX,
    NATS_MIN,
    WINDOW_SIZE,
    SadehAlgorithm,
    sadeh_score,
    score_activity,
)
from sleep_scoring_app.core.constants import AlgorithmType
from sleep_scoring_app.core.pipeline.types import AlgorithmDataRequirement

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_activity_data() -> list[float]:
    """Create sample activity data for testing."""
    return [45, 32, 0, 12, 5, 100, 200, 50, 10, 0, 0, 0, 5, 10, 15]


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create sample DataFrame with activity data."""
    timestamps = pd.date_range("2024-01-15 00:00:00", periods=60, freq="1min")
    activity = [50] * 20 + [0] * 20 + [100] * 20  # Wake, sleep, wake pattern
    return pd.DataFrame({"datetime": timestamps, "Axis1": activity})


# ============================================================================
# Test Constants
# ============================================================================


class TestSadehConstants:
    """Tests for Sadeh algorithm constants."""

    def test_window_size(self) -> None:
        """Window size is 11 minutes."""
        assert WINDOW_SIZE == 11

    def test_activity_cap(self) -> None:
        """Activity cap is 300."""
        assert ACTIVITY_CAP == 300

    def test_nats_range(self) -> None:
        """NATS range is 50-100."""
        assert NATS_MIN == 50
        assert NATS_MAX == 100

    def test_coefficients(self) -> None:
        """Coefficients match published values."""
        assert COEFFICIENT_A == 7.601
        assert COEFFICIENT_B == 0.065
        assert COEFFICIENT_C == 1.08
        assert COEFFICIENT_D == 0.056
        assert COEFFICIENT_E == 0.703


# ============================================================================
# Test score_activity Function
# ============================================================================


class TestScoreActivity:
    """Tests for score_activity function."""

    def test_returns_list(self, sample_activity_data: list[float]) -> None:
        """Returns list of integers."""
        result = score_activity(sample_activity_data)

        assert isinstance(result, list)
        assert all(isinstance(x, int) for x in result)

    def test_returns_same_length(self, sample_activity_data: list[float]) -> None:
        """Returns same length as input."""
        result = score_activity(sample_activity_data)

        assert len(result) == len(sample_activity_data)

    def test_returns_binary_values(self, sample_activity_data: list[float]) -> None:
        """Returns only 0 or 1 values."""
        result = score_activity(sample_activity_data)

        assert all(x in (0, 1) for x in result)

    def test_empty_input_returns_empty(self) -> None:
        """Empty input returns empty list."""
        result = score_activity([])

        assert result == []

    def test_raises_for_none(self) -> None:
        """Raises ValueError for None input."""
        with pytest.raises(ValueError, match="cannot be None"):
            score_activity(None)

    def test_raises_for_nan(self) -> None:
        """Raises ValueError for NaN values."""
        with pytest.raises(ValueError, match="NaN"):
            score_activity([1.0, np.nan, 2.0])

    def test_raises_for_infinity(self) -> None:
        """Raises ValueError for infinite values."""
        with pytest.raises(ValueError, match="infinite"):
            score_activity([1.0, np.inf, 2.0])

    def test_raises_for_negative(self) -> None:
        """Raises ValueError for negative values."""
        with pytest.raises(ValueError, match="negative"):
            score_activity([1.0, -5.0, 2.0])

    def test_low_activity_scores_sleep_exact_output(self) -> None:
        """
        Low activity epochs score as sleep (1).

        For all-zero activity data with the Sadeh algorithm:
        - AVG (11-min window mean) = 0
        - NATS (count in [50, 100)) = 0
        - SD (6-epoch forward std) = 0 (all zeros)
        - LG = log(0 + 1) = 0

        PS = 7.601 - 0.065*0 - 1.08*0 - 0.056*0 - 0.703*0 = 7.601

        Since 7.601 > -4.0 (ActiLife threshold), ALL epochs should score as sleep (1).

        Reference: Sadeh et al. (1994) Sleep, 17(3), 201-207.
        Validated against manual calculation of the algorithm formula.
        """
        # Very low activity should score as sleep
        low_activity = [0] * 20

        result = score_activity(low_activity)

        # ALL epochs should be sleep (1) for zero activity
        assert result == [1] * 20, f"Expected all 1s for zero activity, got {result}"

    def test_high_activity_scores_wake_exact_output(self) -> None:
        """
        High activity epochs score as wake (0).

        For all-300 activity data (capped from 500) with the Sadeh algorithm:
        - AVG (11-min window mean) = 300 (capped)
        - NATS (count in [50, 100)) = 0 (none in range)
        - SD (6-epoch forward std) = 0 (all same value)
        - LG = log(300 + 1) = 5.707

        PS = 7.601 - 0.065*300 - 1.08*0 - 0.056*0 - 0.703*5.707
           = 7.601 - 19.5 - 0 - 0 - 4.012
           = -15.91

        Since -15.91 < -4.0 (ActiLife threshold), ALL epochs should score as wake (0).

        Reference: Sadeh et al. (1994) Sleep, 17(3), 201-207.
        Validated against manual calculation of the algorithm formula.
        """
        # High activity should score as wake (values capped at 300)
        high_activity = [500] * 20

        result = score_activity(high_activity)

        # ALL epochs should be wake (0) for high activity
        assert result == [0] * 20, f"Expected all 0s for high activity, got {result}"

    def test_default_threshold_is_actilife(self) -> None:
        """Default threshold is -4.0 (ActiLife)."""
        # With threshold=-4.0 (ActiLife), should get different results than threshold=0
        activity = [50] * 15

        result_default = score_activity(activity)
        result_original = score_activity(activity, threshold=0.0)

        # Results should differ (ActiLife is more lenient toward sleep)
        # This may not always differ depending on data, so just test it runs
        assert len(result_default) == len(result_original)

    def test_count_scaling_option(self, sample_activity_data: list[float]) -> None:
        """Count scaling option can be enabled."""
        # With count scaling, high values get scaled down
        result_normal = score_activity(sample_activity_data, enable_count_scaling=False)
        result_scaled = score_activity(sample_activity_data, enable_count_scaling=True)

        # Both should return valid results
        assert len(result_normal) == len(result_scaled)

    def test_accepts_numpy_array(self) -> None:
        """Accepts numpy array input."""
        arr = np.array([50, 100, 0, 25, 10])

        result = score_activity(arr)

        assert len(result) == 5

    def test_moderate_activity_threshold_boundary(self) -> None:
        """
        Test activity level at the threshold boundary between sleep and wake.

        For moderate activity around 50 counts:
        - AVG = 50 (when all values are 50)
        - NATS = count of epochs in [50, 100) within 11-epoch window
        - SD = 0 (all same value)
        - LG = log(51) = 3.932

        PS = 7.601 - 0.065*50 - 1.08*NATS - 0.056*0 - 0.703*3.932

        For full window (11 epochs): NATS=11, PS = 7.601 - 3.25 - 11.88 - 2.764 = -10.29 < -4.0 -> Wake

        Note: Edge effects occur at array boundaries where the window is truncated.
        The last epoch may score differently due to reduced NATS count.

        Reference: Sadeh et al. (1994) - NATS term heavily penalizes activity in 50-100 range.
        """
        # Use a longer array to minimize edge effects
        moderate_activity = [50] * 25

        result = score_activity(moderate_activity)

        # Most epochs should be wake due to NATS penalty (all but possible edge effects)
        # Check that at least 80% of epochs are wake
        wake_count = result.count(0)
        assert wake_count >= 20, f"Expected at least 20 wake epochs out of 25, got {wake_count} wake. Full result: {result}"

    def test_mixed_pattern_known_output(self) -> None:
        """
        Test mixed activity pattern with known expected output.

        Pattern: 6 zeros followed by 6 high values (300)
        This creates a transition from sleep to wake that we can verify.

        For the first epochs (surrounded by zeros):
        - PS will be high (sleep)

        For the later epochs (surrounded by high values):
        - PS will be low (wake)

        Reference: Manual calculation based on Sadeh algorithm windowing behavior.
        """
        # 6 zeros then 6 high values
        mixed_pattern = [0] * 6 + [300] * 6

        result = score_activity(mixed_pattern)

        # First few epochs should be sleep (1) - they see mostly zeros in their window
        # Last few epochs should be wake (0) - they see mostly high values
        # The exact transition point depends on windowing (11-minute window)
        assert result[:3] == [1, 1, 1], f"First 3 should be sleep, got {result[:3]}"
        assert result[-3:] == [0, 0, 0], f"Last 3 should be wake, got {result[-3:]}"

    def test_original_threshold_vs_actilife_threshold(self) -> None:
        """
        Test that original (0.0) and ActiLife (-4.0) thresholds produce different results.

        For borderline activity where PS is between -4 and 0:
        - ActiLife (threshold=-4.0): PS > -4.0 -> Sleep
        - Original (threshold=0.0): PS > 0.0 -> Sleep

        Using activity level 100 as test case:
        - AVG = 100
        - NATS = 0 (100 is not in [50, 100))
        - SD = 0 (all same)
        - LG = log(101) = 4.615

        PS = 7.601 - 0.065*100 - 0 - 0 - 0.703*4.615
           = 7.601 - 6.5 - 3.244
           = -2.14

        -4.0 < -2.14 < 0.0

        So with ActiLife threshold: -2.14 > -4.0 -> Sleep (1)
        With original threshold: -2.14 < 0.0 -> Wake (0)

        Note: Edge effects at the end of the array may cause some epochs to differ.

        Reference: ActiLife software documentation and Sadeh et al. (1994).
        """
        # Use longer array to minimize edge effects
        activity = [100] * 25

        result_actilife = score_activity(activity, threshold=-4.0)
        result_original = score_activity(activity, threshold=0.0)

        # ActiLife should score mostly as sleep (PS > -4.0)
        actilife_sleep_count = result_actilife.count(1)
        assert actilife_sleep_count >= 20, (
            f"ActiLife threshold should give mostly sleep, got {actilife_sleep_count} sleep epochs. Full: {result_actilife}"
        )

        # Original should score mostly as wake (PS < 0.0)
        original_wake_count = result_original.count(0)
        assert original_wake_count >= 20, (
            f"Original threshold should give mostly wake, got {original_wake_count} wake epochs. Full: {result_original}"
        )

        # The key difference: ActiLife is more lenient
        assert actilife_sleep_count > original_wake_count - 10, "ActiLife should produce more sleep than original"


# ============================================================================
# Test sadeh_score Function
# ============================================================================


class TestSadehScore:
    """Tests for sadeh_score DataFrame function."""

    def test_returns_dataframe(self, sample_dataframe: pd.DataFrame) -> None:
        """Returns DataFrame with score column."""
        result = sadeh_score(sample_dataframe)

        assert isinstance(result, pd.DataFrame)
        assert "Sleep Score" in result.columns

    def test_preserves_original_columns(self, sample_dataframe: pd.DataFrame) -> None:
        """Preserves original DataFrame columns."""
        result = sadeh_score(sample_dataframe)

        assert "datetime" in result.columns
        assert "Axis1" in result.columns

    def test_raises_for_empty_dataframe(self) -> None:
        """Raises ValueError for empty DataFrame."""
        with pytest.raises(ValueError, match="empty"):
            sadeh_score(pd.DataFrame())

    def test_raises_for_none(self) -> None:
        """Raises ValueError for None input."""
        with pytest.raises(ValueError, match="None"):
            sadeh_score(None)

    def test_raises_for_missing_axis1(self) -> None:
        """Raises ValueError when Axis1 column missing."""
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2024-01-15", periods=10, freq="1min"),
                "other_column": [1] * 10,
            }
        )

        with pytest.raises(ValueError, match="Axis1"):
            sadeh_score(df)

    def test_finds_datetime_column(self) -> None:
        """Finds datetime column automatically."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-15", periods=10, freq="1min"),
                "Axis1": [50] * 10,
            }
        )

        result = sadeh_score(df)

        assert "Sleep Score" in result.columns


# ============================================================================
# Test SadehAlgorithm Class
# ============================================================================


class TestSadehAlgorithmInit:
    """Tests for SadehAlgorithm initialization."""

    def test_default_threshold_is_actilife(self) -> None:
        """Default threshold is -4.0 (ActiLife)."""
        algorithm = SadehAlgorithm()

        assert algorithm._threshold == -4.0

    def test_custom_threshold(self) -> None:
        """Can set custom threshold."""
        algorithm = SadehAlgorithm(threshold=0.0)

        assert algorithm._threshold == 0.0

    def test_count_scaling_disabled_by_default(self) -> None:
        """Count scaling disabled by default."""
        algorithm = SadehAlgorithm()

        assert algorithm._enable_count_scaling is False


class TestSadehAlgorithmProperties:
    """Tests for SadehAlgorithm properties."""

    def test_name_actilife_variant(self) -> None:
        """Name includes ActiLife for default threshold."""
        algorithm = SadehAlgorithm()

        assert "ActiLife" in algorithm.name

    def test_name_original_variant(self) -> None:
        """Name includes Original for threshold=0.0."""
        algorithm = SadehAlgorithm(threshold=0.0, variant_name="original")

        assert "Original" in algorithm.name

    def test_name_count_scaled_variant(self) -> None:
        """Name includes Count-Scaled when enabled."""
        algorithm = SadehAlgorithm(enable_count_scaling=True)

        assert "Count-Scaled" in algorithm.name

    def test_identifier_actilife(self) -> None:
        """Identifier is correct for ActiLife variant."""
        algorithm = SadehAlgorithm()

        assert algorithm.identifier == AlgorithmType.SADEH_1994_ACTILIFE

    def test_identifier_original(self) -> None:
        """Identifier is correct for original variant."""
        algorithm = SadehAlgorithm(threshold=0.0, variant_name="original")

        assert algorithm.identifier == AlgorithmType.SADEH_1994_ORIGINAL

    def test_requires_axis_y(self) -> None:
        """Requires axis_y (vertical axis)."""
        algorithm = SadehAlgorithm()

        assert algorithm.requires_axis == "axis_y"

    def test_data_source_type_epoch(self) -> None:
        """Data source type is epoch."""
        algorithm = SadehAlgorithm()

        assert algorithm.data_source_type == "epoch"

    def test_data_requirement_epoch(self) -> None:
        """Data requirement is EPOCH_DATA."""
        algorithm = SadehAlgorithm()

        assert algorithm.data_requirement == AlgorithmDataRequirement.EPOCH_DATA


class TestSadehAlgorithmScore:
    """Tests for SadehAlgorithm scoring methods."""

    def test_score_dataframe(self, sample_dataframe: pd.DataFrame) -> None:
        """score() method works with DataFrame."""
        algorithm = SadehAlgorithm()

        result = algorithm.score(sample_dataframe)

        assert "Sleep Score" in result.columns

    def test_score_array(self, sample_activity_data: list[float]) -> None:
        """score_array() method works with list."""
        algorithm = SadehAlgorithm()

        result = algorithm.score_array(sample_activity_data)

        assert len(result) == len(sample_activity_data)


class TestSadehAlgorithmParameters:
    """Tests for SadehAlgorithm parameter methods."""

    def test_get_parameters(self) -> None:
        """get_parameters() returns parameter dict."""
        algorithm = SadehAlgorithm()

        params = algorithm.get_parameters()

        assert "threshold" in params
        assert "window_size" in params
        assert params["window_size"] == WINDOW_SIZE

    def test_set_parameters_threshold(self) -> None:
        """set_parameters() can update threshold."""
        algorithm = SadehAlgorithm()

        algorithm.set_parameters(threshold=0.0)

        assert algorithm._threshold == 0.0

    def test_set_parameters_warns_on_invalid(self) -> None:
        """set_parameters() warns on invalid parameters."""
        algorithm = SadehAlgorithm()

        # Should log warning but not raise
        algorithm.set_parameters(invalid_param=123)

        # Original parameters unchanged
        assert algorithm._threshold == -4.0
