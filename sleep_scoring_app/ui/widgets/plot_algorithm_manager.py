#!/usr/bin/env python3
"""
Plot Algorithm Manager - Handles sleep scoring algorithms and rule application.

Extracted from ActivityPlotWidget to reduce god class size.
Manages Sadeh algorithm execution, sleep onset/offset rule application,
and algorithm result caching.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pyqtgraph as pg

from sleep_scoring_app.core.algorithms import AlgorithmFactory, NonwearAlgorithmFactory, SleepScoringAlgorithm
from sleep_scoring_app.core.algorithms.onset_offset_factory import OnsetOffsetRuleFactory
from sleep_scoring_app.core.algorithms.onset_offset_protocol import OnsetOffsetRule
from sleep_scoring_app.core.constants import ActivityDataPreference, UIColors

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import SleepPeriod
    from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

logger = logging.getLogger(__name__)


class PlotAlgorithmManager:
    """Manages sleep scoring algorithms and rule application for ActivityPlotWidget."""

    def __init__(self, parent: ActivityPlotWidget) -> None:
        """
        Initialize the algorithm manager with parent reference.

        Args:
            parent: The ActivityPlotWidget that owns this manager

        """
        self.parent = parent
        self._algorithm_cache: dict[str, dict[str, Any]] = {}
        self._sleep_pattern_cache: dict[tuple, tuple] = {}
        self._sleep_scoring_algorithm: SleepScoringAlgorithm | None = None
        self._onset_offset_rule: OnsetOffsetRule | None = None

    # ========== Property Accessors ==========

    @property
    def timestamps(self):
        """Access parent's timestamps."""
        return self.parent.timestamps

    @property
    def x_data(self):
        """Access parent's x_data."""
        return self.parent.x_data

    @property
    def activity_data(self):
        """Access parent's activity_data."""
        return getattr(self.parent, "activity_data", None)

    @property
    def sadeh_results(self):
        """Access parent's sadeh_results."""
        return getattr(self.parent, "sadeh_results", None)

    def _get_choi_activity_column(self) -> str:
        """
        Get the Choi activity column from config.

        Returns:
            Activity column name: 'vector_magnitude' (default), 'axis_y', 'axis_x', or 'axis_z'

        """
        try:
            # Try direct main_window attribute first
            main_window = getattr(self.parent, "main_window", None)
            # If not found, try Qt parent() - plot_widget's parent IS main_window directly
            if main_window is None and hasattr(self.parent, "parent") and callable(self.parent.parent):
                main_window = self.parent.parent()  # Qt parent() method
            if main_window and hasattr(main_window, "config_manager"):
                choi_axis = main_window.config_manager.config.choi_axis
                if choi_axis:
                    return choi_axis  # Already stored as lowercase column name
        except Exception as e:
            logger.debug("Exception getting Choi activity column: %s", e)
        return ActivityDataPreference.VECTOR_MAGNITUDE  # Default

    def get_sleep_scoring_algorithm(self) -> SleepScoringAlgorithm:
        """
        Get the current sleep scoring algorithm instance.

        Creates the algorithm from the factory if not already cached.
        Uses configuration to determine which algorithm and parameters to use.

        Returns:
            SleepScoringAlgorithm instance (default: SadehAlgorithm)

        """
        if self._sleep_scoring_algorithm is None:
            # Get config from main window
            config = None
            main_window = getattr(self.parent, "main_window", None)
            if main_window is None and hasattr(self.parent, "parent") and callable(self.parent.parent):
                main_window = self.parent.parent()
            if main_window and hasattr(main_window, "config_manager"):
                config = main_window.config_manager.config

            # Get algorithm ID from config or use default
            algorithm_id = AlgorithmFactory.get_default_algorithm_id()
            if config and hasattr(config, "sleep_algorithm_id") and config.sleep_algorithm_id:
                algorithm_id = config.sleep_algorithm_id

            self._sleep_scoring_algorithm = AlgorithmFactory.create(algorithm_id, config)
            logger.debug("Created sleep scoring algorithm: %s (id: %s)", self._sleep_scoring_algorithm.name, algorithm_id)

        return self._sleep_scoring_algorithm

    def set_sleep_scoring_algorithm(self, algorithm: SleepScoringAlgorithm) -> None:
        """
        Set the sleep scoring algorithm instance.

        Clears caches when algorithm changes to ensure fresh results.

        Args:
            algorithm: SleepScoringAlgorithm instance to use

        """
        self._sleep_scoring_algorithm = algorithm
        # Clear caches when algorithm changes
        self._algorithm_cache.clear()
        self._sleep_pattern_cache.clear()
        logger.info("Sleep scoring algorithm changed to: %s", algorithm.name)

    def get_onset_offset_rule(self) -> OnsetOffsetRule:
        """
        Get the current onset/offset rule instance.

        Creates the rule from the factory if not already cached.
        Uses configuration to determine which rule and parameters to use.

        Returns:
            OnsetOffsetRule instance (default: Consecutive 3/5 Minutes)

        """
        if self._onset_offset_rule is None:
            # Get config from main window
            config = None
            main_window = getattr(self.parent, "main_window", None)
            if main_window is None and hasattr(self.parent, "parent") and callable(self.parent.parent):
                main_window = self.parent.parent()
            if main_window and hasattr(main_window, "config_manager"):
                config = main_window.config_manager.config

            # Get rule ID from config or use default
            rule_id = OnsetOffsetRuleFactory.get_default_rule_id()
            if config and hasattr(config, "onset_offset_rule_id") and config.onset_offset_rule_id:
                rule_id = config.onset_offset_rule_id

            self._onset_offset_rule = OnsetOffsetRuleFactory.create(rule_id, config)
            logger.debug("Created onset/offset rule: %s (id: %s)", self._onset_offset_rule.name, rule_id)

        return self._onset_offset_rule

    def set_onset_offset_rule(self, rule: OnsetOffsetRule) -> None:
        """
        Set the onset/offset rule instance.

        Clears caches when rule changes to ensure fresh results.

        Args:
            rule: OnsetOffsetRule instance to use

        """
        self._onset_offset_rule = rule
        # Clear caches when rule changes
        self._sleep_pattern_cache.clear()
        logger.info("Onset/offset rule changed to: %s", rule.name)

    @sadeh_results.setter
    def sadeh_results(self, value):
        """Set parent's sadeh_results."""
        self.parent.sadeh_results = value

    @property
    def main_48h_timestamps(self):
        """Access parent's main 48hr timestamps."""
        return self.parent.main_48h_timestamps

    @property
    def main_48h_activity(self):
        """Access parent's main 48hr activity data."""
        return self.parent.main_48h_activity

    @property
    def main_48h_sadeh_results(self):
        """Access parent's main 48hr Sadeh results."""
        return self.parent.main_48h_sadeh_results

    @main_48h_sadeh_results.setter
    def main_48h_sadeh_results(self, value):
        """Set parent's main 48hr Sadeh results."""
        self.parent.main_48h_sadeh_results = value

    @property
    def main_48h_axis_y_data(self):
        """Access parent's main 48hr axis_y data."""
        return self.parent.main_48h_axis_y_data

    @main_48h_axis_y_data.setter
    def main_48h_axis_y_data(self, value):
        """Set parent's main 48hr axis_y data."""
        self.parent.main_48h_axis_y_data = value

    @property
    def data_max_y(self):
        """Access parent's data_max_y."""
        return self.parent.data_max_y

    @property
    def plotItem(self):
        """Access parent's plotItem."""
        return self.parent.plotItem

    # ========== Algorithm Execution Methods ==========

    def plot_algorithms(self) -> None:
        """Run and plot algorithms with performance optimization and caching."""
        if not hasattr(self.parent, "activity_data") or not self.activity_data:
            logger.debug("No activity data available for algorithm plotting")
            return

        # Always use 48hr main data for algorithms if available
        if self.main_48h_timestamps is not None and self.main_48h_activity is not None:
            algorithm_timestamps = self.main_48h_timestamps
            algorithm_activity = self.main_48h_activity
            logger.debug("Using 48hr main data for algorithms: %d points", len(algorithm_timestamps))
        else:
            algorithm_timestamps = self.timestamps
            algorithm_activity = self.activity_data
            logger.debug("Using current view data for algorithms: %d points", len(algorithm_timestamps))

        # Create cache key based on main data hash for efficient caching
        column_type = getattr(self.parent, "activity_column_type", "unknown")
        data_type = "vm" if column_type == "VECTOR_MAGNITUDE" else "axis_y" if column_type else "unknown"
        data_hash = hashlib.md5(repr(algorithm_activity).encode()).hexdigest()[:16]

        # Include timestamp hash for proper cache invalidation
        timestamp_hash = ""
        sadeh_axis_y_hash = ""

        if hasattr(self.parent, "main_48h_axis_y_timestamps") and self.parent.main_48h_axis_y_timestamps:
            timestamp_str = repr([ts.isoformat() if hasattr(ts, "isoformat") else str(ts) for ts in self.parent.main_48h_axis_y_timestamps[:10]])
            sadeh_axis_y_hash = hashlib.md5(timestamp_str.encode()).hexdigest()[:8]

        if data_type == "axis_y":
            timestamp_hash = sadeh_axis_y_hash
        elif algorithm_timestamps:
            timestamp_str = repr([ts.isoformat() if hasattr(ts, "isoformat") else str(ts) for ts in algorithm_timestamps[:10]])
            timestamp_hash = hashlib.md5(timestamp_str.encode()).hexdigest()[:8]

        # Include algorithm parameters in cache key so changing settings invalidates cache
        algorithm = self.get_sleep_scoring_algorithm()
        algorithm_id = algorithm.identifier
        choi_activity_col = self._get_choi_activity_column()
        cache_key = f"48h_{column_type}_{data_type}_{len(algorithm_activity)}_{data_hash}_{timestamp_hash}_sadeh_{sadeh_axis_y_hash}_algo{algorithm_id}_choi{choi_activity_col}"

        # Check if results are already cached
        if cache_key in self._algorithm_cache:
            cached_results = self._algorithm_cache[cache_key]
            self.main_48h_sadeh_results = cached_results["sadeh"]
            logger.debug("Using cached 48hr algorithm results for %s", cache_key)
            self._extract_view_subset_from_main_results()
            return

        logger.debug("Running algorithms on 48hr main data")

        # Get axis_y data specifically for Sadeh algorithm
        if self.main_48h_axis_y_data is not None:
            axis_y_data = self.main_48h_axis_y_data
            logger.debug("AXIS_Y CACHE HIT: Using cached axis_y data with %d points for Sadeh", len(axis_y_data))
        else:
            axis_y_data = self.parent._get_axis_y_data_for_sadeh()
            self.main_48h_axis_y_data = axis_y_data
            logger.debug("AXIS_Y CACHE MISS: Loaded fresh axis_y data with %d points for Sadeh", len(axis_y_data) if axis_y_data else 0)

        # Run Choi algorithm (nonwear detection) with configured activity column using DI pattern
        choi_activity_column = self._get_choi_activity_column()
        logger.debug("Running Choi algorithm with activity_column: %s", choi_activity_column)
        choi_algorithm = NonwearAlgorithmFactory.create("choi_2011")
        choi_periods = choi_algorithm.detect(
            activity_data=algorithm_activity,
            timestamps=self.parent.timestamps if hasattr(self.parent, "timestamps") else [],
            activity_column=choi_activity_column,
        )
        logger.debug("Choi algorithm returned %d periods", len(choi_periods))
        logger.debug("Choi algorithm completed - plotting handled by NonwearData system")

        # Validate Sadeh input data
        if axis_y_data:
            logger.debug("Sadeh algorithm using axis_y_data with %d points", len(axis_y_data))
        else:
            logger.error("Sadeh algorithm cannot run: axis_y_data is None or empty")

        # Run Sadeh algorithm with axis_y timestamps
        if hasattr(self.parent, "main_48h_axis_y_timestamps") and self.parent.main_48h_axis_y_timestamps:
            if len(self.parent.main_48h_axis_y_timestamps) == len(axis_y_data):
                sadeh_timestamps = self.parent.main_48h_axis_y_timestamps
                logger.debug("Using axis_y-specific timestamps (%d points)", len(sadeh_timestamps))
            else:
                logger.error(
                    "Timestamp count mismatch: axis_y_timestamps=%d, axis_y_data=%d - cannot run Sadeh",
                    len(self.parent.main_48h_axis_y_timestamps),
                    len(axis_y_data),
                )
                self.main_48h_sadeh_results = []
                self._extract_view_subset_from_main_results()
                return
        else:
            logger.error("No axis_y timestamps available - cannot run Sadeh algorithm")
            self.main_48h_sadeh_results = []
            self._extract_view_subset_from_main_results()
            return

        # Use DI pattern to get sleep scoring algorithm
        algorithm = self.get_sleep_scoring_algorithm()
        logger.debug("Running sleep scoring algorithm: %s", algorithm.name)
        self.main_48h_sadeh_results = algorithm.score_array(axis_y_data, sadeh_timestamps)
        logger.debug("Sleep scoring algorithm returned %d results", len(self.main_48h_sadeh_results) if self.main_48h_sadeh_results else 0)

        self._extract_view_subset_from_main_results()

        # Cache results (limit to 5)
        if len(self._algorithm_cache) >= 5:
            oldest_key = next(iter(self._algorithm_cache))
            del self._algorithm_cache[oldest_key]

        self._algorithm_cache[cache_key] = {"sadeh": self.main_48h_sadeh_results}

    def _extract_view_subset_from_main_results(self) -> None:
        """Extract the current view subset from main 48hr algorithm results."""
        from datetime import timedelta

        # CRITICAL: Sadeh MUST use axis_y timestamps since it processes axis_y data
        if (
            self.main_48h_sadeh_results is None
            or not hasattr(self.parent, "main_48h_axis_y_timestamps")
            or self.parent.main_48h_axis_y_timestamps is None
        ):
            logger.debug("No main 48hr Sadeh results or axis_y timestamps to extract subset from (expected during initial load)")
            self.sadeh_results = []
            return

        # If we're in 48hr view, use full results
        if self.parent.current_view_hours == 48:
            self.sadeh_results = self.main_48h_sadeh_results
            logger.debug("Using full 48hr Sadeh results: %d points", len(self.sadeh_results))
            return

        # For 24hr view, extract noon-to-noon subset
        if not self.timestamps:
            logger.warning("No current timestamps to match against")
            self.sadeh_results = []
            return

        # CRITICAL FIX: Use axis_y timestamps for Sadeh alignment since Sadeh processes axis_y data
        main_axis_y_timestamps = self.parent.main_48h_axis_y_timestamps

        # Use fuzzy timestamp matching with tolerance for microsecond differences
        tolerance = timedelta(seconds=30)  # 30 second tolerance for timestamp matching

        def find_closest_timestamp_index(target_ts, timestamp_list, tolerance_delta):
            """Find the closest timestamp within tolerance."""
            for i, ts in enumerate(timestamp_list):
                if abs((target_ts - ts).total_seconds()) <= tolerance_delta.total_seconds():
                    return i
            return None

        # Map each current timestamp to its corresponding Sadeh result
        subset_results = []
        for ts in self.timestamps:
            # First try exact match for performance
            try:
                idx = main_axis_y_timestamps.index(ts)
            except ValueError:
                # Fall back to fuzzy matching with tolerance
                idx = find_closest_timestamp_index(ts, main_axis_y_timestamps, tolerance)

            if idx is not None:
                # Comprehensive bounds checking
                if 0 <= idx < len(self.main_48h_sadeh_results) and idx < len(main_axis_y_timestamps):
                    subset_results.append(self.main_48h_sadeh_results[idx])
                else:
                    logger.warning(
                        f"Index {idx} out of bounds for Sadeh results at timestamp {ts} (results length: {len(self.main_48h_sadeh_results)})"
                    )
                    subset_results.append(0)  # Default to Wake if out of bounds
            else:
                # Timestamp not found in main axis_y data even with tolerance
                logger.warning(f"Timestamp {ts} not found in main axis_y timestamps (even with {tolerance} tolerance)")
                subset_results.append(0)  # Default to Wake if timestamp not found

        self.sadeh_results = subset_results

        # Verify alignment
        if len(self.sadeh_results) != len(self.timestamps):
            logger.error("Sadeh subset length mismatch after extraction: timestamps=%d, results=%d", len(self.timestamps), len(self.sadeh_results))
        else:
            logger.debug("Extracted 24hr subset from main: %d points from %d total", len(self.sadeh_results), len(self.main_48h_sadeh_results))

    def plot_choi_results(self, nonwear_periods) -> None:
        """Plot Choi nonwear periods as purple background regions (optimized)."""
        if not nonwear_periods:
            return

        choi_brush = tuple(map(int, UIColors.CHOI_ALGORITHM_BRUSH.split(",")))
        choi_border = tuple(map(int, UIColors.CHOI_ALGORITHM_BORDER.split(",")))

        for period in nonwear_periods:
            start_time = self.timestamps[period["start_index"]].timestamp()
            end_time = self.timestamps[period["end_index"]].timestamp()

            region = pg.LinearRegionItem(
                [start_time, end_time],
                brush=pg.mkBrush(*choi_brush),
                pen=pg.mkPen(*choi_border, width=1),
                movable=False,
            )
            region.setZValue(-10)
            self.plotItem.addItem(region)

    # ========== Sleep Scoring Rule Methods ==========

    def apply_sleep_scoring_rules(self, main_sleep_period: SleepPeriod) -> None:
        """Apply onset/offset detection rules to selected marker set using injected rule."""
        selected_period = self.parent.get_selected_marker_period()
        if not selected_period or not selected_period.is_complete or not hasattr(self.parent, "sadeh_results"):
            return

        if not self.sadeh_results or len(self.sadeh_results) == 0:
            return

        self.clear_sleep_onset_offset_markers()

        # Get onset/offset rule instance
        rule = self.get_onset_offset_rule()

        # Convert period timestamps to datetime objects
        sleep_start_time = datetime.fromtimestamp(selected_period.onset_timestamp)
        sleep_end_time = datetime.fromtimestamp(selected_period.offset_timestamp)

        # Convert x_data (Unix timestamps) to datetime objects
        timestamps = [datetime.fromtimestamp(ts) for ts in self.x_data]

        # Apply rule via protocol
        onset_idx, offset_idx = rule.apply_rules(
            sleep_scores=self.sadeh_results,
            sleep_start_marker=sleep_start_time,
            sleep_end_marker=sleep_end_time,
            timestamps=timestamps,
        )

        # Create visual markers
        if onset_idx is not None:
            self.create_sleep_onset_marker(self.x_data[onset_idx], rule)

        if offset_idx is not None:
            self.create_sleep_offset_marker(self.x_data[offset_idx], rule)

    def create_sleep_onset_marker(self, timestamp, rule: OnsetOffsetRule | None = None) -> None:
        """Create sleep onset marker with arrow and axis label."""
        custom_arrow_colors = getattr(self.parent, "custom_arrow_colors", {})
        onset_arrow_color = custom_arrow_colors.get("onset", "#0066CC")

        arrow = pg.ArrowItem(
            pos=(timestamp, self.data_max_y * 0.88),
            angle=-90,
            headLen=15,
            headWidth=12,
            tailLen=25,
            tailWidth=3,
            pen=pg.mkPen(color=onset_arrow_color, width=2),
            brush=pg.mkBrush(color=onset_arrow_color),
        )
        arrow.setZValue(10)
        arrow.setVisible(True)
        self.plotItem.addItem(arrow)

        time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M")

        # Get label from rule protocol if available
        if rule is not None:
            onset_label, _ = rule.get_marker_labels(time_str, "")
        else:
            onset_label = f"Sleep Onset at {time_str}\n3-minute rule applied"

        onset_text = pg.TextItem(
            text=onset_label,
            color=onset_arrow_color,
            anchor=(0.5, 1.0),
        )
        onset_text.setFont(pg.QtGui.QFont("Arial", 10, pg.QtGui.QFont.Weight.Bold))
        onset_text.setPos(timestamp, self.data_max_y * 0.85)
        onset_text.setZValue(10)
        onset_text.setVisible(True)
        self.plotItem.addItem(onset_text)

        if not hasattr(self.parent, "sleep_rule_markers"):
            self.parent.sleep_rule_markers = []
        self.parent.sleep_rule_markers.extend([arrow, onset_text])

    def create_sleep_offset_marker(self, timestamp, rule: OnsetOffsetRule | None = None) -> None:
        """Create sleep offset marker with arrow and axis label."""
        custom_arrow_colors = getattr(self.parent, "custom_arrow_colors", {})
        offset_arrow_color = custom_arrow_colors.get("offset", "#FFA500")

        arrow = pg.ArrowItem(
            pos=(timestamp, self.data_max_y * 0.88),
            angle=-90,
            headLen=15,
            headWidth=12,
            tailLen=25,
            tailWidth=3,
            pen=pg.mkPen(color=offset_arrow_color, width=2),
            brush=pg.mkBrush(color=offset_arrow_color),
        )
        arrow.setZValue(10)
        arrow.setVisible(True)
        self.plotItem.addItem(arrow)

        time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M")

        # Get label from rule protocol if available
        if rule is not None:
            _, offset_label = rule.get_marker_labels("", time_str)
        else:
            offset_label = f"Sleep Offset at {time_str}\n5-minute rule applied"

        offset_text = pg.TextItem(
            text=offset_label,
            color=offset_arrow_color,
            anchor=(0.5, 1.0),
        )
        offset_text.setFont(pg.QtGui.QFont("Arial", 10, pg.QtGui.QFont.Weight.Bold))
        offset_text.setPos(timestamp, self.data_max_y * 0.85)
        offset_text.setZValue(10)
        offset_text.setVisible(True)
        self.plotItem.addItem(offset_text)

        if not hasattr(self.parent, "sleep_rule_markers"):
            self.parent.sleep_rule_markers = []
        self.parent.sleep_rule_markers.extend([arrow, offset_text])

    def clear_sleep_onset_offset_markers(self) -> None:
        """Clear sleep onset/offset markers from 3/5 rule."""
        if hasattr(self.parent, "sleep_rule_markers"):
            for marker in self.parent.sleep_rule_markers:
                self.plotItem.removeItem(marker)
            self.parent.sleep_rule_markers.clear()

    # ========== Cache Management ==========

    def clear_algorithm_cache(self) -> None:
        """Clear the algorithm results cache."""
        self._algorithm_cache.clear()
        self._sleep_pattern_cache.clear()

    def get_algorithm_cache_info(self) -> dict[str, int]:
        """Get information about the current algorithm cache state."""
        return {
            "algorithm_cache_size": len(self._algorithm_cache),
            "sleep_pattern_cache_size": len(self._sleep_pattern_cache),
        }
