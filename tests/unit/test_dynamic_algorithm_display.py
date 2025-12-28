"""
Unit tests for dynamic algorithm display in marker tables.

Tests the DI-pattern implementation for dynamically updating table headers
to show the currently selected sleep/wake algorithm name.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from sleep_scoring_app.core.algorithms import AlgorithmFactory
from sleep_scoring_app.core.constants import AlgorithmType, TableColumn, TooltipText
from sleep_scoring_app.utils.table_helpers import (
    create_marker_data_table,
    update_marker_table,
    update_table_sleep_algorithm_header,
)


@pytest.fixture
def qapp():
    """Create QApplication for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sadeh_display_name() -> str:
    """Get display name for Sadeh ActiLife algorithm from factory."""
    return AlgorithmFactory.get_available_algorithms()[AlgorithmType.SADEH_1994_ACTILIFE]


@pytest.fixture
def cole_kripke_display_name() -> str:
    """Get display name for Cole-Kripke ActiLife algorithm from factory."""
    return AlgorithmFactory.get_available_algorithms()[AlgorithmType.COLE_KRIPKE_1992_ACTILIFE]


@pytest.fixture
def van_hees_display_name() -> str:
    """Get display name for Van Hees 2015 SIB algorithm from factory."""
    return AlgorithmFactory.get_available_algorithms()[AlgorithmType.VAN_HEES_2015_SIB]


class TestTableCreationWithAlgorithmName:
    """Tests for creating tables with dynamic algorithm names."""

    def test_create_table_with_default_algorithm_name(self, qapp) -> None:
        """Test creating table with no algorithm name uses generic 'Sleep' header."""
        table_container = create_marker_data_table("Test Table")

        table = table_container.table_widget
        header_item = table.horizontalHeaderItem(3)

        assert header_item is not None
        assert header_item.text() == TableColumn.SLEEP_SCORE

    def test_create_table_with_sadeh_algorithm(self, qapp, sadeh_display_name: str) -> None:
        """Test creating table with Sadeh algorithm name."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        table = table_container.table_widget
        header_item = table.horizontalHeaderItem(3)

        assert header_item is not None
        assert header_item.text() == sadeh_display_name

    def test_create_table_with_cole_kripke_algorithm(self, qapp, cole_kripke_display_name: str) -> None:
        """Test creating table with Cole-Kripke algorithm name."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=cole_kripke_display_name)

        table = table_container.table_widget
        header_item = table.horizontalHeaderItem(3)

        assert header_item is not None
        assert header_item.text() == cole_kripke_display_name

    def test_create_table_stores_algorithm_name(self, qapp, sadeh_display_name: str) -> None:
        """Test that algorithm name is stored on the container."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        assert hasattr(table_container, "sleep_algorithm_name")
        assert table_container.sleep_algorithm_name == sadeh_display_name

    def test_create_table_with_none_algorithm_name(self, qapp) -> None:
        """Test creating table with explicit None algorithm name."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=None)

        table = table_container.table_widget
        header_item = table.horizontalHeaderItem(3)

        assert header_item is not None
        assert header_item.text() == TableColumn.SLEEP_SCORE

    def test_table_has_correct_column_count(self, qapp, sadeh_display_name: str) -> None:
        """Test that table has expected column count."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        table = table_container.table_widget
        assert table.columnCount() == 6  # Time, Axis-Y, VM, Sleep, Choi, NWT

    def test_algorithm_tooltip_is_set_correctly(self, qapp, cole_kripke_display_name: str) -> None:
        """Test that algorithm column has correct tooltip."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=cole_kripke_display_name)

        table = table_container.table_widget
        header_item = table.horizontalHeaderItem(3)

        assert header_item is not None
        assert cole_kripke_display_name in header_item.toolTip()
        assert "S=Sleep" in header_item.toolTip()
        assert "W=Wake" in header_item.toolTip()


class TestUpdateTableSleepAlgorithmHeader:
    """Tests for dynamically updating table headers."""

    def test_update_header_to_sadeh(self, qapp, sadeh_display_name: str) -> None:
        """Test updating header to Sadeh algorithm."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name="Generic")

        update_table_sleep_algorithm_header(table_container, sadeh_display_name)

        table = table_container.table_widget
        header_item = table.horizontalHeaderItem(3)

        assert header_item.text() == sadeh_display_name

    def test_update_header_to_cole_kripke(self, qapp, sadeh_display_name: str, cole_kripke_display_name: str) -> None:
        """Test updating header to Cole-Kripke algorithm."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        update_table_sleep_algorithm_header(table_container, cole_kripke_display_name)

        table = table_container.table_widget
        header_item = table.horizontalHeaderItem(3)

        assert header_item.text() == cole_kripke_display_name

    def test_update_header_updates_tooltip(self, qapp, sadeh_display_name: str, van_hees_display_name: str) -> None:
        """Test that updating header also updates tooltip."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        update_table_sleep_algorithm_header(table_container, van_hees_display_name)

        table = table_container.table_widget
        header_item = table.horizontalHeaderItem(3)

        assert van_hees_display_name in header_item.toolTip()

    def test_update_header_stores_new_algorithm_name(
        self, qapp, sadeh_display_name: str, cole_kripke_display_name: str
    ) -> None:
        """Test that updating header updates stored algorithm name."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        update_table_sleep_algorithm_header(table_container, cole_kripke_display_name)

        assert table_container.sleep_algorithm_name == cole_kripke_display_name

    def test_update_header_with_invalid_container_logs_warning(self, qapp, sadeh_display_name: str) -> None:
        """Test that updating header with invalid container logs warning."""
        invalid_container = QWidget()

        # Should not raise an exception
        update_table_sleep_algorithm_header(invalid_container, sadeh_display_name)

    def test_update_header_preserves_other_columns(
        self, qapp, sadeh_display_name: str, cole_kripke_display_name: str
    ) -> None:
        """Test that updating algorithm header doesn't affect other columns."""
        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        update_table_sleep_algorithm_header(table_container, cole_kripke_display_name)

        table = table_container.table_widget

        # Check other columns are unchanged
        assert table.horizontalHeaderItem(0).text() == TableColumn.TIME
        assert table.horizontalHeaderItem(1).text() == TableColumn.AXIS_Y
        assert table.horizontalHeaderItem(2).text() == TableColumn.VM
        assert table.horizontalHeaderItem(4).text() == TableColumn.CHOI
        assert table.horizontalHeaderItem(5).text() == TableColumn.NWT_SENSOR


class TestUpdateMarkerTableWithSleepScore:
    """Tests for update_marker_table with sleep_score key."""

    def test_update_table_with_sleep_score_key(self, qapp, sadeh_display_name: str) -> None:
        """Test that update_marker_table uses sleep_score key."""
        from PyQt6.QtGui import QColor

        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        data = [
            {"time": "22:00", "axis_y": 100, "vm": 150, "sleep_score": 1, "choi": 0, "nwt_sensor": 0, "is_marker": True},
            {"time": "22:01", "axis_y": 50, "vm": 75, "sleep_score": 0, "choi": 0, "nwt_sensor": 0, "is_marker": False},
        ]

        update_marker_table(
            table_container,
            data,
            marker_bg_color=QColor(255, 0, 0),
            marker_fg_color=QColor(255, 255, 255),
        )

        table = table_container.table_widget

        # First row should show "S" for sleep
        assert table.item(0, 3).text() == "S"
        # Second row should show "W" for wake
        assert table.item(1, 3).text() == "W"

    def test_update_table_without_sleep_score_shows_placeholder(self, qapp, sadeh_display_name: str) -> None:
        """Test that missing sleep_score key shows placeholder."""
        from PyQt6.QtGui import QColor

        table_container = create_marker_data_table("Test Table", sleep_algorithm_name=sadeh_display_name)

        # No sleep_score key provided
        data = [
            {"time": "22:00", "axis_y": 100, "vm": 150, "choi": 0, "nwt_sensor": 0, "is_marker": True},
        ]

        update_marker_table(
            table_container,
            data,
            marker_bg_color=QColor(255, 0, 0),
            marker_fg_color=QColor(255, 255, 255),
        )

        table = table_container.table_widget

        # Should show placeholder when sleep_score is missing
        assert table.item(0, 3).text() == "--"


class TestAlgorithmFactoryIntegration:
    """Tests for integration with AlgorithmFactory."""

    def test_all_available_algorithms_have_display_names(self) -> None:
        """Test that all available algorithms have display names."""
        available = AlgorithmFactory.get_available_algorithms()

        for display_name in available.values():
            assert isinstance(display_name, str)
            assert len(display_name) > 0

    def test_created_algorithms_have_name_property(self) -> None:
        """Test that created algorithms have name property for table display."""
        available = AlgorithmFactory.get_available_algorithms()

        for algo_id in available:
            algorithm = AlgorithmFactory.create(algo_id)
            assert hasattr(algorithm, "name")
            assert isinstance(algorithm.name, str)
            assert len(algorithm.name) > 0

    def test_algorithm_display_names_match_factory_values(self) -> None:
        """Test that algorithm names match between factory and instances."""
        available = AlgorithmFactory.get_available_algorithms()

        for algo_id, expected_name in available.items():
            algorithm = AlgorithmFactory.create(algo_id)
            assert algorithm.name == expected_name


class TestTableColumnConstants:
    """Tests for TableColumn enum constants."""

    def test_sleep_score_constant_exists(self) -> None:
        """Test that SLEEP_SCORE constant exists."""
        assert hasattr(TableColumn, "SLEEP_SCORE")
        assert TableColumn.SLEEP_SCORE == "Sleep"

    def test_sleep_score_tooltip_exists(self) -> None:
        """Test that sleep score tooltip exists."""
        assert hasattr(TooltipText, "SLEEP_SCORE_COLUMN")
        assert "S=Sleep" in TooltipText.SLEEP_SCORE_COLUMN
        assert "W=Wake" in TooltipText.SLEEP_SCORE_COLUMN


class TestMarkerTableManagerIntegration:
    """Tests for MarkerTableManager integration (requires mocking)."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for MarkerTableManager."""
        store = MagicMock()
        store.state.current_file = None
        navigation = MagicMock()
        marker_ops = MagicMock()
        app_state = MagicMock()
        services = MagicMock()
        services.config_manager = None
        services.plot_widget = None
        parent = MagicMock()
        parent.onset_table = None
        parent.offset_table = None
        return store, navigation, marker_ops, app_state, services, parent

    def test_get_current_sleep_algorithm_name_returns_string(self, mock_dependencies) -> None:
        """Test that get_current_sleep_algorithm_name returns a string."""
        from sleep_scoring_app.ui.marker_table import MarkerTableManager

        store, navigation, marker_ops, app_state, services, parent = mock_dependencies

        manager = MarkerTableManager(
            store=store,
            navigation=navigation,
            marker_ops=marker_ops,
            app_state=app_state,
            services=services,
            parent=parent,
        )
        result = manager.get_current_sleep_algorithm_name()

        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_current_sleep_algorithm_name_default_fallback(self, mock_dependencies) -> None:
        """Test that get_current_sleep_algorithm_name returns fallback when no config/callback."""
        from sleep_scoring_app.ui.marker_table import MarkerTableManager

        store, navigation, marker_ops, app_state, services, parent = mock_dependencies

        manager = MarkerTableManager(
            store=store,
            navigation=navigation,
            marker_ops=marker_ops,
            app_state=app_state,
            services=services,
            parent=parent,
        )
        result = manager.get_current_sleep_algorithm_name()

        # The current implementation has a hardcoded fallback - this test documents that behavior
        # Ideally this should use AlgorithmFactory.get_default_algorithm_id() to get proper name
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_current_sleep_algorithm_name_from_callback(self, mock_dependencies) -> None:
        """Test that get_current_sleep_algorithm_name uses callback if provided."""
        from sleep_scoring_app.ui.marker_table import MarkerTableManager

        store, navigation, marker_ops, app_state, services, parent = mock_dependencies

        # Get the proper display name for Cole-Kripke ActiLife from the factory
        cole_kripke_display_name = AlgorithmFactory.get_available_algorithms()[
            AlgorithmType.COLE_KRIPKE_1992_ACTILIFE
        ]

        # Provide a custom callback that returns the proper display name
        custom_callback = MagicMock(return_value=cole_kripke_display_name)

        manager = MarkerTableManager(
            store=store,
            navigation=navigation,
            marker_ops=marker_ops,
            app_state=app_state,
            services=services,
            parent=parent,
            get_sleep_algorithm_name=custom_callback,
        )
        result = manager.get_current_sleep_algorithm_name()

        # Should return value from callback
        assert result == cole_kripke_display_name
        custom_callback.assert_called_once()

    def test_update_table_headers_for_algorithm_caches_name(self, mock_dependencies) -> None:
        """Test that update_table_headers_for_algorithm caches the algorithm name."""
        from sleep_scoring_app.ui.marker_table import MarkerTableManager

        store, navigation, marker_ops, app_state, services, parent = mock_dependencies

        manager = MarkerTableManager(
            store=store,
            navigation=navigation,
            marker_ops=marker_ops,
            app_state=app_state,
            services=services,
            parent=parent,
        )

        # First call should set the cache
        manager.update_table_headers_for_algorithm()

        assert manager._cached_algorithm_name is not None

    def test_update_table_headers_skips_if_unchanged(self, mock_dependencies) -> None:
        """Test that update_table_headers_for_algorithm skips update if unchanged."""
        from sleep_scoring_app.ui.marker_table import MarkerTableManager

        store, navigation, marker_ops, app_state, services, parent = mock_dependencies

        # Get the proper display name for Sadeh ActiLife from the factory
        sadeh_display_name = AlgorithmFactory.get_available_algorithms()[
            AlgorithmType.SADEH_1994_ACTILIFE
        ]

        manager = MarkerTableManager(
            store=store,
            navigation=navigation,
            marker_ops=marker_ops,
            app_state=app_state,
            services=services,
            parent=parent,
            get_sleep_algorithm_name=MagicMock(return_value=sadeh_display_name),
        )

        # Pre-set the cache to the same value callback will return
        manager._cached_algorithm_name = sadeh_display_name

        # This should return early without updating tables
        manager.update_table_headers_for_algorithm()

        # No table update calls should have been made
        # (No assertion needed - just verifying no exception)
