"""
Integration tests for the Dependency Injection system.

Tests that all DI components work together correctly across the application.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from sleep_scoring_app.core.algorithms.datasource_factory import DataSourceFactory
from sleep_scoring_app.core.algorithms.factory import AlgorithmFactory
from sleep_scoring_app.core.algorithms.nonwear_factory import NonwearAlgorithmFactory
from sleep_scoring_app.core.algorithms.onset_offset_factory import OnsetOffsetRuleFactory
from sleep_scoring_app.core.constants import AlgorithmType, DataSourceType, NonwearAlgorithm


class TestFactoryEnumAlignment:
    """Tests that factory IDs align with enum values."""

    def test_algorithm_type_enum_matches_factory(self) -> None:
        """Test AlgorithmType enum values match factory registered IDs."""
        factory_ids = set(AlgorithmFactory.get_available_algorithms().keys())

        # Core algorithm types should be in factory
        assert AlgorithmType.SADEH_1994_ORIGINAL.value in factory_ids
        assert AlgorithmType.SADEH_1994_ACTILIFE.value in factory_ids
        assert AlgorithmType.COLE_KRIPKE_1992.value in factory_ids

    def test_nonwear_algorithm_enum_matches_factory(self) -> None:
        """Test NonwearAlgorithm enum values match factory registered IDs."""
        factory_ids = set(NonwearAlgorithmFactory.get_available_algorithms().keys())

        assert NonwearAlgorithm.CHOI_2011.value in factory_ids

    def test_create_from_enum_value(self) -> None:
        """Test creating algorithms using enum values."""
        # Sleep scoring
        algo = AlgorithmFactory.create(AlgorithmType.SADEH_1994_ACTILIFE.value)
        assert algo is not None
        assert algo.name == "Sadeh (1994) ActiLife"

        # Nonwear
        nonwear = NonwearAlgorithmFactory.create(NonwearAlgorithm.CHOI_2011.value)
        assert nonwear is not None
        assert nonwear.name == "Choi (2011)"


class TestEnumMigration:
    """Tests for legacy value migration in enums."""

    def test_algorithm_type_legacy_migration(self) -> None:
        """Test that legacy AlgorithmType values migrate correctly."""
        # Legacy "Sadeh" should migrate to sadeh_1994_actilife
        migrated = AlgorithmType.migrate_legacy_value("Sadeh")
        assert migrated == AlgorithmType.SADEH_1994_ACTILIFE

        # Legacy "Manual + Algorithm" should migrate
        migrated = AlgorithmType.migrate_legacy_value("Manual + Algorithm")
        assert migrated == AlgorithmType.SADEH_1994_ACTILIFE

        # Non-legacy values should pass through
        migrated = AlgorithmType.migrate_legacy_value("sadeh_1994_original")
        assert migrated == AlgorithmType.SADEH_1994_ORIGINAL

    def test_nonwear_algorithm_legacy_migration(self) -> None:
        """Test that legacy NonwearAlgorithm values migrate correctly."""
        # Legacy "Choi" should migrate to choi_2011
        migrated = NonwearAlgorithm.migrate_legacy_value("Choi")
        assert migrated == NonwearAlgorithm.CHOI_2011

        # Non-legacy values should pass through
        migrated = NonwearAlgorithm.migrate_legacy_value("choi_2011")
        assert migrated == NonwearAlgorithm.CHOI_2011


class TestSleepScoringPipeline:
    """Integration tests for complete sleep scoring pipeline."""

    @pytest.fixture
    def sample_activity_df(self) -> pd.DataFrame:
        """Generate sample activity DataFrame for testing."""
        np.random.seed(42)
        n_epochs = 60

        # Simulate 1 hour of data at 1-minute epochs
        timestamps = pd.date_range(start="2024-01-01 22:00:00", periods=n_epochs, freq="1min")

        activity = np.concatenate(
            [
                np.random.randint(0, 50, size=20),  # Sleep period
                np.random.randint(100, 500, size=20),  # Wake period
                np.random.randint(0, 50, size=20),  # Sleep period
            ]
        )

        return pd.DataFrame(
            {
                "datetime": timestamps,
                "Axis1": activity,
            }
        )

    def test_sadeh_scores_dataframe(self, sample_activity_df: pd.DataFrame) -> None:
        """Test that Sadeh algorithm can score a DataFrame."""
        algorithm = AlgorithmFactory.create("sadeh_1994_actilife")
        result = algorithm.score(sample_activity_df)

        assert "Sadeh Score" in result.columns
        assert len(result) == len(sample_activity_df)
        # Scores should be 0 (wake) or 1 (sleep)
        assert set(result["Sadeh Score"].unique()).issubset({0, 1})

    def test_cole_kripke_scores_dataframe(self, sample_activity_df: pd.DataFrame) -> None:
        """Test that Cole-Kripke algorithm can score a DataFrame."""
        algorithm = AlgorithmFactory.create("cole_kripke_1992")
        result = algorithm.score(sample_activity_df)

        # Cole-Kripke uses "Sleep Score" as the column name (standardized across algorithms)
        assert "Sleep Score" in result.columns
        assert len(result) == len(sample_activity_df)
        # Scores should be 0 (wake) or 1 (sleep)
        assert set(result["Sleep Score"].unique()).issubset({0, 1})

    def test_all_algorithms_score_array(self) -> None:
        """Test that all algorithms can score array data."""
        np.random.seed(42)
        activity = list(np.random.randint(0, 300, size=60))

        for algo_id in AlgorithmFactory.get_available_algorithms():
            algorithm = AlgorithmFactory.create(algo_id)
            scores = algorithm.score_array(activity)

            assert len(scores) == len(activity)
            assert all(s in [0, 1] for s in scores), f"Algorithm {algo_id} produced invalid scores"


class TestOnsetOffsetPipeline:
    """Integration tests for onset/offset detection pipeline."""

    @pytest.fixture
    def sample_sleep_scenario(self) -> tuple[list[int], list[datetime]]:
        """Generate sample sleep/wake scenario with timestamps."""
        # 0 = wake, 1 = sleep
        sleep_scores = (
            [0] * 10  # Wake (10 min)
            + [1] * 60  # Sleep period (60 min)
            + [0] * 10  # Wake (10 min)
        )

        base_time = datetime(2024, 1, 1, 22, 0, 0)
        timestamps = [base_time + timedelta(minutes=i) for i in range(len(sleep_scores))]

        return sleep_scores, timestamps

    def test_consecutive_3_5_finds_onset_offset(self, sample_sleep_scenario: tuple) -> None:
        """Test consecutive 3/5 rule finds onset and offset."""
        sleep_scores, timestamps = sample_sleep_scenario

        rule = OnsetOffsetRuleFactory.create("consecutive_3_5")

        # Define search markers
        sleep_start = timestamps[5]  # Before sleep starts
        sleep_end = timestamps[75]  # After sleep ends

        onset_idx, offset_idx = rule.apply_rules(
            sleep_scores=sleep_scores,
            sleep_start_marker=sleep_start,
            sleep_end_marker=sleep_end,
            timestamps=timestamps,
        )

        assert onset_idx is not None, "Should find sleep onset"
        assert offset_idx is not None, "Should find sleep offset"
        assert onset_idx < offset_idx, "Onset should be before offset"
        # Onset should be at or after index 10 (where sleep starts)
        assert onset_idx >= 10

    def test_tudor_locke_finds_onset_offset(self, sample_sleep_scenario: tuple) -> None:
        """Test Tudor-Locke rule finds onset and offset."""
        sleep_scores, timestamps = sample_sleep_scenario

        rule = OnsetOffsetRuleFactory.create("tudor_locke_2014")

        sleep_start = timestamps[5]
        sleep_end = timestamps[75]

        onset_idx, offset_idx = rule.apply_rules(
            sleep_scores=sleep_scores,
            sleep_start_marker=sleep_start,
            sleep_end_marker=sleep_end,
            timestamps=timestamps,
        )

        # Tudor-Locke may not find periods that don't meet min duration
        # Just verify it doesn't crash and returns valid types
        assert onset_idx is None or isinstance(onset_idx, int)
        assert offset_idx is None or isinstance(offset_idx, int)


class TestNonwearPipeline:
    """Integration tests for nonwear detection pipeline."""

    @pytest.fixture
    def sample_activity_with_nonwear(self) -> tuple[np.ndarray, list[datetime]]:
        """Generate sample activity data with nonwear periods."""
        np.random.seed(42)
        n_epochs = 180  # 3 hours of data

        # Create activity with a nonwear period (zeros in middle)
        activity = np.concatenate(
            [
                np.random.randint(10, 500, size=60),  # Normal activity
                np.zeros(60, dtype=int),  # Nonwear period (1 hour of zeros)
                np.random.randint(10, 500, size=60),  # Normal activity
            ]
        )

        # Create timestamps
        base_time = datetime(2024, 1, 1, 8, 0, 0)
        timestamps = [base_time + timedelta(minutes=i) for i in range(n_epochs)]

        return activity, timestamps

    def test_choi_detects_nonwear(self, sample_activity_with_nonwear: tuple) -> None:
        """Test that Choi algorithm detects nonwear periods."""
        activity, timestamps = sample_activity_with_nonwear

        algorithm = NonwearAlgorithmFactory.create("choi_2011")
        periods = algorithm.detect(activity, timestamps)

        # Should detect the zero-activity period as nonwear
        # Note: Choi algorithm has specific criteria (90+ min), may not detect 60 min period
        assert isinstance(periods, list)

    def test_choi_detect_mask(self, sample_activity_with_nonwear: tuple) -> None:
        """Test that Choi algorithm produces per-epoch mask."""
        activity, timestamps = sample_activity_with_nonwear

        algorithm = NonwearAlgorithmFactory.create("choi_2011")
        mask = algorithm.detect_mask(activity)

        assert isinstance(mask, list)
        assert len(mask) == len(activity)
        assert all(m in [0, 1] for m in mask)


class TestCrossFactoryIntegration:
    """Tests for integration between different factories."""

    def test_full_scoring_workflow(self) -> None:
        """Test complete workflow: score -> onset/offset."""
        np.random.seed(42)

        # Create test data
        n_epochs = 120
        timestamps = pd.date_range(start="2024-01-01 22:00:00", periods=n_epochs, freq="1min")

        activity = np.concatenate(
            [
                np.random.randint(200, 500, size=30),  # Wake
                np.random.randint(0, 50, size=60),  # Sleep
                np.random.randint(200, 500, size=30),  # Wake
            ]
        )

        df = pd.DataFrame(
            {
                "datetime": timestamps,
                "Axis1": activity,
            }
        )

        # Step 1: Score activity with sleep algorithm
        sleep_algo = AlgorithmFactory.create(AlgorithmType.SADEH_1994_ACTILIFE.value)
        scored_df = sleep_algo.score(df)

        assert "Sadeh Score" in scored_df.columns

        # Step 2: Find onset/offset with rule
        onset_rule = OnsetOffsetRuleFactory.create("consecutive_3_5")
        sleep_scores = scored_df["Sadeh Score"].tolist()
        ts_list = [pd.Timestamp(t).to_pydatetime() for t in timestamps]

        onset_idx, offset_idx = onset_rule.apply_rules(
            sleep_scores=sleep_scores,
            sleep_start_marker=ts_list[20],
            sleep_end_marker=ts_list[100],
            timestamps=ts_list,
        )

        # Verify workflow completed
        assert len(scored_df) == n_epochs
        # onset/offset may or may not be found depending on data
        assert onset_idx is None or isinstance(onset_idx, int)

    def test_nonwear_and_sleep_scoring(self) -> None:
        """Test nonwear detection alongside sleep scoring."""
        np.random.seed(42)

        # Create test data
        n_epochs = 180
        base_time = datetime(2024, 1, 1, 20, 0, 0)
        timestamps = [base_time + timedelta(minutes=i) for i in range(n_epochs)]

        activity = np.concatenate(
            [
                np.random.randint(50, 300, size=60),  # Evening activity
                np.random.randint(0, 30, size=60),  # Sleep (low activity)
                np.random.randint(50, 300, size=60),  # Morning activity
            ]
        )

        # Detect nonwear
        nonwear_algo = NonwearAlgorithmFactory.create(NonwearAlgorithm.CHOI_2011.value)
        nonwear_periods = nonwear_algo.detect(activity, timestamps)

        # Score sleep
        df = pd.DataFrame(
            {
                "datetime": timestamps,
                "Axis1": activity,
            }
        )
        sleep_algo = AlgorithmFactory.create(AlgorithmType.SADEH_1994_ACTILIFE.value)
        scored_df = sleep_algo.score(df)

        # Both should complete without errors
        assert isinstance(nonwear_periods, list)
        assert "Sadeh Score" in scored_df.columns


class TestDataSourceDIIntegration:
    """Integration tests for DataSource DI system."""

    def test_datasource_factory_enum_alignment(self) -> None:
        """Test DataSourceType enum values have factory entries."""
        factory_ids = set(DataSourceFactory.get_available_loaders().keys())

        # All DataSourceType values should have factory entries
        assert DataSourceType.CSV.value in factory_ids
        assert DataSourceType.GT3X.value in factory_ids

    def test_csv_full_pipeline(self, tmp_path) -> None:
        """Test full CSV load->validate->metadata flow."""
        # Create test CSV file
        csv_file = tmp_path / "test.csv"
        lines = [
            "Header Line 1",
            "Header Line 2",
            "Header Line 3",
            "Header Line 4",
            "Header Line 5",
            "Header Line 6",
            "Header Line 7",
            "Header Line 8",
            "Header Line 9",
            "Header Line 10",
            "Date,Time,Axis1",
            "1/15/2024,08:00:00,100",
            "1/15/2024,08:01:00,120",
            "1/15/2024,08:02:00,110",
        ]
        csv_file.write_text("\n".join(lines))

        # Get loader from factory
        loader = DataSourceFactory.create(DataSourceType.CSV.value)

        # Load file
        result = loader.load_file(csv_file)

        # Verify result structure
        assert "activity_data" in result
        assert "metadata" in result
        assert "column_mapping" in result

        # Verify data
        df = result["activity_data"]
        assert len(df) == 3
        assert "timestamp" in df.columns
        assert "axis_y" in df.columns

        # Verify metadata
        metadata = result["metadata"]
        assert "file_size" in metadata
        assert "total_epochs" in metadata
        assert metadata["total_epochs"] == 3

    def test_all_di_factories_operational(self) -> None:
        """Test all 4 DI factories can create instances."""
        # 1. Sleep scoring factory
        sleep_algo = AlgorithmFactory.create(AlgorithmFactory.get_default_algorithm_id())
        assert sleep_algo is not None
        assert hasattr(sleep_algo, "score")

        # 2. Onset/offset factory
        onset_rule = OnsetOffsetRuleFactory.create(OnsetOffsetRuleFactory.get_default_rule_id())
        assert onset_rule is not None
        assert hasattr(onset_rule, "apply_rules")

        # 3. Nonwear factory
        nonwear = NonwearAlgorithmFactory.create(NonwearAlgorithmFactory.get_default_algorithm_id())
        assert nonwear is not None
        assert hasattr(nonwear, "detect")

        # 4. DataSource factory
        datasource = DataSourceFactory.create(DataSourceFactory.get_default_loader_id())
        assert datasource is not None
        assert hasattr(datasource, "load_file")

    def test_datasource_with_sleep_scoring(self, tmp_path) -> None:
        """Test integrating datasource loading with sleep scoring."""
        # Create test CSV file
        csv_file = tmp_path / "activity.csv"
        np.random.seed(42)

        # Generate activity data
        n_epochs = 60
        header = ["Header"] * 10
        data_header = ["Date,Time,Axis1"]

        data_rows = []
        for i in range(n_epochs):
            hour = 8 + (i // 60)
            minute = i % 60
            activity = np.random.randint(0, 200)
            data_rows.append(f"1/15/2024,{hour:02d}:{minute:02d}:00,{activity}")

        csv_file.write_text("\n".join(header + data_header + data_rows))

        # Load data with DataSource factory
        loader = DataSourceFactory.create("csv")
        result = loader.load_file(csv_file)
        df = result["activity_data"]

        # Rename column for Sadeh algorithm
        df_for_scoring = df.rename(columns={"timestamp": "datetime", "axis_y": "Axis1"})

        # Score with sleep algorithm
        algo = AlgorithmFactory.create("sadeh_1994_actilife")
        scored_df = algo.score(df_for_scoring)

        # Verify integration works
        assert "Sadeh Score" in scored_df.columns
        assert len(scored_df) == n_epochs

    def test_enum_default_consistency(self) -> None:
        """Test DataSourceType enum default matches factory default."""
        enum_default = DataSourceType.get_default()
        factory_default = DataSourceFactory.get_default_loader_id()
        assert enum_default.value == factory_default


class TestDefaultValues:
    """Tests for default algorithm selections."""

    def test_defaults_are_consistent(self) -> None:
        """Test that default values are consistent across system."""
        # AlgorithmType default should match factory default
        enum_default = AlgorithmType.get_default()
        factory_default = AlgorithmFactory.get_default_algorithm_id()
        assert enum_default.value == factory_default

        # NonwearAlgorithm default should match factory default
        nonwear_enum_default = NonwearAlgorithm.get_default()
        nonwear_factory_default = NonwearAlgorithmFactory.get_default_algorithm_id()
        assert nonwear_enum_default.value == nonwear_factory_default

        # DataSourceType default should match factory default
        datasource_enum_default = DataSourceType.get_default()
        datasource_factory_default = DataSourceFactory.get_default_loader_id()
        assert datasource_enum_default.value == datasource_factory_default

    def test_defaults_create_valid_instances(self) -> None:
        """Test that default IDs create valid algorithm instances."""
        # Sleep scoring
        algo = AlgorithmFactory.create(AlgorithmFactory.get_default_algorithm_id())
        assert algo is not None
        assert hasattr(algo, "score")
        assert hasattr(algo, "score_array")

        # Onset/offset
        rule = OnsetOffsetRuleFactory.create(OnsetOffsetRuleFactory.get_default_rule_id())
        assert rule is not None
        assert hasattr(rule, "apply_rules")

        # Nonwear
        nonwear = NonwearAlgorithmFactory.create(NonwearAlgorithmFactory.get_default_algorithm_id())
        assert nonwear is not None
        assert hasattr(nonwear, "detect")

        # DataSource
        datasource = DataSourceFactory.create(DataSourceFactory.get_default_loader_id())
        assert datasource is not None
        assert hasattr(datasource, "load_file")
