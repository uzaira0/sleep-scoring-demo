#!/usr/bin/env python3
"""
Activity Plot Widget - Core plotting functionality extracted from RestrictedActivityPlot
Focuses on display and user interaction, with algorithms handled separately.
"""

import logging
import traceback
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from sleep_scoring_app.core.algorithms import SleepScoringAlgorithms
from sleep_scoring_app.core.constants import MarkerLimits, NonwearDataSource, UIColors
from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod
from sleep_scoring_app.ui.widgets.plot_algorithm_manager import PlotAlgorithmManager
from sleep_scoring_app.ui.widgets.plot_marker_renderer import PlotMarkerRenderer
from sleep_scoring_app.ui.widgets.plot_overlay_renderer import PlotOverlayRenderer
from sleep_scoring_app.ui.widgets.plot_state_serializer import PlotStateSerializer

# Configure logging
logger = logging.getLogger(__name__)
from sleep_scoring_app.services.nonwear_service import NonwearPeriod


class TimeAxisItem(pg.AxisItem):
    """Custom axis for displaying time labels."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing) -> list[str]:  # Qt naming convention
        """Convert timestamps to readable time strings."""
        strings = []
        for v in values:
            try:
                dt = datetime.fromtimestamp(v)
                strings.append(dt.strftime("%H"))
            except (ValueError, OSError):
                strings.append("")
        return strings


class ActivityPlotWidget(pg.PlotWidget):
    """Activity plot widget with restricted pan/zoom and sleep markers."""

    sleep_markers_changed = pyqtSignal(DailySleepMarkers)  # Signal for daily sleep markers updates
    marker_limit_exceeded = pyqtSignal(str)  # Signal when marker limit exceeded

    def __init__(self, parent=None) -> None:
        # Create with custom time axis
        time_axis = TimeAxisItem(orientation="bottom")
        super().__init__(axisItems={"bottom": time_axis})
        self.parent_window = parent  # Store reference to parent window

        # Data boundaries
        self.data_start_time = None
        self.data_end_time = None
        self.data_min_y = 0
        self.data_max_y = 100
        self.max_vm_value = None  # Store the max vector magnitude value for consistent y-axis
        self.current_view_hours = 24

        # Sleep markers (new extended system)
        self.daily_sleep_markers = DailySleepMarkers()
        self.marker_lines = []  # Visual line objects
        self.markers_saved = False  # Track if markers have been saved permanently
        self.current_marker_being_placed = None  # Track incomplete marker pairs
        self.selected_marker_set_index = 1  # Currently selected marker set (1, 2, 3, or 4)
        self._marker_click_in_progress = False  # Prevent double processing of marker clicks

        # File info display
        self.file_info_label = None
        self.current_filename = None

        # Store main 48hr data and algorithm results
        self.main_48h_timestamps = None
        self.main_48h_activity = None
        self.main_48h_sadeh_results = None
        self.main_48h_axis_y_data = None

        # Setup plot appearance
        self._setup_plot_appearance()

        # Connect event handlers
        self._setup_event_handlers()

        # Initialize marker renderer (manages all marker operations)
        self.marker_renderer = PlotMarkerRenderer(self)

        # Initialize overlay renderer (manages nonwear/Choi overlays)
        self.overlay_renderer = PlotOverlayRenderer(self)

        # Initialize algorithm manager (manages Sadeh/Choi algorithms and sleep rules)
        self.algorithm_manager = PlotAlgorithmManager(self)

        # Initialize state serializer (manages state capture/restore)
        self.state_serializer = PlotStateSerializer(self)

    def _setup_plot_appearance(self) -> None:
        """Configure plot appearance and styling with performance optimizations."""
        # Remove axis labels
        self.setLabel("bottom", "")  # Remove X-axis label
        self.getAxis("left").setLabel("")  # Remove Y-axis label but keep ticks
        self.showGrid(x=True, y=True, alpha=0.2)

        # Configure tick spacing for more uniform appearance
        self.getAxis("bottom").setTickSpacing(major=3600, minor=900)  # Major ticks every hour, minor every 15 min
        self.getAxis("left").enableAutoSIPrefix(False)  # Disable scientific notation
        self.getAxis("left").setTickSpacing(major=None, minor=None)  # Auto spacing for Y-axis

        # Improve plot styling
        self.getAxis("left").setPen(pg.mkPen(color="#333333", width=1))
        self.getAxis("bottom").setPen(pg.mkPen(color="#333333", width=1))
        self.getAxis("left").setTextPen(pg.mkPen(color="#444444"))
        self.getAxis("bottom").setTextPen(pg.mkPen(color="#444444"))

        # Set to panning mode instead of rectangle selection
        self.plotItem.getViewBox().setMouseMode(pg.ViewBox.PanMode)

        # Disable context menu to prevent unwanted interactions
        self.plotItem.setMenuEnabled(False)
        self.plotItem.getViewBox().setMenuEnabled(False)

        # Performance optimizations for pyqtgraph
        # Enable OpenGL for better rendering performance if available
        try:
            if hasattr(self.plotItem, "setUseOpenGL"):
                self.plotItem.setUseOpenGL(True)
        except AttributeError:
            # OpenGL not available, continue with software rendering
            pass

        # Optimize rendering settings (check availability first)
        try:
            if hasattr(self.plotItem, "setDownsampling"):
                self.plotItem.setDownsampling(mode="peak")  # Use peak downsampling for better performance
            if hasattr(self.plotItem, "setClipToView"):
                self.plotItem.setClipToView(True)  # Only render visible data
            if hasattr(self.plotItem, "setAutoDownsample"):
                self.plotItem.setAutoDownsample(True)  # Enable automatic downsampling
        except AttributeError:
            # These optimization methods not available in this pyqtgraph version
            pass

        # Reduce anti-aliasing for better performance (can be re-enabled if needed)
        try:
            if hasattr(self.plotItem, "setAntialiasing"):
                self.plotItem.setAntialiasing(False)
        except AttributeError:
            pass

        # Add focus indicator for accessibility
        self.setStyleSheet("""
            ActivityPlotWidget:focus {
                border: 3px solid #0080FF;
                background-color: #fafbff;
            }
        """)

    def _setup_event_handlers(self) -> None:
        """Setup event handlers for mouse and keyboard interaction."""
        # Get ViewBox for range control
        self.vb = self.plotItem.getViewBox()
        self.vb.sigRangeChanged.connect(self.enforce_range_limits)

        # Connect mouse clicks
        self.plotItem.scene().sigMouseClicked.connect(self.on_plot_clicked)

        # Connect mouse hover for tooltips with throttling
        self._mouse_move_timer = QTimer()
        self._mouse_move_timer.setSingleShot(True)
        self._mouse_move_timer.timeout.connect(self._process_mouse_move)
        self._last_mouse_pos = None

        self.plotItem.scene().sigMouseMoved.connect(self._on_mouse_move_throttled)
        self.setMouseTracking(True)

        # Enable keyboard focus for key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def cleanup_widget(self) -> None:
        """Clean up widget resources to prevent memory leaks."""
        try:
            # Stop and cleanup mouse move timer
            if hasattr(self, "_mouse_move_timer") and self._mouse_move_timer:
                self._mouse_move_timer.stop()
                self._mouse_move_timer.timeout.disconnect()
                self._mouse_move_timer.deleteLater()
                self._mouse_move_timer = None

            # Disconnect signals to prevent reference cycles
            try:
                if hasattr(self, "vb") and self.vb:
                    self.vb.sigRangeChanged.disconnect()
            except (TypeError, RuntimeError):
                # Signal already disconnected or object deleted
                pass

            try:
                if hasattr(self, "plotItem") and self.plotItem:
                    scene = self.plotItem.scene()
                    if scene:
                        scene.sigMouseClicked.disconnect()
                        scene.sigMouseMoved.disconnect()
            except (TypeError, RuntimeError):
                # Signal already disconnected or object deleted
                pass

            # Clear data references
            self.timestamps = None
            self.main_48h_timestamps = None
            self.main_48h_activity = None
            self.main_48h_sadeh_results = None
            self.main_48h_axis_y_data = None
            self._last_mouse_pos = None

            # Clear marker lines and sleep rule markers
            if hasattr(self, "marker_lines"):
                for line in self.marker_lines:
                    try:
                        if hasattr(line, "deleteLater"):
                            line.deleteLater()
                    except (RuntimeError, AttributeError):
                        pass
                self.marker_lines.clear()

            if hasattr(self, "sleep_rule_markers"):
                for marker in self.sleep_rule_markers:
                    try:
                        if hasattr(marker, "deleteLater"):
                            marker.deleteLater()
                    except (RuntimeError, AttributeError):
                        pass
                self.sleep_rule_markers.clear()

            logger.debug("ActivityPlotWidget cleanup completed")

        except Exception as e:
            logger.warning(f"Error during ActivityPlotWidget cleanup: {e}")

    def set_data_and_restrictions(
        self, timestamps, activity_data, view_hours=24, skip_nonwear_plotting=False, filename=None, activity_column_type=None, current_date=None
    ) -> None:
        """Set data and establish pan/zoom restrictions."""
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            "PLOT WIDGET: set_data_and_restrictions called with %s timestamps, %s activity_data, view_hours=%s, filename=%s",
            len(timestamps) if timestamps else 0,
            len(activity_data) if activity_data else 0,
            view_hours,
            filename,
        )

        # Also print to make sure we see it

        self.current_view_hours = view_hours
        self.current_filename = filename

        # Cached results are managed by NonwearData system

        # Convert timestamps to numeric values (optimized for performance)
        self.timestamps = timestamps
        # Use vectorized conversion for better performance with large datasets
        if timestamps:
            # Convert timestamps to numeric values directly (avoid numpy datetime corruption)
            self.x_data = np.array([ts.timestamp() for ts in timestamps])
        else:
            self.x_data = np.array([])

        logger.info("PLOT WIDGET: Converted %s timestamps to x_data array", len(self.x_data))

        # Calculate expected time boundaries based on view mode (not actual data bounds)
        # This ensures consistent display regardless of data availability

        # Use the provided current_date for plot bounds
        if current_date is not None:
            target_date = current_date
        elif len(self.x_data) > 0:
            # Fallback to first timestamp if no current_date provided
            target_date = datetime.fromtimestamp(self.x_data[0])
        else:
            # If no data and no current_date, use current date
            target_date = datetime.now()

        # Convert date to datetime if needed
        if isinstance(target_date, date) and not isinstance(target_date, datetime):
            target_datetime = datetime.combine(target_date, datetime.min.time())
        else:
            target_datetime = target_date

        if view_hours == 24:
            # 24h: noon to noon next day
            expected_start = target_datetime.replace(hour=12, minute=0, second=0, microsecond=0)
            expected_end = expected_start + timedelta(days=1)
        else:
            # 48h: midnight to midnight + 48h
            expected_start = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            expected_end = expected_start + timedelta(hours=48)

        # Set data boundaries to expected full range (not actual data range)
        self.data_start_time = expected_start.timestamp()
        self.data_end_time = expected_end.timestamp()

        # Set Y-axis boundaries based on actual data
        self.data_min_y = 0  # Always start at zero

        # Always calculate max based on the actual data
        current_max = max(activity_data) if activity_data else 200

        # Store max VM value if this is vector magnitude data
        if activity_column_type == "VECTOR_MAGNITUDE":
            self.max_vm_value = current_max
            # Use VM max for y-axis
            self.data_max_y = self.max_vm_value * 1.5
        # For axis_y, still use VM max if available, otherwise use current
        elif self.max_vm_value is not None:
            self.data_max_y = self.max_vm_value * 1.5
        else:
            # No VM data yet, temporarily use axis_y max
            self.data_max_y = current_max * 1.5

        # Clear existing plot
        self.clear()
        self.clear_sleep_markers()

        # Store raw data for potential future use (may be axis_y or vector_magnitude)
        self.activity_data = activity_data

        # If this is 48hr data, store it as main data for algorithm calculations
        if view_hours == 48:
            self.main_48h_timestamps = timestamps
            self.main_48h_activity = activity_data
            self.main_48h_axis_y_data = None  # Will be set when needed
            logger.debug("Stored 48hr main data: %d timestamps", len(timestamps) if timestamps else 0)

        # Store column type for later reference
        self.activity_column_type = activity_column_type

        # axis_y_data will be loaded on demand via property using unified loader
        logger.debug("PLOT WIDGET: Activity column type: %s", activity_column_type)

        # Data loaded successfully
        logger.info("PLOT WIDGET: About to plot data - x_data: %s points, activity_data: %s points", len(self.x_data), len(activity_data))

        # Plot activity data with improved styling and store reference for seamless updates
        self.activity_plot_item = self.plot(
            self.x_data,
            activity_data,
            pen=pg.mkPen(color="#2E86AB", width=2),
            name="Activity Data",
        )

        logger.info("PLOT WIDGET: Plot data added successfully, plot_item: %s", self.activity_plot_item)

        # Run and plot algorithms (optimized)
        # Note: This will only plot Choi if no nonwear sensor data is available
        if not skip_nonwear_plotting:
            self.plot_algorithms()

        # Set view to actual data range (show where data actually exists)
        if len(self.x_data) > 0:
            actual_start = float(self.x_data[0])
            actual_end = float(self.x_data[-1])
            padding = (actual_end - actual_start) * 0.02  # 2% padding
            start_time = actual_start - padding
            end_time = actual_end + padding
        else:
            # Fallback to expected range if no data
            start_time = self.data_start_time
            end_time = self.data_end_time

        # Configure Y-axis range and ticks to match data
        self.getAxis("left").setRange(self.data_min_y, self.data_max_y)

        # Set view range with Y constrained to data range
        logger.info("PLOT WIDGET: Setting view range - x: [%s, %s], y: [%s, %s]", start_time, end_time, self.data_min_y, self.data_max_y)

        self.vb.setRange(
            xRange=[start_time, end_time],
            yRange=[self.data_min_y, self.data_max_y],
            padding=0,
        )

        logger.info("PLOT WIDGET: Plot setup completed successfully")

        # Update file info label
        self._update_file_info_label()

    def update_view_range_only(self, view_hours: int, current_date=None) -> None:
        """Update ONLY the visual range of the plot, not the underlying data."""
        self.current_view_hours = view_hours

        # Use the provided current_date for plot bounds
        if current_date is not None:
            target_date = current_date
        elif hasattr(self, "x_data") and len(self.x_data) > 0:
            # Fallback to first timestamp if no current_date provided
            target_date = datetime.fromtimestamp(self.x_data[0])
        else:
            # If no data and no current_date, use current date
            target_date = datetime.now()

        # Convert date to datetime if needed
        if isinstance(target_date, date) and not isinstance(target_date, datetime):
            target_datetime = datetime.combine(target_date, datetime.min.time())
        else:
            target_datetime = target_date

        if view_hours == 24:
            # 24h: noon to noon next day
            expected_start = target_datetime.replace(hour=12, minute=0, second=0, microsecond=0)
            expected_end = expected_start + timedelta(days=1)
        else:
            # 48h: midnight to midnight + 48h
            expected_start = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            expected_end = expected_start + timedelta(hours=48)

        # Just update the view range, not the data
        start_time = expected_start.timestamp()
        end_time = expected_end.timestamp()

        # Set Y-axis boundaries based on actual data within view range
        if hasattr(self, "activity_data") and self.activity_data and hasattr(self, "timestamps"):
            # Find data within the view range
            visible_data = []
            for i, ts in enumerate(self.timestamps):
                ts_value = ts.timestamp()
                if start_time <= ts_value <= end_time and i < len(self.activity_data):
                    visible_data.append(self.activity_data[i])

            if visible_data:
                self.data_min_y = 0
                self.data_max_y = max(visible_data) * 1.5
            else:
                self.data_min_y = 0
                self.data_max_y = 200
        else:
            self.data_min_y = 0
            self.data_max_y = 200

        # Update the view box range
        self.vb.setRange(
            xRange=[start_time, end_time],
            yRange=[self.data_min_y, self.data_max_y],
            padding=0,
        )

        # Redraw sleep markers in the new range
        self.redraw_markers()

        # Update file info label
        self._update_file_info_label()

    def update_data_and_view_only(self, timestamps, activity_data, view_hours=24, current_date=None) -> None:
        """Update data and view without clearing sleep markers - for view mode switching."""
        self.current_view_hours = view_hours

        # Keep the same data - we're always using 48hr data now
        # Only update if not already set
        if not hasattr(self, "timestamps") or len(timestamps) != len(self.timestamps):
            # Convert timestamps to numeric values (optimized for performance)
            self.timestamps = timestamps
            # Use vectorized conversion for better performance with large datasets
            if timestamps:
                # Convert timestamps to numeric values directly (avoid numpy datetime corruption)
                self.x_data = np.array([ts.timestamp() for ts in timestamps])
            else:
                self.x_data = np.array([])

        # Calculate expected time boundaries based on view mode (not actual data bounds)
        # This ensures consistent display regardless of data availability

        # Use the provided current_date for plot bounds
        if current_date is not None:
            target_date = current_date
        elif len(self.x_data) > 0:
            # Fallback to first timestamp if no current_date provided
            target_date = datetime.fromtimestamp(self.x_data[0])
        else:
            # If no data and no current_date, use current date
            target_date = datetime.now()

        # Convert date to datetime if needed
        if isinstance(target_date, date) and not isinstance(target_date, datetime):
            target_datetime = datetime.combine(target_date, datetime.min.time())
        else:
            target_datetime = target_date

        if view_hours == 24:
            # 24h: noon to noon next day
            expected_start = target_datetime.replace(hour=12, minute=0, second=0, microsecond=0)
            expected_end = expected_start + timedelta(days=1)
        else:
            # 48h: midnight to midnight + 48h
            expected_start = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            expected_end = expected_start + timedelta(hours=48)

        # Set data boundaries to expected full range
        self.data_start_time = expected_start.timestamp()
        self.data_end_time = expected_end.timestamp()

        # Set Y-axis boundaries based on actual data
        self.data_min_y = 0  # Always start at zero

        # In update_data_and_view_only, we DON'T update max_vm_value
        # because we don't know what type of data is being passed in
        # Just keep using whatever data_max_y was already set
        # (This preserves the Y-axis range when switching between VM and axis_y)

        # Always update the data (could be switching between VM and axis_y)
        self.activity_data = activity_data

        # Only update main_48h data if we're in 48h view mode
        # In 24h mode, keep the existing main_48h data
        if view_hours == 48:
            self.main_48h_timestamps = timestamps
            self.main_48h_activity = activity_data
        # Don't clear axis_y cache - it's independent of what we're displaying
        logger.debug("Stored 48hr reference data: %d timestamps", len(timestamps) if timestamps else 0)

        # Check if we have an existing plot item to update
        if hasattr(self, "activity_plot_item") and self.activity_plot_item is not None:
            # Update existing plot item with new data
            self.activity_plot_item.setData(self.x_data, activity_data)
            logger.debug("Updated existing plot item with new activity data")
        else:
            # Create new plot item if none exists
            self.clear()
            self.activity_plot_item = self.plot(
                self.x_data,
                activity_data,
                pen=pg.mkPen(color="#2E86AB", width=2),
                name="Activity Data",
            )

            # Run algorithms if needed
            if not hasattr(self, "nonwear_data"):
                self.plot_algorithms()

        # Just update the view range based on the mode
        if view_hours == 24:
            # Show noon to noon portion of 48hr data
            start_time = expected_start.timestamp()
            end_time = expected_end.timestamp()
        else:
            # Show full 48hr data
            start_time = expected_start.timestamp()
            end_time = expected_end.timestamp()

        # Configure Y-axis range and ticks to match data
        self.getAxis("left").setRange(self.data_min_y, self.data_max_y)

        # Set view range with Y constrained to data range
        self.vb.setRange(
            xRange=[start_time, end_time],
            yRange=[self.data_min_y, self.data_max_y],
            padding=0,
        )

        # Restore sleep markers if they exist
        if self.daily_sleep_markers.get_all_periods():
            self.redraw_markers()

    def swap_activity_data(self, new_timestamps: list[datetime], new_activity_data: list[float], new_column_type: str) -> None:
        """
        Seamlessly swap activity data without triggering full plot recreation or state loss.

        This method preserves all plot widget state including:
        - Current zoom level and pan position
        - Sleep markers and their positions
        - Nonwear visualizations
        - All other plot elements and settings

        Args:
            new_timestamps: New timestamp data
            new_activity_data: New activity values
            new_column_type: Column type identifier for logging/debugging

        """
        logger.info("SEAMLESS SWAP: Starting data swap to %s column with %s data points", new_column_type, len(new_activity_data))

        try:
            # Store current view state to preserve after swap
            current_view_range = self.vb.viewRange()
            current_x_range = current_view_range[0]
            current_view_range[1]

            # Convert new timestamps to numeric values for plot compatibility
            if new_timestamps:
                # Convert timestamps to numeric values directly (avoid numpy datetime corruption)
                new_x_data = np.array([ts.timestamp() for ts in new_timestamps])
            else:
                new_x_data = np.array([])

            # Update internal data references
            self.timestamps = new_timestamps
            self.x_data = new_x_data
            self.activity_data = new_activity_data

            # Update column type for property access
            self.activity_column_type = new_column_type

            # axis_y_data will be loaded on demand via property
            logger.debug("SEAMLESS SWAP: Column type now %s", new_column_type)

            # Update Y-axis boundaries - keep consistent using VM max
            if new_column_type == "VECTOR_MAGNITUDE":
                # Update max VM value when we have vector magnitude data
                self.max_vm_value = max(new_activity_data) if new_activity_data else 200
                self.data_max_y = self.max_vm_value * 1.5
            # When switching to axis_y, DON'T change the y-axis range at all!
            # Just keep using whatever data_max_y was already set

            # Check if we have an existing activity plot item to update
            if hasattr(self, "activity_plot_item") and self.activity_plot_item is not None:
                # Direct data update - this is the key to seamless swapping
                self.activity_plot_item.setData(new_x_data, new_activity_data)
                logger.debug("SEAMLESS SWAP: Updated existing plot item data directly")
            else:
                # Fallback: create new plot item if none exists
                logger.warning("SEAMLESS SWAP: No existing plot item found, creating new one")
                self.activity_plot_item = self.plot(
                    new_x_data,
                    new_activity_data,
                    pen=pg.mkPen(color="#2E86AB", width=2),
                    name="Activity Data",
                )

            # Update Y-axis range to fixed VM-based range
            self.getAxis("left").setRange(self.data_min_y, self.data_max_y)

            # Restore the X view but keep Y fixed to VM range
            preserved_x_range = current_x_range
            fixed_y_range = [self.data_min_y, self.data_max_y]

            self.vb.setRange(
                xRange=preserved_x_range,
                yRange=fixed_y_range,
                padding=0,
            )

            # Always clear algorithm cache when activity data changes
            # This ensures correct algorithm results for the new activity source
            if hasattr(self, "_algorithm_cache"):
                self._algorithm_cache.clear()
                logger.debug("SEAMLESS SWAP: Cleared algorithm cache for new activity data")

            # Recalculate algorithms with new data
            # NonwearData system will handle its own updates if active
            if hasattr(self, "nonwear_data"):
                logger.debug("SEAMLESS SWAP: NonwearData system active, will update separately")
            self.plot_algorithms()

            # Update file info label to reflect new data source
            self._update_file_info_label()

            logger.info("SEAMLESS SWAP: Data swap completed successfully, preserved view state")

        except Exception as e:
            logger.exception("SEAMLESS SWAP: Failed to swap data: %s", e)
            logger.exception("SEAMLESS SWAP: Traceback: %s", traceback.format_exc())
            # Don't raise - let the application continue with existing data

    def enforce_range_limits(self) -> None:
        """Enforce strict pan/zoom boundaries."""
        if self.data_start_time is None:
            return

        current_range = self.vb.viewRange()
        x_range = current_range[0]  # [xmin, xmax]
        y_range = current_range[1]  # [ymin, ymax]

        # Calculate allowed boundaries based on display mode
        if self.current_view_hours == 24:
            # 24h mode: can only view within the 24h window
            max_start = self.data_start_time
            max_end = self.data_start_time + (24 * 3600)
            max_end = min(max_end, self.data_end_time)  # Don't exceed actual data
        else:
            # 48h mode: can view full dataset
            max_start = self.data_start_time
            max_end = self.data_end_time

        # Correct out-of-bounds X ranges
        x_min = max(x_range[0], max_start)  # Can't pan before start
        x_max = min(x_range[1], max_end)  # Can't pan after end

        # Prevent zooming out beyond allowed range
        current_width = x_max - x_min
        max_width = max_end - max_start

        if current_width > max_width:
            # Force back to full allowed range
            x_min = max_start
            x_max = max_end
        elif x_max - x_min < 1800:  # Minimum 30 minutes visible
            # Prevent over-zooming
            center = (x_range[0] + x_range[1]) / 2
            x_min = center - 900  # 15 minutes before center
            x_max = center + 900  # 15 minutes after center

            # Adjust if this pushes us out of bounds
            if x_min < max_start:
                x_min = max_start
                x_max = x_min + 1800
            elif x_max > max_end:
                x_max = max_end
                x_min = x_max - 1800

        # Force Y range to always be the full data range (no Y-axis zooming)
        y_min = self.data_min_y  # Always 0
        y_max = self.data_max_y  # Always 1.5x max value

        # Fix Y-axis range on the axis itself to prevent visual changes
        self.getAxis("left").setRange(y_min, y_max)

        # Also fix X-axis range to prevent visual axis number changes
        self.getAxis("bottom").setRange(x_min, x_max)

        # Apply corrected ranges if needed
        x_changed = abs(x_min - x_range[0]) > 0.1 or abs(x_max - x_range[1]) > 0.1
        y_changed = abs(y_min - y_range[0]) > 0.1 or abs(y_max - y_range[1]) > 0.1

        if x_changed or y_changed:
            self.vb.blockSignals(True)
            self.vb.setRange(xRange=[x_min, x_max], yRange=[y_min, y_max], padding=0)
            self.vb.blockSignals(False)

    def keyPressEvent(self, event) -> None:  # Qt naming convention
        """Handle keyboard events for marker adjustment and clearing."""
        key = event.key()
        logger.debug(f"Key pressed: {key} (C={Qt.Key.Key_C}, Delete={Qt.Key.Key_Delete})")

        # Handle clear marker shortcuts and incomplete marker cancellation (C and Delete)
        if key in (Qt.Key.Key_C, Qt.Key.Key_Delete):
            # First check if there's an incomplete marker to cancel
            if self.current_marker_being_placed is not None:
                logger.debug("Delete/C key detected - cancelling incomplete marker placement")
                self.cancel_incomplete_marker()
                return

            # Otherwise, clear selected marker set
            logger.debug("Clear marker shortcut detected")
            self.clear_selected_marker_set()
            return

        # Handle marker adjustment for currently selected marker set
        selected_period = self.get_selected_marker_period()
        if selected_period and selected_period.is_complete:
            if key == Qt.Key.Key_Q:  # Move onset left
                self.adjust_selected_marker("onset", -60)  # -1 minute
            elif key == Qt.Key.Key_E:  # Move onset right
                self.adjust_selected_marker("onset", 60)  # +1 minute
            elif key == Qt.Key.Key_A:  # Move offset left
                self.adjust_selected_marker("offset", -60)  # -1 minute
            elif key == Qt.Key.Key_D:  # Move offset right
                self.adjust_selected_marker("offset", 60)  # +1 minute
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def adjust_main_sleep_marker(self, marker_type: str, seconds_delta: int) -> None:
        """Adjust main sleep marker by specified number of seconds."""
        main_sleep = self.daily_sleep_markers.get_main_sleep()
        if not main_sleep or not main_sleep.is_complete:
            return

        # Get current timestamp
        if marker_type == "onset":
            current_timestamp = main_sleep.onset_timestamp
        elif marker_type == "offset":
            current_timestamp = main_sleep.offset_timestamp
        else:
            return

        # Calculate new timestamp
        new_timestamp = current_timestamp + seconds_delta

        # Ensure timestamp is within data bounds
        if not (self.data_start_time <= new_timestamp <= self.data_end_time):
            return

        # Update the timestamp
        if marker_type == "onset":
            # Ensure onset is before offset
            if new_timestamp < main_sleep.offset_timestamp:
                main_sleep.onset_timestamp = new_timestamp
            else:
                return
        elif marker_type == "offset":
            # Ensure offset is after onset
            if new_timestamp > main_sleep.onset_timestamp:
                main_sleep.offset_timestamp = new_timestamp
            else:
                return

        # Update classifications and redraw
        self.daily_sleep_markers.update_classifications()
        self.redraw_markers()
        self.sleep_markers_changed.emit(self.daily_sleep_markers)

    def move_marker_to_timestamp(self, marker_type: str, target_timestamp: float, period_slot: int | None = None) -> bool:
        """
        Move a marker to a specific timestamp with validation.

        Args:
            marker_type: "onset" or "offset"
            target_timestamp: Unix timestamp to move the marker to
            period_slot: Optional period slot (1-4). If None, uses main sleep period.

        Returns:
            bool: True if marker was moved successfully, False otherwise

        """
        # Snap to nearest minute
        target_timestamp = round(target_timestamp / 60) * 60

        # Ensure timestamp is within data bounds
        if not (self.data_start_time <= target_timestamp <= self.data_end_time):
            logger.warning(f"Target timestamp {target_timestamp} is outside data bounds [{self.data_start_time}, {self.data_end_time}]")
            return False

        # Get the target period
        if period_slot is None:
            # Use main sleep period
            period = self.daily_sleep_markers.get_main_sleep()
            if not period:
                logger.warning("No main sleep period to move marker for")
                return False
        else:
            # Get period by slot
            period = self.daily_sleep_markers.get_period_by_slot(period_slot)
            if not period:
                logger.warning(f"No period found in slot {period_slot}")
                return False

        # Check if period is complete (has both markers)
        if not period.is_complete:
            logger.warning("Cannot move marker for incomplete period")
            return False

        # Validate the new position
        if marker_type == "onset":
            # Ensure onset would be before offset
            if target_timestamp >= period.offset_timestamp:
                logger.warning(f"Cannot move onset to {target_timestamp} - would be after offset at {period.offset_timestamp}")
                return False
            # Update onset timestamp
            period.onset_timestamp = target_timestamp
        elif marker_type == "offset":
            # Ensure offset would be after onset
            if target_timestamp <= period.onset_timestamp:
                logger.warning(f"Cannot move offset to {target_timestamp} - would be before onset at {period.onset_timestamp}")
                return False
            # Update offset timestamp
            period.offset_timestamp = target_timestamp
        else:
            logger.warning(f"Invalid marker type: {marker_type}")
            return False

        # Update classifications and check for duration ties
        self.daily_sleep_markers.update_classifications()
        if self.daily_sleep_markers.check_duration_tie():
            # Duration tie detected - notify user but keep markers
            self.marker_limit_exceeded.emit("Warning: Multiple periods with identical duration detected")

        # Redraw markers and apply sleep scoring rules
        self.redraw_markers()

        # Apply sleep scoring rules if this is the selected period
        if period is self.get_selected_marker_period():
            self.apply_sleep_scoring_rules(period)

        # Emit change signal (redraw_markers doesn't always emit this)
        self.sleep_markers_changed.emit(self.daily_sleep_markers)

        logger.info(f"Successfully moved {marker_type} marker to timestamp {target_timestamp}")
        return True

    def add_sleep_marker(self, timestamp: float) -> None:
        """Add sleep marker using new extended marker system."""
        try:
            if self.current_marker_being_placed is None:
                # Start new sleep period
                if not self.daily_sleep_markers.has_space_for_new_period():
                    self.marker_limit_exceeded.emit(f"Maximum {MarkerLimits.MAX_SLEEP_PERIODS_PER_DAY} sleep periods per day allowed")
                    return

                # Determine what type this marker will be based on existing complete periods
                from sleep_scoring_app.core.dataclasses import MarkerType

                main_sleep = self.daily_sleep_markers.get_main_sleep()

                # If no main sleep exists, this will become main sleep
                # Otherwise it's a nap
                marker_type = MarkerType.MAIN_SLEEP if main_sleep is None else MarkerType.NAP

                # Create new incomplete period (onset only) with the correct type
                self.current_marker_being_placed = SleepPeriod(onset_timestamp=timestamp, offset_timestamp=None, marker_type=marker_type)

            else:
                # Complete the current period (add offset)
                if timestamp <= self.current_marker_being_placed.onset_timestamp:
                    # Invalid: offset before onset, reset
                    self.current_marker_being_placed = None
                    return

                self.current_marker_being_placed.offset_timestamp = timestamp

                # Find next available slot and add to daily markers
                slot = self._get_next_available_slot()
                if slot is not None:
                    self.current_marker_being_placed.marker_index = slot
                    self._assign_period_to_slot(self.current_marker_being_placed, slot)

                    # Set this as the currently selected marker set
                    self.selected_marker_set_index = slot

                    # Update classifications and emit signal
                    self.daily_sleep_markers.update_classifications()

                    # Check for duration ties
                    if self.daily_sleep_markers.check_duration_tie():
                        # Remove the just-added period
                        self._remove_period_from_slot(slot)
                        self.marker_limit_exceeded.emit("Cannot determine main sleep: multiple periods with identical duration")
                    else:
                        self.sleep_markers_changed.emit(self.daily_sleep_markers)

                self.current_marker_being_placed = None

            self.redraw_markers()

        except Exception:
            logger.exception("Error adding sleep marker")
            self.current_marker_being_placed = None

    def _get_next_available_slot(self) -> int | None:
        """Get the next available period slot (1, 2, 3, or 4)."""
        if self.daily_sleep_markers.period_1 is None:
            return 1
        if self.daily_sleep_markers.period_2 is None:
            return 2
        if self.daily_sleep_markers.period_3 is None:
            return 3
        if self.daily_sleep_markers.period_4 is None:
            return 4
        return None

    def _assign_period_to_slot(self, period: SleepPeriod, slot: int) -> None:
        """Assign a sleep period to a specific slot."""
        if slot == 1:
            self.daily_sleep_markers.period_1 = period
        elif slot == 2:
            self.daily_sleep_markers.period_2 = period
        elif slot == 3:
            self.daily_sleep_markers.period_3 = period
        elif slot == 4:
            self.daily_sleep_markers.period_4 = period

    def _remove_period_from_slot(self, slot: int) -> None:
        """Remove a sleep period from a specific slot."""
        if slot == 1:
            self.daily_sleep_markers.period_1 = None
        elif slot == 2:
            self.daily_sleep_markers.period_2 = None
        elif slot == 3:
            self.daily_sleep_markers.period_3 = None
        elif slot == 4:
            self.daily_sleep_markers.period_4 = None

    # ========== Marker Methods (delegated to PlotMarkerRenderer) ==========

    def _get_nap_number(self, period: SleepPeriod) -> int:
        """Get the sequential nap number for a given period."""
        return self.marker_renderer.get_nap_number(period)

    def _prepare_sleep_period_markers(self, period: SleepPeriod, is_main_sleep: bool) -> list[pg.InfiniteLine]:
        """Prepare onset and offset markers for a sleep period."""
        return self.marker_renderer.prepare_sleep_period_markers(period, is_main_sleep)

    def _draw_sleep_period(self, period: SleepPeriod, is_main_sleep: bool) -> None:
        """Draw onset and offset markers for a sleep period."""
        self.marker_renderer.draw_sleep_period(period, is_main_sleep)

    def _draw_incomplete_marker(self, period: SleepPeriod) -> None:
        """Draw a temporary marker for an incomplete sleep period."""
        self.marker_renderer.draw_incomplete_marker(period)

    def _create_marker_line(
        self, timestamp: float, color: str, label: str, period: SleepPeriod | None, marker_type: str, is_selected: bool = False
    ) -> pg.InfiniteLine:
        """Create a draggable marker line with proper styling and behavior."""
        return self.marker_renderer.create_marker_line(timestamp, color, label, period, marker_type, is_selected)

    def _create_marker_line_no_add(
        self, timestamp: float, color: str, label: str, period: SleepPeriod | None, marker_type: str, is_selected: bool = False
    ) -> pg.InfiniteLine:
        """Create a draggable marker line without adding to plot."""
        return self.marker_renderer.create_marker_line_no_add(timestamp, color, label, period, marker_type, is_selected)

    def load_daily_sleep_markers(self, daily_markers: DailySleepMarkers, markers_saved: bool = True) -> None:
        """Load existing daily sleep markers into the plot widget."""
        self.marker_renderer.load_daily_sleep_markers(daily_markers, markers_saved)

    def get_daily_sleep_markers(self) -> DailySleepMarkers:
        """Get the current daily sleep markers."""
        return self.marker_renderer.get_daily_sleep_markers()

    def remove_sleep_period(self, period_index: int) -> bool:
        """Remove a sleep period by its index (1, 2, 3, or 4)."""
        return self.marker_renderer.remove_sleep_period(period_index)

    def display_adjacent_day_markers(self, adjacent_day_markers_data: list) -> None:
        """Display adjacent day markers from adjacent days."""
        self.marker_renderer.display_adjacent_day_markers(adjacent_day_markers_data)

    def clear_adjacent_day_markers(self) -> None:
        """Clear all adjacent day markers from the plot."""
        self.marker_renderer.clear_adjacent_day_markers()

    def redraw_markers(self) -> None:
        """Redraw all sleep markers with proper colors for main sleep vs naps."""
        self.marker_renderer.redraw_markers()

    def _update_all_marker_labels(self) -> None:
        """Update labels and colors for all marker lines based on current classifications."""
        self.marker_renderer.update_marker_visual_state()

    def _update_marker_labels_text_only(self) -> None:
        """Update only the text of marker labels (safe for real-time updates during drag)."""
        self.marker_renderer.update_marker_labels_text_only()

    def get_marker_data(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract surrounding data for main sleep markers."""
        main_sleep = self.daily_sleep_markers.get_main_sleep()
        if not main_sleep or not main_sleep.is_complete:
            return [], []

        if not hasattr(self, "timestamps") or not hasattr(self, "axis_y_data"):
            return [], []

        first_marker_ts = main_sleep.onset_timestamp
        last_marker_ts = main_sleep.offset_timestamp

        # Find indices for markers using optimized lookup
        first_marker_idx = self._find_closest_data_index(first_marker_ts)
        last_marker_idx = self._find_closest_data_index(last_marker_ts)

        onset_data = []
        offset_data = []

        # Get Sadeh, Choi, and Nonwear Sensor results if available
        sadeh_results = getattr(self, "sadeh_results", [])
        choi_results = self.get_choi_results_per_minute()
        nonwear_sensor_results = self.get_nonwear_sensor_results_per_minute()

        if first_marker_idx is not None:
            # Get 21 elements around first marker (10 before + marker + 10 after)
            start_idx = max(0, first_marker_idx - 10)
            end_idx = min(len(self.timestamps), first_marker_idx + 11)  # +11 to include 10 after

            for i in range(start_idx, end_idx):
                # Comprehensive bounds checking for all arrays
                if i < len(self.timestamps) and i < len(self.axis_y_data) and 0 <= i < len(self.timestamps):
                    is_marker = i == first_marker_idx
                    sadeh_value = sadeh_results[i] if i < len(sadeh_results) else 0
                    choi_value = choi_results[i] if i < len(choi_results) else 0
                    nwt_value = nonwear_sensor_results[i] if i < len(nonwear_sensor_results) else 0

                    onset_data.append(
                        {
                            "time": self.timestamps[i].strftime("%H:%M"),
                            "activity": int(self.axis_y_data[i]),
                            "sadeh": sadeh_value,
                            "choi": choi_value,
                            "nwt_sensor": nwt_value,
                            "is_marker": is_marker,
                        },
                    )

        if last_marker_idx is not None:
            # Get 21 elements around last marker (10 before + marker + 10 after)
            start_idx = max(0, last_marker_idx - 10)
            end_idx = min(len(self.timestamps), last_marker_idx + 11)  # +11 to include 10 after

            for i in range(start_idx, end_idx):
                if i < len(self.timestamps) and i < len(self.axis_y_data):
                    is_marker = i == last_marker_idx
                    sadeh_value = sadeh_results[i] if i < len(sadeh_results) else 0
                    choi_value = choi_results[i] if i < len(choi_results) else 0
                    nwt_value = nonwear_sensor_results[i] if i < len(nonwear_sensor_results) else 0
                    offset_data.append(
                        {
                            "time": self.timestamps[i].strftime("%H:%M"),
                            "activity": int(self.axis_y_data[i]),
                            "sadeh": sadeh_value,
                            "choi": choi_value,
                            "nwt_sensor": nwt_value,
                            "is_marker": is_marker,
                        },
                    )

        return onset_data, offset_data

    def _find_closest_data_index(self, target_timestamp):
        """Find the data index closest to the target timestamp using efficient search."""
        if not hasattr(self, "timestamps") or not self.timestamps:
            return None

        # Convert Unix timestamp back to naive datetime in local timezone
        # (matches how the original timestamps were converted to Unix time)
        target_dt = datetime.fromtimestamp(target_timestamp)

        # Simple linear search comparing FULL timestamps, not just time-of-day
        best_idx = None
        min_diff = float("inf")

        for i, timestamp in enumerate(self.timestamps):
            # Calculate difference in total seconds between full timestamps
            time_diff = abs((target_dt - timestamp).total_seconds())

            if time_diff < min_diff:
                min_diff = time_diff
                best_idx = i

            # If we found a very close match (within 30 seconds), stop searching
            if time_diff < 30:
                break

        return best_idx

    def get_choi_results_per_minute(self) -> list[int]:
        """Get Choi nonwear periods as per-minute results (1=nonwear, 0=wear)."""
        # Use NonwearData system if available
        if hasattr(self, "nonwear_data"):
            return list(self.nonwear_data.choi_mask)

        # Fallback: compute on demand if NonwearData system not active
        if not hasattr(self, "axis_y_data"):
            return []

        choi_per_minute = [0] * len(self.axis_y_data)
        algorithms = SleepScoringAlgorithms()
        choi_periods = algorithms.run_choi_algorithm(self.axis_y_data)

        # Convert periods to per-minute mask
        for period in choi_periods:
            start_idx = period["start_index"]
            end_idx = period["end_index"]
            for i in range(start_idx, min(end_idx + 1, len(choi_per_minute))):
                choi_per_minute[i] = 1

        return choi_per_minute

    def get_nonwear_sensor_results_per_minute(self) -> list[int]:
        """Get nonwear sensor periods as per-minute results (1=nonwear, 0=wear)."""
        # Use NonwearData system if available
        if hasattr(self, "nonwear_data"):
            return list(self.nonwear_data.sensor_mask)

        # Fallback processing if NonwearData system hasn't been used yet
        # This should rarely be used now that we have the unified NonwearData system
        logger.warning("Using fallback sensor data processing - NonwearData system not active")
        if not hasattr(self, "activity_data"):
            return []
        return [0] * len(self.activity_data)  # Return all wear periods as fallback

    @property
    def axis_y_data(self) -> list[float]:
        """Property that loads axis_y data on demand using unified loader."""
        # NEVER use display data for Sadeh - always load actual axis_y data
        # This ensures Sadeh algorithm always uses correct axis_y data regardless of display preference
        return self._get_axis_y_data_for_sadeh()

    def _get_axis_y_data_for_sadeh(self) -> list[float]:
        """Get axis_y data specifically for Sadeh algorithm using unified loader."""
        # Always use parent window's unified loading method
        if hasattr(self, "parent_window") and self.parent_window and hasattr(self.parent_window, "_get_axis_y_data_for_sadeh"):
            return self.parent_window._get_axis_y_data_for_sadeh()

        logger.warning("Parent window doesn't have unified axis_y loader")
        return []  # No fallback - must use unified loader

    def _extract_view_subset_from_main_results(self) -> None:
        """Extract the current view subset from main 48hr algorithm results."""
        self.algorithm_manager._extract_view_subset_from_main_results()

    def plot_algorithms(self) -> None:
        """Run and plot algorithms with performance optimization and caching."""
        self.algorithm_manager.plot_algorithms()

    def plot_choi_results(self, nonwear_periods) -> None:
        """Plot Choi nonwear periods as purple background regions (optimized)."""
        self.algorithm_manager.plot_choi_results(nonwear_periods)

    def extract_participant_info(self) -> dict[str, str]:
        """Extract participant information using centralized extractor."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        try:
            # Get selected file from parent window or self
            selected_file = None
            if hasattr(self, "parent_window") and self.parent_window and hasattr(self.parent_window, "selected_file"):
                selected_file = self.parent_window.selected_file
            elif hasattr(self, "selected_file"):
                selected_file = self.selected_file

            if not selected_file:
                # Fallback to timestamp-based naming if no file info
                return {
                    "participant_id": "Unknown",
                    "timepoint": "Unknown",
                }

            # Use centralized extractor
            participant_info = extract_participant_info(selected_file)

            return {
                "participant_id": participant_info.numerical_id,
                "timepoint": participant_info.timepoint,
            }

        except Exception:
            # Ultimate fallback
            return {
                "participant_id": "Unknown",
                "timepoint": "Unknown",
            }

    def apply_sleep_scoring_rules(self, main_sleep_period: SleepPeriod) -> None:
        """Apply 3 minute rule for onset and 5 minute rule for offset to selected marker set."""
        self.algorithm_manager.apply_sleep_scoring_rules(main_sleep_period)

    def create_sleep_onset_marker(self, timestamp) -> None:
        """Create sleep onset marker with arrow and axis label."""
        self.algorithm_manager.create_sleep_onset_marker(timestamp)

    def create_sleep_offset_marker(self, timestamp) -> None:
        """Create sleep offset marker with arrow and axis label."""
        self.algorithm_manager.create_sleep_offset_marker(timestamp)

    def clear_sleep_onset_offset_markers(self) -> None:
        """Clear sleep onset/offset markers from 3/5 rule."""
        self.algorithm_manager.clear_sleep_onset_offset_markers()

    def clear_sleep_markers(self) -> None:
        """Remove all sleep markers."""
        self.marker_renderer.clear_sleep_markers()
        self.clear_sleep_onset_offset_markers()
        self.sleep_markers_changed.emit(self.daily_sleep_markers)

    def clear_plot(self) -> None:
        """Clear all plot data and markers."""
        # Clear the main plot
        self.plotItem.clear()

        # Clear sleep markers
        self.clear_sleep_markers()

        # Clear nonwear visualizations
        self.clear_nonwear_visualizations()

        # Reset plot state
        self.data_start_time = None
        self.data_end_time = None
        self.data_min_y = 0
        self.data_max_y = 100

    def get_sleep_duration(self) -> float | None:
        """Calculate duration of the currently selected marker period."""
        selected_period = self.get_selected_marker_period()
        if selected_period and selected_period.is_complete:
            return selected_period.duration_hours
        return None

    def get_selected_marker_period(self) -> SleepPeriod | None:
        """Get the currently selected marker period."""
        return self.marker_renderer.get_selected_marker_period()

    def clear_selected_marker_set(self) -> None:
        """Clear the currently selected marker set."""
        self.marker_renderer.clear_selected_marker_set()

    def cancel_incomplete_marker(self) -> None:
        """Cancel the current incomplete marker placement and remove its visual indicator."""
        self.marker_renderer.cancel_incomplete_marker()

    def adjust_selected_marker(self, marker_type: str, seconds_delta: int) -> None:
        """Adjust selected marker set by specified number of seconds."""
        self.marker_renderer.adjust_selected_marker(marker_type, seconds_delta)

    def _update_sleep_scoring_rules(self) -> None:
        """Update sleep scoring rules for the currently selected marker period."""
        selected_period = self.get_selected_marker_period()
        if selected_period and selected_period.is_complete:
            self.apply_sleep_scoring_rules(selected_period)

    def _select_marker_set_by_period(self, period: SleepPeriod) -> None:
        """Select the marker set that contains the given period."""
        self.marker_renderer.select_marker_set_by_period(period)

    def _auto_select_marker_set(self) -> None:
        """Automatically select an appropriate marker set when the current one is cleared."""
        self.marker_renderer.auto_select_marker_set()

    def _update_marker_visual_state(self) -> None:
        """Update the visual state of all markers to reflect current selection."""
        self.marker_renderer.update_marker_visual_state()

    def add_background_region(
        self,
        start_time,
        end_time,
        color=(220, 53, 69, 40),
        border_color=(220, 53, 69, 120),
    ) -> pg.LinearRegionItem:
        """Add a background region (e.g., for nonwear periods)."""
        region = pg.LinearRegionItem(
            [start_time, end_time],
            brush=pg.mkBrush(*color),
            pen=pg.mkPen(*border_color[:3], width=1),
            movable=False,
        )
        region.setZValue(-10)  # Behind the activity plot
        self.plotItem.addItem(region)
        return region

    # ========== Overlay Methods (delegated to PlotOverlayRenderer) ==========

    def set_nonwear_data(self, nonwear_data) -> None:
        """Set nonwear data using immutable NonwearData structure."""
        self.overlay_renderer.set_nonwear_data(nonwear_data)

    def clear_nonwear_visualizations(self) -> None:
        """Clear all nonwear period visualizations."""
        self.overlay_renderer.clear_nonwear_visualizations()

    def plot_nonwear_periods(self) -> None:
        """Plot nonwear periods using the same per-minute data as table/mouseover."""
        self.overlay_renderer.plot_nonwear_periods()

    def update_choi_overlay_only(self, new_activity_data: list[float]) -> None:
        """Recalculate Choi algorithm with new data while preserving Sadeh algorithm state."""
        self.overlay_renderer.update_choi_overlay_only(new_activity_data)

    def update_choi_overlay_async(self, new_activity_data: list[float]) -> None:
        """Asynchronously recalculate Choi algorithm with new data."""
        self.overlay_renderer.update_choi_overlay_async(new_activity_data)

    def _update_choi_cache_key(self, new_activity_data: list[float]) -> None:
        """Update cache key for Choi results while preserving Sadeh cache."""
        self.overlay_renderer._update_choi_cache_key(new_activity_data)

    def restore_choi_from_cache(self, activity_data: list[float]) -> bool:
        """Attempt to restore Choi results from cache for quick switching."""
        return self.overlay_renderer.restore_choi_from_cache(activity_data)

    def clear_choi_cache(self) -> None:
        """Clear the Choi algorithm results cache."""
        self.overlay_renderer.clear_choi_cache()

    def get_choi_cache_info(self) -> dict[str, int]:
        """Get information about the current Choi cache state."""
        return self.overlay_renderer.get_choi_cache_info()

    def validate_choi_overlay_state(self) -> bool:
        """Validate the current Choi overlay state for consistency."""
        return self.overlay_renderer.validate_choi_overlay_state()

    def _convert_choi_results_to_periods(self):
        """Convert dynamically generated Choi results to NonwearPeriod format."""
        return self.overlay_renderer.convert_choi_results_to_periods()

    def add_visual_marker(self, timestamp, text, color="#0066CC", position_factor=0.90) -> tuple[pg.ArrowItem, pg.TextItem]:
        """Add a visual marker with arrow and text at specified timestamp."""
        # Create arrow pointing down to the timeline
        arrow = pg.ArrowItem(
            pos=(timestamp, self.data_max_y * 0.88),
            angle=-90,  # Point downward
            headLen=15,
            headWidth=12,
            tailLen=25,
            tailWidth=3,
            pen=pg.mkPen(color=color, width=2),
            brush=pg.mkBrush(color=color),
        )
        arrow.setZValue(10)  # Above everything else
        self.plotItem.addItem(arrow)

        # Create text label above the arrow
        time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M")
        text_item = pg.TextItem(
            text=f"{text} at {time_str}",
            color=color,
            anchor=(0.5, 1.0),  # Center horizontally, bottom of text at point
        )
        text_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        text_item.setPos(timestamp, self.data_max_y * position_factor)
        text_item.setZValue(10)
        self.plotItem.addItem(text_item)

        return arrow, text_item

    def on_plot_clicked(self, event) -> None:
        """Handle mouse clicks for placing sleep markers."""
        # Handle right-click cancellation of incomplete markers
        if event.button() == Qt.MouseButton.RightButton:
            if self.current_marker_being_placed is not None:
                logger.debug("Right-click detected - cancelling incomplete marker placement")
                self.cancel_incomplete_marker()
            return

        # Only process left mouse button clicks for placement
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Ensure this widget has keyboard focus for keyboard shortcuts
        self.setFocus()

        # Don't create new markers if we just clicked on an existing marker
        if self._marker_click_in_progress:
            logger.debug("Skipping plot click - marker was clicked")
            return

        # Get mouse position in data coordinates
        mouse_pos = event.scenePos()
        if self.plotItem.sceneBoundingRect().contains(mouse_pos):
            # Convert to data coordinates
            data_pos = self.plotItem.getViewBox().mapSceneToView(mouse_pos)
            clicked_time = data_pos.x()

            # Check if click is within data boundaries
            if self.data_start_time <= clicked_time <= self.data_end_time:
                self.add_sleep_marker(clicked_time)

        # Update marker visual state when clicking away from markers
        # This ensures selected markers stay emboldened/brightened even when clicked away
        self._update_marker_visual_state()

    def _on_mouse_move_throttled(self, pos) -> None:
        """Throttled mouse move handler to improve performance."""
        self._last_mouse_pos = pos

        # Throttle mouse move events to avoid excessive processing
        if not self._mouse_move_timer.isActive():
            self._mouse_move_timer.start(50)  # Process at most every 50ms

    def _process_mouse_move(self) -> None:
        """Process the last mouse move position."""
        if self._last_mouse_pos is not None:
            self.on_mouse_move(self._last_mouse_pos)

    def on_mouse_move(self, pos) -> None:
        """Handle mouse movement for tooltips."""
        if not hasattr(self, "axis_y_data") or not hasattr(self, "x_data"):
            return

        # Check if mouse is over the plot area
        if self.plotItem.sceneBoundingRect().contains(pos):
            # Convert to data coordinates
            data_pos = self.plotItem.getViewBox().mapSceneToView(pos)
            hover_time = data_pos.x()

            # Check if hover is within data boundaries
            if self.data_start_time <= hover_time <= self.data_end_time:
                # Find closest data point
                closest_idx = self._find_closest_data_index(hover_time)
                if closest_idx is not None and closest_idx < len(self.axis_y_data):
                    axis_y_value = self.axis_y_data[closest_idx]
                    timestamp = self.timestamps[closest_idx]

                    # Format tooltip text
                    time_str = timestamp.strftime("%H:%M")
                    tooltip_text = f"Time: {time_str}\nActivity: {axis_y_value}"

                    # Add sleep scoring info if available
                    if hasattr(self, "sadeh_results") and closest_idx < len(self.sadeh_results):
                        sadeh_value = self.sadeh_results[closest_idx]
                        sadeh_state = "Sleep" if sadeh_value == 1 else "Wake"
                        tooltip_text += f"\nSadeh: {sadeh_state}"

                    # Add Choi algorithm info if available
                    choi_results = self.get_choi_results_per_minute()
                    if choi_results and closest_idx < len(choi_results):
                        choi_value = choi_results[closest_idx]
                        choi_state = "Nonwear" if choi_value == 1 else "Wear"
                        tooltip_text += f"\nChoi: {choi_state}"

                    # Add nonwear sensor info if available
                    nonwear_sensor_results = self.get_nonwear_sensor_results_per_minute()
                    if nonwear_sensor_results and closest_idx < len(nonwear_sensor_results):
                        nwt_value = nonwear_sensor_results[closest_idx]
                        nwt_state = "Nonwear" if nwt_value == 1 else "Wear"
                        tooltip_text += f"\nNWT Sensor: {nwt_state}"

                    # Set tooltip
                    self.setToolTip(tooltip_text)
                else:
                    self.setToolTip("")
            else:
                self.setToolTip("")
        else:
            self.setToolTip("")

    def capture_complete_state(self) -> dict[str, Any]:
        """Capture complete UI state for seamless data source switching."""
        return self.state_serializer.capture_complete_state()

    def restore_complete_state(self, state_dict: dict[str, Any]) -> bool:
        """Restore complete UI state for seamless data source switching."""
        return self.state_serializer.restore_complete_state(state_dict)

    def _serialize_sleep_period(self, period: SleepPeriod | None) -> dict[str, Any] | None:
        """Serialize a SleepPeriod to a dictionary for state storage."""
        return self.state_serializer._serialize_sleep_period(period)

    def _deserialize_sleep_period(self, data: dict[str, Any] | None) -> SleepPeriod | None:
        """Deserialize a dictionary back to a SleepPeriod."""
        return self.state_serializer._deserialize_sleep_period(data)

    def _update_file_info_label(self) -> None:
        """Update the file info label with the currently loaded file information."""
        # Check if we have an external label widget to use instead of plot TextItem
        external_label = getattr(self, "external_filename_label", None)

        if external_label:
            # Use external QLabel widget
            if self.current_filename:
                # Extract participant info directly from the filename
                from sleep_scoring_app.utils.participant_extractor import extract_participant_info

                info = extract_participant_info(self.current_filename)

                # Create display text showing the actual loaded data
                participant_id = info.numerical_id
                timepoint = info.timepoint
                group = info.group

                label_text = f"Loaded: {participant_id} {timepoint} {group} ({self.current_filename})"
                external_label.setText(label_text)
                external_label.setVisible(True)
            else:
                external_label.setText("")
                external_label.setVisible(False)

            # Clean up any existing plot TextItem if we're switching to external label
            if self.file_info_label:
                self.plotItem.removeItem(self.file_info_label)
                self.file_info_label = None
        else:
            # Fallback to original TextItem behavior for backward compatibility
            # Remove existing label if it exists
            if self.file_info_label:
                self.plotItem.removeItem(self.file_info_label)
                self.file_info_label = None

            # Create new label if we have filename
            if self.current_filename:
                # Extract participant info directly from the filename that was loaded from database/CSV
                # This is independent of the table selection, ensuring accuracy
                from sleep_scoring_app.utils.participant_extractor import extract_participant_info

                info = extract_participant_info(self.current_filename)

                # Create display text showing the actual loaded data
                participant_id = info.numerical_id
                timepoint = info.timepoint
                group = info.group

                label_text = f"Loaded: {participant_id} {timepoint} {group} ({self.current_filename})"

                # Create text item
                import pyqtgraph as pg
                from PyQt6.QtGui import QFont

                self.file_info_label = pg.TextItem(
                    text=label_text,
                    color=(0, 0, 0),  # Black text for maximum visibility
                    anchor=(0, 0),  # Bottom-left anchor to position lower
                )

                # Create bold font for better visibility
                self.file_info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))

                # Position in top-left corner of plot area
                view_range = self.vb.viewRange()
                x_min = view_range[0][0]
                y_max = view_range[1][1]

                # Offset slightly from the edges
                x_offset = (view_range[0][1] - view_range[0][0]) * 0.02  # 2% from left edge
                y_offset = (view_range[1][1] - view_range[1][0]) * 0.05  # 5% from top edge

                self.file_info_label.setPos(x_min + x_offset, y_max - y_offset)
                self.file_info_label.setZValue(15)  # Above all other elements

                # Add to plot
                self.plotItem.addItem(self.file_info_label)
