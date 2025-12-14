"""
Tests for algorithm-data compatibility system.

These tests verify that the compatibility registry and checker correctly
identify valid and invalid algorithm-data combinations.
"""

from __future__ import annotations

import pytest

from sleep_scoring_app.core.algorithms.compatibility import (
    AlgorithmCategory,
    AlgorithmCompatibilityInfo,
    AlgorithmCompatibilityRegistry,
    AlgorithmDataCompatibilityChecker,
    CompatibilityResult,
    CompatibilityStatus,
)
from sleep_scoring_app.core.pipeline.types import (
    AlgorithmDataRequirement,
    DataSourceType,
    PipelineType,
)


class TestAlgorithmCompatibilityRegistry:
    """Test the algorithm compatibility registry."""

    def test_get_algorithm_info(self):
        """Test retrieving algorithm information."""
        # Get Sadeh ActiLife
        info = AlgorithmCompatibilityRegistry.get("sadeh_1994_actilife")
        assert info is not None
        assert info.algorithm_id == "sadeh_1994_actilife"
        assert info.display_name == "Sadeh (1994) ActiLife"
        assert info.data_requirement == AlgorithmDataRequirement.EPOCH_DATA
        assert info.category == AlgorithmCategory.EPOCH_BASED

    def test_get_unknown_algorithm(self):
        """Test retrieving unknown algorithm returns None."""
        info = AlgorithmCompatibilityRegistry.get("nonexistent_algorithm")
        assert info is None

    def test_get_compatible_with_epoch_data(self):
        """Test finding algorithms compatible with epoch CSV data."""
        compatible = AlgorithmCompatibilityRegistry.get_compatible(DataSourceType.CSV_EPOCH)

        # Should only return epoch-based algorithms
        assert len(compatible) > 0
        for algo in compatible:
            assert algo.data_requirement == AlgorithmDataRequirement.EPOCH_DATA
            assert algo.category == AlgorithmCategory.EPOCH_BASED

        # Verify specific algorithms are included
        algo_ids = {algo.algorithm_id for algo in compatible}
        assert "sadeh_1994_actilife" in algo_ids
        assert "cole_kripke_1992_original" in algo_ids

        # Verify raw-data algorithms are excluded
        assert "van_hees_2015_sib" not in algo_ids
        assert "hdcza_2018" not in algo_ids

    def test_get_compatible_with_raw_data(self):
        """Test finding algorithms compatible with raw GT3X data."""
        compatible = AlgorithmCompatibilityRegistry.get_compatible(DataSourceType.GT3X_RAW)

        # Should return ALL algorithms (raw can be epoched if needed)
        assert len(compatible) > 0

        algo_ids = {algo.algorithm_id for algo in compatible}

        # Both epoch-based and raw-data algorithms should be included
        assert "sadeh_1994_actilife" in algo_ids  # Epoch-based (will be epoched)
        assert "van_hees_2015_sib" in algo_ids  # Raw-data (direct)

    def test_is_compatible_epoch_csv_with_sadeh(self):
        """Test that Sadeh is compatible with epoch CSV."""
        is_compat = AlgorithmCompatibilityRegistry.is_compatible(
            DataSourceType.CSV_EPOCH,
            "sadeh_1994_actilife",
        )
        assert is_compat is True

    def test_is_compatible_epoch_csv_with_van_hees(self):
        """Test that van Hees SIB is NOT compatible with epoch CSV."""
        is_compat = AlgorithmCompatibilityRegistry.is_compatible(
            DataSourceType.CSV_EPOCH,
            "van_hees_2015_sib",
        )
        assert is_compat is False

    def test_is_compatible_gt3x_with_van_hees(self):
        """Test that van Hees SIB is compatible with GT3X."""
        is_compat = AlgorithmCompatibilityRegistry.is_compatible(
            DataSourceType.GT3X_RAW,
            "van_hees_2015_sib",
        )
        assert is_compat is True

    def test_get_all_algorithms(self):
        """Test retrieving all registered algorithms."""
        all_algos = AlgorithmCompatibilityRegistry.get_all()
        assert len(all_algos) >= 8  # At least 6 epoch-based + 2 raw-data

        # Verify mix of categories
        categories = {algo.category for algo in all_algos}
        assert AlgorithmCategory.EPOCH_BASED in categories
        assert AlgorithmCategory.RAW_DATA in categories

    def test_get_by_category_epoch_based(self):
        """Test filtering algorithms by epoch-based category."""
        epoch_algos = AlgorithmCompatibilityRegistry.get_by_category(AlgorithmCategory.EPOCH_BASED)

        assert len(epoch_algos) >= 6  # Sadeh x3, Cole-Kripke x3
        for algo in epoch_algos:
            assert algo.category == AlgorithmCategory.EPOCH_BASED
            assert algo.data_requirement == AlgorithmDataRequirement.EPOCH_DATA

    def test_get_by_category_raw_data(self):
        """Test filtering algorithms by raw-data category."""
        raw_algos = AlgorithmCompatibilityRegistry.get_by_category(AlgorithmCategory.RAW_DATA)

        assert len(raw_algos) >= 2  # van Hees SIB, HDCZA
        for algo in raw_algos:
            assert algo.category == AlgorithmCategory.RAW_DATA
            assert algo.data_requirement == AlgorithmDataRequirement.RAW_DATA


class TestAlgorithmDataCompatibilityChecker:
    """Test the compatibility checker implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = AlgorithmDataCompatibilityChecker()

    def test_check_compatible_epoch_direct(self):
        """Test compatible combination: Epoch CSV + Sadeh."""
        result = self.checker.check(
            DataSourceType.CSV_EPOCH,
            "sadeh_1994_actilife",
        )

        assert result.status == CompatibilityStatus.COMPATIBLE
        assert result.pipeline_type == PipelineType.EPOCH_DIRECT
        assert result.data_source == DataSourceType.CSV_EPOCH
        assert result.algorithm_id == "sadeh_1994_actilife"
        assert "compatible" in result.reason.lower()
        assert len(result.suggested_alternatives) == 0  # No alternatives needed

    def test_check_incompatible_epoch_with_raw_algo(self):
        """Test incompatible combination: Epoch CSV + van Hees SIB."""
        result = self.checker.check(
            DataSourceType.CSV_EPOCH,
            "van_hees_2015_sib",
        )

        assert result.status == CompatibilityStatus.INCOMPATIBLE
        assert result.pipeline_type is None
        assert result.data_source == DataSourceType.CSV_EPOCH
        assert result.algorithm_id == "van_hees_2015_sib"
        assert "raw" in result.reason.lower()
        assert len(result.suggested_alternatives) > 0  # Should suggest alternatives

        # Verify alternatives are epoch-based
        for alt_id in result.suggested_alternatives:
            alt_info = AlgorithmCompatibilityRegistry.get(alt_id)
            assert alt_info.data_requirement == AlgorithmDataRequirement.EPOCH_DATA

    def test_check_requires_preprocessing_gt3x_with_sadeh(self):
        """Test combination requiring preprocessing: GT3X + Sadeh."""
        result = self.checker.check(
            DataSourceType.GT3X_RAW,
            "sadeh_1994_actilife",
        )

        assert result.status == CompatibilityStatus.REQUIRES_PREPROCESSING
        assert result.pipeline_type == PipelineType.RAW_TO_EPOCH
        assert "epoched" in result.reason.lower()
        assert len(result.suggested_alternatives) == 0  # No alternatives needed

    def test_check_compatible_raw_to_raw(self):
        """Test compatible raw combination: GT3X + van Hees SIB."""
        result = self.checker.check(
            DataSourceType.GT3X_RAW,
            "van_hees_2015_sib",
        )

        assert result.status == CompatibilityStatus.COMPATIBLE
        assert result.pipeline_type == PipelineType.RAW_TO_RAW
        assert "compatible" in result.reason.lower()

    def test_get_incompatibility_reason_valid(self):
        """Test getting incompatibility reason for invalid combination."""
        reason = self.checker.get_incompatibility_reason(
            DataSourceType.CSV_EPOCH,
            "van_hees_2015_sib",
        )

        assert len(reason) > 0
        assert "raw" in reason.lower()

    def test_get_incompatibility_reason_compatible(self):
        """Test getting incompatibility reason for valid combination returns empty."""
        reason = self.checker.get_incompatibility_reason(
            DataSourceType.CSV_EPOCH,
            "sadeh_1994_actilife",
        )

        assert reason == ""

    def test_suggest_alternatives_for_epoch_csv(self):
        """Test suggesting alternatives for epoch CSV data."""
        alternatives = self.checker.suggest_alternatives(DataSourceType.CSV_EPOCH)

        assert len(alternatives) > 0
        assert "sadeh_1994_actilife" in alternatives
        assert "cole_kripke_1992_original" in alternatives

        # Raw-data algorithms should NOT be suggested
        assert "van_hees_2015_sib" not in alternatives
        assert "hdcza_2018" not in alternatives

    def test_suggest_alternatives_for_gt3x(self):
        """Test suggesting alternatives for GT3X raw data."""
        alternatives = self.checker.suggest_alternatives(DataSourceType.GT3X_RAW)

        assert len(alternatives) > 0

        # All algorithms should be suggested (raw can be epoched)
        assert "sadeh_1994_actilife" in alternatives
        assert "van_hees_2015_sib" in alternatives

    def test_check_unknown_algorithm(self):
        """Test checking compatibility with unknown algorithm."""
        result = self.checker.check(
            DataSourceType.CSV_EPOCH,
            "nonexistent_algorithm",
        )

        assert result.status == CompatibilityStatus.INCOMPATIBLE
        assert result.pipeline_type is None
        assert "unknown" in result.reason.lower()


class TestCompatibilityMatrix:
    """Test the complete compatibility matrix."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = AlgorithmDataCompatibilityChecker()

    @pytest.mark.parametrize(
        "data_source,algorithm_id,expected_status,expected_pipeline",
        [
            # GT3X (raw) combinations
            (DataSourceType.GT3X_RAW, "sadeh_1994_actilife", CompatibilityStatus.REQUIRES_PREPROCESSING, PipelineType.RAW_TO_EPOCH),
            (DataSourceType.GT3X_RAW, "cole_kripke_1992_original", CompatibilityStatus.REQUIRES_PREPROCESSING, PipelineType.RAW_TO_EPOCH),
            (DataSourceType.GT3X_RAW, "van_hees_2015_sib", CompatibilityStatus.COMPATIBLE, PipelineType.RAW_TO_RAW),
            (DataSourceType.GT3X_RAW, "hdcza_2018", CompatibilityStatus.COMPATIBLE, PipelineType.RAW_TO_RAW),
            # Raw CSV combinations
            (DataSourceType.CSV_RAW, "sadeh_1994_actilife", CompatibilityStatus.REQUIRES_PREPROCESSING, PipelineType.RAW_TO_EPOCH),
            (DataSourceType.CSV_RAW, "van_hees_2015_sib", CompatibilityStatus.COMPATIBLE, PipelineType.RAW_TO_RAW),
            # Epoch CSV combinations
            (DataSourceType.CSV_EPOCH, "sadeh_1994_actilife", CompatibilityStatus.COMPATIBLE, PipelineType.EPOCH_DIRECT),
            (DataSourceType.CSV_EPOCH, "cole_kripke_1992_original", CompatibilityStatus.COMPATIBLE, PipelineType.EPOCH_DIRECT),
            (DataSourceType.CSV_EPOCH, "van_hees_2015_sib", CompatibilityStatus.INCOMPATIBLE, None),
            (DataSourceType.CSV_EPOCH, "hdcza_2018", CompatibilityStatus.INCOMPATIBLE, None),
        ],
    )
    def test_compatibility_matrix(
        self,
        data_source,
        algorithm_id,
        expected_status,
        expected_pipeline,
    ):
        """Test the complete compatibility matrix."""
        result = self.checker.check(data_source, algorithm_id)

        assert result.status == expected_status, f"Expected {expected_status} for {data_source.value} + {algorithm_id}, got {result.status}"
        assert result.pipeline_type == expected_pipeline, (
            f"Expected {expected_pipeline} for {data_source.value} + {algorithm_id}, got {result.pipeline_type}"
        )
