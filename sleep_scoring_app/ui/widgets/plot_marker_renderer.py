#!/usr/bin/env python3
"""
Plot Marker Renderer for Activity Plot Widget.

Manages all marker rendering operations for the activity plot including:
- Sleep marker creation and rendering
- Marker visual state management
- Marker drag handling
- Adjacent day marker display
- Marker selection and highlighting
"""

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer

from sleep_scoring_app.core.constants import MarkerCategory, UIColors
from sleep_scoring_app.core.dataclasses import (
    DailyNonwearMarkers,
    DailySleepMarkers,
    ManualNonwearPeriod,
    MarkerType,
    SleepPeriod,
)

if TYPE_CHECKING:
    from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

logger = logging.getLogger(__name__)


class PlotMarkerRenderer:
    """
    Manages marker rendering for the activity plot widget.

    Responsibilities:
    - Create and render sleep markers (onset/offset lines)
    - Handle marker drag events
    - Manage marker selection state
    - Update marker visual appearance
    - Display adjacent day markers
    """

    def __init__(self, parent: ActivityPlotWidget) -> None:
        """Initialize the plot marker renderer."""
        self.parent = parent
        logger.info("PlotMarkerRenderer initialized")

    # ========== Marker State Access ==========

    @property
    def daily_sleep_markers(self) -> DailySleepMarkers:
        """Get daily sleep markers from parent."""
        return self.parent.daily_sleep_markers

    @daily_sleep_markers.setter
    def daily_sleep_markers(self, value: DailySleepMarkers) -> None:
        """Set daily sleep markers on parent."""
        self.parent.daily_sleep_markers = value

    @property
    def marker_lines(self) -> list:
        """Get marker lines from parent."""
        return self.parent.marker_lines

    @marker_lines.setter
    def marker_lines(self, value: list) -> None:
        """Set marker lines on parent."""
        self.parent.marker_lines = value

    @property
    def selected_marker_set_index(self) -> int:
        """Get selected marker set index from parent."""
        return self.parent.selected_marker_set_index

    @selected_marker_set_index.setter
    def selected_marker_set_index(self, value: int) -> None:
        """Set selected marker set index on parent."""
        self.parent.selected_marker_set_index = value

    # ========== Nonwear Marker State Access ==========

    @property
    def daily_nonwear_markers(self) -> DailyNonwearMarkers:
        """Get daily nonwear markers from parent."""
        if not hasattr(self.parent, "_daily_nonwear_markers"):
            self.parent._daily_nonwear_markers = DailyNonwearMarkers()
        return self.parent._daily_nonwear_markers

    @daily_nonwear_markers.setter
    def daily_nonwear_markers(self, value: DailyNonwearMarkers) -> None:
        """Set daily nonwear markers on parent."""
        self.parent._daily_nonwear_markers = value

    @property
    def nonwear_marker_lines(self) -> list:
        """Get nonwear marker lines from parent."""
        if not hasattr(self.parent, "_nonwear_marker_lines"):
            self.parent._nonwear_marker_lines = []
        return self.parent._nonwear_marker_lines

    @nonwear_marker_lines.setter
    def nonwear_marker_lines(self, value: list) -> None:
        """Set nonwear marker lines on parent."""
        self.parent._nonwear_marker_lines = value

    @property
    def selected_nonwear_marker_index(self) -> int:
        """Get selected nonwear marker index from parent."""
        if not hasattr(self.parent, "_selected_nonwear_marker_index"):
            self.parent._selected_nonwear_marker_index = 1
        return self.parent._selected_nonwear_marker_index

    @selected_nonwear_marker_index.setter
    def selected_nonwear_marker_index(self, value: int) -> None:
        """Set selected nonwear marker index on parent."""
        self.parent._selected_nonwear_marker_index = value

    @property
    def nonwear_markers_visible(self) -> bool:
        """Get nonwear markers visibility from parent."""
        if not hasattr(self.parent, "_nonwear_markers_visible"):
            self.parent._nonwear_markers_visible = True
        return self.parent._nonwear_markers_visible

    @nonwear_markers_visible.setter
    def nonwear_markers_visible(self, value: bool) -> None:
        """Set nonwear markers visibility on parent."""
        self.parent._nonwear_markers_visible = value

    # ========== Nap Numbering ==========

    def get_nap_number(self, period: SleepPeriod) -> int:
        """Get the sequential nap number for a given period."""
        naps = self.daily_sleep_markers.get_naps()
        # Sort naps by onset time to ensure consistent numbering
        sorted_naps = sorted(naps, key=lambda p: p.onset_timestamp or 0)
        for i, nap in enumerate(sorted_naps, 1):
            if nap is period:
                return i
        return 1  # Default to 1 if not found

    # ========== Marker Creation ==========

    def create_marker_line(
        self,
        timestamp: float,
        color: str,
        label: str,
        period: SleepPeriod | None,
        marker_type: str,
        is_selected: bool = False,
    ) -> pg.InfiniteLine:
        """Create a draggable marker line with proper styling and behavior."""
        line = self._create_marker_line_internal(timestamp, color, label, period, marker_type, is_selected)
        self.parent.plotItem.addItem(line)
        return line

    def create_marker_line_no_add(
        self,
        timestamp: float,
        color: str,
        label: str,
        period: SleepPeriod | None,
        marker_type: str,
        is_selected: bool = False,
    ) -> pg.InfiniteLine:
        """Create a draggable marker line without adding to plot (for batch operations)."""
        return self._create_marker_line_internal(timestamp, color, label, period, marker_type, is_selected)

    def _create_marker_line_internal(
        self,
        timestamp: float,
        color: str,
        label: str,
        period: SleepPeriod | None,
        marker_type: str,
        is_selected: bool = False,
    ) -> pg.InfiniteLine:
        """Internal method to create marker line."""
        # Use thicker line for selected markers
        line_width = 5 if is_selected else 3

        line = pg.InfiniteLine(
            pos=timestamp,
            angle=90,  # Vertical line
            pen=pg.mkPen(color, width=line_width, style=pg.QtCore.Qt.PenStyle.SolidLine),
            movable=(marker_type != "incomplete"),  # Incomplete markers not draggable
            bounds=[self.parent.data_start_time, self.parent.data_end_time],
            label=label,
            labelOpts={
                "position": 0.5,
                "color": (255, 255, 255),
                "fill": pg.mkBrush(color),
                "border": pg.mkPen(color, width=2),
                "rotateAxis": (1, 0),  # Rotate text to be vertical
            },
        )

        # Set hover color to gray for colorblind accessibility
        line.setHoverPen(pg.mkPen(UIColors.HOVERED_MARKER, width=line_width + 1, style=pg.QtCore.Qt.PenStyle.SolidLine))

        # Connect drag events for complete markers
        if marker_type != "incomplete":
            # Store period and marker type on line for drag handling
            line.period = period
            line.marker_type = marker_type

            line.sigPositionChangeFinished.connect(partial(self._on_marker_drag_finished_wrapper, line))
            line.sigPositionChanged.connect(partial(self._on_marker_dragged_wrapper, line))
            line.sigClicked.connect(partial(self._on_marker_clicked_wrapper, line))

        return line

    # ========== Marker Drawing ==========

    def prepare_sleep_period_markers(self, period: SleepPeriod, is_main_sleep: bool) -> list[pg.InfiniteLine]:
        """Prepare onset and offset markers for a sleep period (optimized for batch operations)."""
        if not period.is_complete:
            return []

        # Check if this period is currently selected
        selected_period = self.get_selected_marker_period()
        is_selected = period is selected_period

        # Get colors based on selection state
        onset_color, offset_color = self._get_marker_colors(is_selected)

        # Create labels
        if is_main_sleep:
            onset_label = "Main Sleep Onset"
            offset_label = "Main Sleep Offset"
        else:
            nap_number = self.get_nap_number(period)
            onset_label = f"Nap {nap_number} Onset"
            offset_label = f"Nap {nap_number} Offset"

        # Create markers (but don't add to plot yet)
        onset_line = self.create_marker_line_no_add(period.onset_timestamp, onset_color, onset_label, period, "onset", is_selected)
        offset_line = self.create_marker_line_no_add(period.offset_timestamp, offset_color, offset_label, period, "offset", is_selected)

        return [onset_line, offset_line]

    def draw_sleep_period(self, period: SleepPeriod, is_main_sleep: bool) -> None:
        """Draw onset and offset markers for a sleep period."""
        if not period.is_complete:
            return

        # Check if this period is currently selected
        selected_period = self.get_selected_marker_period()
        is_selected = period is selected_period

        # Get colors based on selection state
        onset_color, offset_color = self._get_marker_colors(is_selected)

        # Create labels
        if is_main_sleep:
            onset_label = "Main Sleep Onset"
            offset_label = "Main Sleep Offset"
        else:
            nap_number = self.get_nap_number(period)
            onset_label = f"Nap {nap_number} Onset"
            offset_label = f"Nap {nap_number} Offset"

        # Draw onset marker
        onset_line = self.create_marker_line(period.onset_timestamp, onset_color, onset_label, period, "onset", is_selected)
        self.marker_lines.append(onset_line)

        # Draw offset marker
        offset_line = self.create_marker_line(period.offset_timestamp, offset_color, offset_label, period, "offset", is_selected)
        self.marker_lines.append(offset_line)

    def draw_incomplete_marker(self, period: SleepPeriod) -> None:
        """Draw a temporary marker for an incomplete sleep period."""
        # Use the actual marker type from the period being placed
        if period.marker_type == MarkerType.MAIN_SLEEP:
            label = "Main Sleep Onset?"
        else:
            # For naps, count how many naps are already complete to determine which number this will be
            existing_naps = self.daily_sleep_markers.get_naps()
            complete_naps = [nap for nap in existing_naps if nap.is_complete]
            nap_number = len(complete_naps) + 1  # This will be the next nap
            label = f"Nap {nap_number} Onset?"

        line = self.create_marker_line(
            period.onset_timestamp,
            UIColors.INCOMPLETE_MARKER,  # Gray color for incomplete
            label,
            None,
            "incomplete",
        )
        self.marker_lines.append(line)

    def _get_marker_colors(self, is_selected: bool) -> tuple[str, str]:
        """Get onset and offset colors based on selection state."""
        custom_colors = getattr(self.parent, "custom_colors", {})
        if is_selected:
            onset_color = custom_colors.get("selected_onset", UIColors.SELECTED_MARKER_ONSET)
            offset_color = custom_colors.get("selected_offset", UIColors.SELECTED_MARKER_OFFSET)
        else:
            onset_color = custom_colors.get("unselected_onset", UIColors.UNSELECTED_MARKER_ONSET)
            offset_color = custom_colors.get("unselected_offset", UIColors.UNSELECTED_MARKER_OFFSET)
        return onset_color, offset_color

    # ========== Marker Redrawing ==========

    def redraw_markers(self) -> None:
        """Redraw all sleep markers with proper colors for main sleep vs naps (optimized)."""
        # Batch remove existing visual markers for better performance
        if self.marker_lines:
            for line in self.marker_lines:
                self.parent.plotItem.removeItem(line)
            self.marker_lines.clear()

        # Get all complete periods
        complete_periods = self.daily_sleep_markers.get_complete_periods()
        if not complete_periods:
            # Show incomplete marker being placed
            current_marker = self.parent.current_marker_being_placed
            if current_marker and current_marker.onset_timestamp:
                self.draw_incomplete_marker(current_marker)
            return

        # Batch create markers for better performance
        main_sleep = self.daily_sleep_markers.get_main_sleep()
        markers_to_add = []

        # Prepare all markers first, then add them in batch
        for period in complete_periods:
            is_main_sleep = period is main_sleep
            period_markers = self.prepare_sleep_period_markers(period, is_main_sleep)
            markers_to_add.extend(period_markers)

        # Add all markers in batch
        for marker in markers_to_add:
            self.parent.plotItem.addItem(marker)
            self.marker_lines.append(marker)

        # Show incomplete marker being placed
        current_marker = self.parent.current_marker_being_placed
        if current_marker and current_marker.onset_timestamp:
            self.draw_incomplete_marker(current_marker)

        # Emit signal with new format
        self.parent.sleep_markers_changed.emit(self.daily_sleep_markers)

        # Apply sleep scoring rules for selected marker period
        # BUT skip if we're being called from a context that will apply rules separately
        if not getattr(self.parent, "_skip_auto_apply_rules", False):
            selected_period = self.get_selected_marker_period()
            if selected_period and selected_period.is_complete:
                self.parent.apply_sleep_scoring_rules(selected_period)

        # Ensure visual state is properly updated
        self.update_marker_visual_state()

    def clear_sleep_markers(self) -> None:
        """Clear all sleep markers from the plot."""
        for line in self.marker_lines:
            self.parent.plotItem.removeItem(line)
        self.marker_lines.clear()
        self.daily_sleep_markers = DailySleepMarkers()
        self.parent.markers_saved = False
        self.parent.current_marker_being_placed = None

    # ========== Marker Selection ==========

    def get_selected_marker_period(self) -> SleepPeriod | None:
        """Get the currently selected marker period."""
        if self.selected_marker_set_index == 1:
            return self.daily_sleep_markers.period_1
        if self.selected_marker_set_index == 2:
            return self.daily_sleep_markers.period_2
        if self.selected_marker_set_index == 3:
            return self.daily_sleep_markers.period_3
        if self.selected_marker_set_index == 4:
            return self.daily_sleep_markers.period_4
        return None

    def select_marker_set_by_period(self, period: SleepPeriod) -> None:
        """Select the marker set that contains the given period."""
        old_selection = self.selected_marker_set_index

        # Find which slot this period belongs to
        if period is self.daily_sleep_markers.period_1:
            self.selected_marker_set_index = 1
        elif period is self.daily_sleep_markers.period_2:
            self.selected_marker_set_index = 2
        elif period is self.daily_sleep_markers.period_3:
            self.selected_marker_set_index = 3
        elif period is self.daily_sleep_markers.period_4:
            self.selected_marker_set_index = 4
        else:
            logger.warning("Period not found in daily_sleep_markers - cannot select")
            return

        logger.debug(f"Auto-selected marker set changed from {old_selection} to {self.selected_marker_set_index}")

        # Only update UI if selection actually changed
        if old_selection != self.selected_marker_set_index:
            self.update_marker_visual_state()
            self.parent.sleep_markers_changed.emit(self.daily_sleep_markers)

    def auto_select_marker_set(self) -> None:
        """Automatically select an appropriate marker set when the current one is cleared."""
        # If the current selection is still valid, keep it
        current_period = self.get_selected_marker_period()
        if current_period is not None:
            return

        # Try to select the main sleep period first
        main_sleep = self.daily_sleep_markers.get_main_sleep()
        if main_sleep:
            if main_sleep is self.daily_sleep_markers.period_1:
                self.selected_marker_set_index = 1
            elif main_sleep is self.daily_sleep_markers.period_2:
                self.selected_marker_set_index = 2
            elif main_sleep is self.daily_sleep_markers.period_3:
                self.selected_marker_set_index = 3
            elif main_sleep is self.daily_sleep_markers.period_4:
                self.selected_marker_set_index = 4
        # If no main sleep, select the first available period
        elif self.daily_sleep_markers.period_1:
            self.selected_marker_set_index = 1
        elif self.daily_sleep_markers.period_2:
            self.selected_marker_set_index = 2
        elif self.daily_sleep_markers.period_3:
            self.selected_marker_set_index = 3
        elif self.daily_sleep_markers.period_4:
            self.selected_marker_set_index = 4

        # Update sleep scoring rules for the newly selected period
        self._update_sleep_scoring_rules()

    # ========== Marker Visual State ==========

    def update_marker_visual_state(self) -> None:
        """Update the visual state of all markers to reflect current selection."""
        if not self.marker_lines:
            return

        # Get the currently selected period
        selected_period = self.get_selected_marker_period()

        # If no period is explicitly selected but we have markers, auto-select one
        if selected_period is None and self.daily_sleep_markers.get_complete_periods():
            self.auto_select_marker_set()
            selected_period = self.get_selected_marker_period()

        self._apply_marker_visual_state(selected_period)

    def _update_marker_visual_state_no_auto_select(self) -> None:
        """
        Update the visual state of all markers WITHOUT auto-selecting.

        Use this when intentionally deselecting all sleep markers (e.g., when
        switching to nonwear mode).
        """
        if not self.marker_lines:
            return

        # Get the currently selected period (may be None if index is 0)
        selected_period = self.get_selected_marker_period()
        self._apply_marker_visual_state(selected_period)

    def _apply_marker_visual_state(self, selected_period: SleepPeriod | None) -> None:
        """Apply visual state to all marker lines based on the selected period."""
        for line in self.marker_lines:
            if hasattr(line, "period") and line.period and hasattr(line, "marker_type"):
                is_selected = line.period is selected_period

                # Get colors based on selection state
                custom_colors = getattr(self.parent, "custom_colors", {})
                if is_selected:
                    if line.marker_type == "onset":
                        new_color = custom_colors.get("selected_onset", UIColors.SELECTED_MARKER_ONSET)
                    else:
                        new_color = custom_colors.get("selected_offset", UIColors.SELECTED_MARKER_OFFSET)
                elif line.marker_type == "onset":
                    new_color = custom_colors.get("unselected_onset", UIColors.UNSELECTED_MARKER_ONSET)
                else:
                    new_color = custom_colors.get("unselected_offset", UIColors.UNSELECTED_MARKER_OFFSET)

                # Update line width and color
                line_width = 5 if is_selected else 3
                line.setPen(pg.mkPen(new_color, width=line_width, style=pg.QtCore.Qt.PenStyle.SolidLine))

                # Update flag (label) colors to match
                if hasattr(line, "label") and line.label:
                    line.label.fill = pg.mkBrush(new_color)
                    line.label.border = pg.mkPen(new_color, width=2)
                    line.label.prepareGeometryChange()
                    line.label.update()

    def update_marker_labels_text_only(self) -> None:
        """Update labels for all marker lines based on current classifications (lightweight)."""
        main_sleep = self.daily_sleep_markers.get_main_sleep()

        for line in self.marker_lines:
            if hasattr(line, "period") and line.period and hasattr(line, "marker_type"):
                is_main_sleep = line.period is main_sleep

                # Update label text
                if is_main_sleep:
                    if line.marker_type == "onset":
                        new_label = "Main Sleep Onset"
                    else:
                        new_label = "Main Sleep Offset"
                else:
                    nap_number = self.get_nap_number(line.period)
                    if line.marker_type == "onset":
                        new_label = f"Nap {nap_number} Onset"
                    else:
                        new_label = f"Nap {nap_number} Offset"

                # Update label if changed
                if hasattr(line, "label") and line.label:
                    current_text = line.label.format if hasattr(line.label, "format") else ""
                    if current_text != new_label:
                        line.label.format = new_label
                        line.label.update()

    # ========== Drag Event Handlers ==========

    def _on_marker_drag_finished_wrapper(self, line: pg.InfiniteLine) -> None:
        """Wrapper to handle signal without lambda."""
        self._on_marker_drag_finished(line)

    def _on_marker_dragged_wrapper(self, line: pg.InfiniteLine) -> None:
        """Wrapper to handle signal without lambda."""
        self._on_marker_dragged(line)

    def _on_marker_clicked_wrapper(self, line: pg.InfiniteLine) -> None:
        """Wrapper to handle signal without lambda."""
        self._on_marker_clicked(line)

    def _on_marker_drag_finished(self, line: pg.InfiniteLine) -> None:
        """Handle marker drag completion with snapping."""
        from sleep_scoring_app.core.constants import MarkerCategory

        # Only allow dragging sleep markers when in SLEEP mode
        if self.parent.get_active_marker_category() != MarkerCategory.SLEEP:
            # Revert to original position
            if hasattr(line, "period") and line.period:
                original_pos = line.period.onset_timestamp if line.marker_type == "onset" else line.period.offset_timestamp
                line.setPos(original_pos)
            logger.debug("Reverting sleep marker drag - not in SLEEP mode")
            return

        new_pos = line.getPos()[0]

        # Snap to nearest minute to avoid fractional seconds in database
        snapped_pos = round(new_pos / 60) * 60
        line.setPos(snapped_pos)

        # Update the period with new timestamp
        if hasattr(line, "period") and line.period:
            if line.marker_type == "onset":
                line.period.onset_timestamp = snapped_pos
            elif line.marker_type == "offset":
                line.period.offset_timestamp = snapped_pos

            # Validate period is still valid (onset before offset)
            if line.period.is_complete and line.period.onset_timestamp >= line.period.offset_timestamp:
                # Invalid order - revert change
                if line.marker_type == "onset":
                    line.period.onset_timestamp = line.getPos()[0] + 60
                elif line.marker_type == "offset":
                    line.period.offset_timestamp = line.getPos()[0] - 60
                line.setPos(line.period.onset_timestamp if line.marker_type == "onset" else line.period.offset_timestamp)
                return

            # Update classifications and check for duration ties
            self.daily_sleep_markers.update_classifications()
            if self.daily_sleep_markers.check_duration_tie():
                self.parent.marker_limit_exceeded.emit("Warning: Multiple periods with identical duration detected")

            # Full redraw after drag completion
            self.redraw_markers()

            # Reapply sleep scoring rules if this is the selected period
            if line.period is self.get_selected_marker_period():
                self.parent.apply_sleep_scoring_rules(line.period)

    def _on_marker_dragged(self, line: pg.InfiniteLine) -> None:
        """Handle marker drag in progress (real-time feedback)."""
        from sleep_scoring_app.core.constants import MarkerCategory

        # Only allow dragging sleep markers when in SLEEP mode
        if self.parent.get_active_marker_category() != MarkerCategory.SLEEP:
            return

        new_pos = line.getPos()[0]

        if hasattr(line, "period") and line.period:
            # Auto-select the marker set being dragged
            if line.period is not self.get_selected_marker_period():
                self.select_marker_set_by_period(line.period)

            if line.marker_type == "onset":
                line.period.onset_timestamp = new_pos
            elif line.marker_type == "offset":
                line.period.offset_timestamp = new_pos

            # Update classifications
            self.daily_sleep_markers.update_classifications()

            # Lightweight label updates only during drag
            self.update_marker_labels_text_only()

            # Update sleep scoring rules
            if line.period.is_complete:
                self.parent.apply_sleep_scoring_rules(line.period)

            # Emit signal for UI updates
            self.parent.sleep_markers_changed.emit(self.daily_sleep_markers)

    def _on_marker_clicked(self, line: pg.InfiniteLine) -> None:
        """Handle marker click to select the marker set."""
        logger.debug(f"Marker clicked: {line}")

        from sleep_scoring_app.core.constants import MarkerCategory

        # Only allow interaction with sleep markers when in SLEEP mode
        if self.parent.get_active_marker_category() != MarkerCategory.SLEEP:
            logger.debug("Ignoring sleep marker click - not in SLEEP mode")
            return

        self.parent._marker_click_in_progress = True
        QTimer.singleShot(150, lambda: setattr(self.parent, "_marker_click_in_progress", False))

        if hasattr(line, "period") and line.period:
            old_selection = self.selected_marker_set_index

            self.select_marker_set_by_period(line.period)

            # Deselect nonwear markers when sleep marker is selected
            self._deselect_nonwear_markers()

            # Always update sleep scoring rules when clicking a marker
            self._update_sleep_scoring_rules()

            if old_selection != self.selected_marker_set_index:
                self.parent.sleep_markers_changed.emit(self.daily_sleep_markers)
                self.update_marker_visual_state()
                self.parent.setFocus()

    def _deselect_nonwear_markers(self) -> None:
        """Deselect all nonwear markers (make them all unselected visually)."""
        # Set selected index to 0 (no selection) - this is a special value meaning none selected
        self.selected_nonwear_marker_index = 0
        # Update visual state - all markers will appear unselected
        self._update_nonwear_marker_visual_state_no_auto_select()
        # Emit signal to notify that nonwear selection was cleared
        self.parent.nonwear_marker_selected.emit(None)

    def _update_sleep_scoring_rules(self) -> None:
        """Update sleep scoring rules for the currently selected marker period."""
        selected_period = self.get_selected_marker_period()
        if selected_period and selected_period.is_complete:
            self.parent.apply_sleep_scoring_rules(selected_period)

    # ========== Adjacent Day Markers ==========

    def display_adjacent_day_markers(self, adjacent_day_markers_data: list) -> None:
        """Display adjacent day markers from adjacent days."""
        logger.info(f"ADJACENT DAY MARKERS: display_adjacent_day_markers called with {len(adjacent_day_markers_data)} markers")

        # Clear existing adjacent day markers first
        self.clear_adjacent_day_markers()

        if not hasattr(self.parent, "adjacent_day_marker_lines"):
            self.parent.adjacent_day_marker_lines = []
        if not hasattr(self.parent, "adjacent_day_marker_labels"):
            self.parent.adjacent_day_marker_labels = []

        for i, marker_data in enumerate(adjacent_day_markers_data):
            logger.info(f"ADJACENT DAY MARKERS: Processing marker {i}: {marker_data}")

            onset_time = marker_data.get("onset_datetime")
            offset_time = marker_data.get("offset_datetime")
            adjacent_date = marker_data.get("adjacent_date", "")

            logger.info(f"ADJACENT DAY MARKERS: Marker {i} - onset: {onset_time}, offset: {offset_time}, date: {adjacent_date}")

            # Create adjacent day onset marker if exists
            if onset_time:
                onset_line = pg.InfiniteLine(
                    pos=onset_time,
                    angle=90,
                    pen=pg.mkPen(
                        color="#000000",
                        width=3,
                        style=Qt.PenStyle.DashLine,
                    ),
                    movable=False,
                )
                onset_line.setOpacity(0.4)
                self.parent.plotItem.addItem(onset_line)
                self.parent.adjacent_day_marker_lines.append(onset_line)

                # Add date label for onset
                onset_label = pg.TextItem(
                    text=f"{adjacent_date} Onset",
                    color="#000000",
                    anchor=(0.5, 0),
                )
                y_range = self.parent.plotItem.getViewBox().viewRange()[1]
                onset_label.setPos(onset_time, y_range[1] * 0.9)
                self.parent.plotItem.addItem(onset_label)
                self.parent.adjacent_day_marker_labels.append(onset_label)

            # Create adjacent day offset marker if exists
            if offset_time:
                offset_line = pg.InfiniteLine(
                    pos=offset_time,
                    angle=90,
                    pen=pg.mkPen(
                        color="#000000",
                        width=3,
                        style=Qt.PenStyle.DashLine,
                    ),
                    movable=False,
                )
                offset_line.setOpacity(0.4)
                self.parent.plotItem.addItem(offset_line)
                self.parent.adjacent_day_marker_lines.append(offset_line)

                # Add date label for offset
                offset_label = pg.TextItem(
                    text=f"{adjacent_date} Offset",
                    color="#000000",
                    anchor=(0.5, 0),
                )
                y_range = self.parent.plotItem.getViewBox().viewRange()[1]
                offset_label.setPos(offset_time, y_range[1] * 0.85)
                self.parent.plotItem.addItem(offset_label)
                self.parent.adjacent_day_marker_labels.append(offset_label)

    def clear_adjacent_day_markers(self) -> None:
        """Clear all adjacent day markers from the plot."""
        if hasattr(self.parent, "adjacent_day_marker_lines"):
            for line in self.parent.adjacent_day_marker_lines:
                self.parent.plotItem.removeItem(line)
            self.parent.adjacent_day_marker_lines.clear()

        if hasattr(self.parent, "adjacent_day_marker_labels"):
            for label in self.parent.adjacent_day_marker_labels:
                self.parent.plotItem.removeItem(label)
            self.parent.adjacent_day_marker_labels.clear()

    # ========== Marker Loading ==========

    def _validate_sleep_period_bounds(self, period: SleepPeriod | None) -> bool:
        """
        Check if a sleep period's timestamps are within data bounds.

        Returns True if period is valid (within bounds or None), False if out of bounds.
        """
        if period is None:
            return True

        data_start = self.parent.data_start_time
        data_end = self.parent.data_end_time

        if data_start is None or data_end is None:
            return True  # No bounds to check against

        # Check onset
        if period.onset_timestamp is not None:
            if not (data_start <= period.onset_timestamp <= data_end):
                logger.warning(f"Sleep period onset {period.onset_timestamp} outside data bounds [{data_start}, {data_end}]")
                return False

        # Check offset
        if period.offset_timestamp is not None:
            if not (data_start <= period.offset_timestamp <= data_end):
                logger.warning(f"Sleep period offset {period.offset_timestamp} outside data bounds [{data_start}, {data_end}]")
                return False

        return True

    def _filter_out_of_bounds_sleep_markers(self, daily_markers: DailySleepMarkers) -> int:
        """
        Remove sleep periods that are outside the current data bounds.

        Returns the count of periods that were removed.
        """
        removed_count = 0

        for i in range(1, 5):  # Check periods 1-4
            period = daily_markers.get_period_by_slot(i)
            if period and not self._validate_sleep_period_bounds(period):
                daily_markers.set_period_by_slot(i, None)
                removed_count += 1

        if removed_count > 0:
            daily_markers.update_classifications()

        return removed_count

    def load_daily_sleep_markers(self, daily_markers: DailySleepMarkers, markers_saved: bool = True) -> None:
        """Load existing daily sleep markers into the plot widget."""
        # Filter out any periods that are outside data bounds
        removed_count = self._filter_out_of_bounds_sleep_markers(daily_markers)
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} sleep period(s) outside data bounds")
            self.parent.marker_limit_exceeded.emit(f"Warning: {removed_count} sleep period(s) were outside the data range and have been removed")

        self.daily_sleep_markers = daily_markers
        self.parent.current_marker_being_placed = None
        self.parent.markers_saved = markers_saved
        self.redraw_markers()

        # Auto-select an appropriate marker set when loading
        self.auto_select_marker_set()

        # Ensure visual state is properly updated
        self.update_marker_visual_state()

        # Extract view subset from main Sadeh results before applying rules
        if hasattr(self.parent, "main_48h_sadeh_results") and self.parent.main_48h_sadeh_results:
            self.parent._extract_view_subset_from_main_results()

        # Always update sleep scoring rules after loading markers
        self._update_sleep_scoring_rules()

    def get_daily_sleep_markers(self) -> DailySleepMarkers:
        """Get the current daily sleep markers."""
        return self.daily_sleep_markers

    # ========== Marker Period Operations ==========

    def remove_sleep_period(self, period_index: int) -> bool:
        """Remove a sleep period by its index (1, 2, 3, or 4)."""
        try:
            if period_index == 1 and self.daily_sleep_markers.period_1:
                self.daily_sleep_markers.period_1 = None
            elif period_index == 2 and self.daily_sleep_markers.period_2:
                self.daily_sleep_markers.period_2 = None
            elif period_index == 3 and self.daily_sleep_markers.period_3:
                self.daily_sleep_markers.period_3 = None
            elif period_index == 4 and self.daily_sleep_markers.period_4:
                self.daily_sleep_markers.period_4 = None
            else:
                return False

            self.daily_sleep_markers.update_classifications()
            self.redraw_markers()
            self.parent.sleep_markers_changed.emit(self.daily_sleep_markers)
            return True

        except Exception:
            logger.exception("Error removing sleep period %d", period_index)
            return False

    def clear_selected_marker_set(self) -> None:
        """Clear the currently selected marker set."""
        logger.debug(f"Clearing selected marker set {self.selected_marker_set_index}")

        selected_period = self.get_selected_marker_period()

        if selected_period is None:
            logger.debug("No selected period to clear - trying to clear any existing markers")
            if self.marker_lines:
                logger.debug(f"Found {len(self.marker_lines)} marker lines to clear")
                for line in self.marker_lines:
                    self.parent.plotItem.removeItem(line)
                self.marker_lines.clear()

                self.daily_sleep_markers = DailySleepMarkers()
                self.parent.markers_saved = False
                self.parent.sleep_markers_changed.emit(self.daily_sleep_markers)
                self.parent.clear_sleep_onset_offset_markers()
            return

        # Remove visual markers for this period
        lines_to_remove = [line for line in self.marker_lines if line.period == selected_period]
        for line in lines_to_remove:
            self.parent.plotItem.removeItem(line)
        self.parent.marker_lines = [line for line in self.marker_lines if line.period != selected_period]

        # Clear the period from daily_sleep_markers
        if self.selected_marker_set_index == 1:
            self.daily_sleep_markers.period_1 = None
        elif self.selected_marker_set_index == 2:
            self.daily_sleep_markers.period_2 = None
        elif self.selected_marker_set_index == 3:
            self.daily_sleep_markers.period_3 = None
        elif self.selected_marker_set_index == 4:
            self.daily_sleep_markers.period_4 = None

        self.daily_sleep_markers.update_classifications()
        self.redraw_markers()
        self.parent.markers_saved = False
        self.parent.sleep_markers_changed.emit(self.daily_sleep_markers)
        self.parent.clear_sleep_onset_offset_markers()
        self.auto_select_marker_set()
        self.update_marker_visual_state()

    def cancel_incomplete_marker(self) -> None:
        """Cancel the current incomplete marker placement and remove its visual indicator."""
        if self.parent.current_marker_being_placed is not None:
            logger.debug("Cancelling incomplete marker placement")
            self.parent.current_marker_being_placed = None
            self.redraw_markers()
            logger.debug("Incomplete marker cancelled")

    def adjust_selected_marker(self, marker_type: str, seconds_delta: int) -> None:
        """Adjust selected marker set by specified number of seconds."""
        selected_period = self.get_selected_marker_period()
        if not selected_period or not selected_period.is_complete:
            return

        # Get current timestamp
        if marker_type == "onset":
            current_timestamp = selected_period.onset_timestamp
        elif marker_type == "offset":
            current_timestamp = selected_period.offset_timestamp
        else:
            return

        # Calculate new timestamp
        new_timestamp = current_timestamp + seconds_delta

        # Ensure timestamp is within data bounds
        if not (self.parent.data_start_time <= new_timestamp <= self.parent.data_end_time):
            return

        # Update the timestamp
        if marker_type == "onset":
            if new_timestamp < selected_period.offset_timestamp:
                selected_period.onset_timestamp = new_timestamp
            else:
                return
        elif marker_type == "offset":
            if new_timestamp > selected_period.onset_timestamp:
                selected_period.offset_timestamp = new_timestamp
            else:
                return

        self.daily_sleep_markers.update_classifications()
        self.redraw_markers()
        self.parent.markers_saved = False
        self.parent.sleep_markers_changed.emit(self.daily_sleep_markers)
        self._update_sleep_scoring_rules()
        self.update_marker_visual_state()

    # =========================================================================
    # MANUAL NONWEAR MARKER METHODS
    # =========================================================================

    def create_nonwear_marker_line(
        self,
        timestamp: float,
        color: str,
        label: str,
        period: ManualNonwearPeriod | None,
        marker_type: str,
        is_selected: bool = False,
    ) -> pg.InfiniteLine:
        """Create a dashed marker line for manual nonwear periods."""
        line = self._create_nonwear_marker_line_internal(timestamp, color, label, period, marker_type, is_selected)
        self.parent.plotItem.addItem(line)
        return line

    def _create_nonwear_marker_line_internal(
        self,
        timestamp: float,
        color: str,
        label: str,
        period: ManualNonwearPeriod | None,
        marker_type: str,
        is_selected: bool = False,
    ) -> pg.InfiniteLine:
        """Internal method to create nonwear marker line with dashed style."""
        # Use thicker line for selected markers
        line_width = 4 if is_selected else 2

        # Create dashed line to distinguish from sleep markers
        line = pg.InfiniteLine(
            pos=timestamp,
            angle=90,  # Vertical line
            pen=pg.mkPen(color, width=line_width, style=Qt.PenStyle.DashLine),
            movable=(marker_type != "incomplete"),
            bounds=[self.parent.data_start_time, self.parent.data_end_time],
            label=label,
            labelOpts={
                "position": 0.3,  # Position label lower to avoid overlap with sleep markers
                "color": (255, 255, 255),
                "fill": pg.mkBrush(color),
                "border": pg.mkPen(color, width=2),
                "rotateAxis": (1, 0),
            },
        )

        # Set hover color
        line.setHoverPen(pg.mkPen(UIColors.HOVERED_MARKER, width=line_width + 1, style=Qt.PenStyle.DashLine))

        # Connect drag events for complete markers
        if marker_type != "incomplete":
            line.period = period
            line.marker_type = marker_type
            line.marker_category = MarkerCategory.NONWEAR

            line.sigPositionChangeFinished.connect(partial(self._on_nonwear_marker_drag_finished_wrapper, line))
            line.sigPositionChanged.connect(partial(self._on_nonwear_marker_dragged_wrapper, line))
            line.sigClicked.connect(partial(self._on_nonwear_marker_clicked_wrapper, line))

        return line

    def _get_nonwear_marker_colors(self, is_selected: bool) -> tuple[str, str]:
        """Get start and end colors for nonwear markers based on selection state."""
        custom_colors = getattr(self.parent, "custom_colors", {})
        if is_selected:
            start_color = custom_colors.get("selected_manual_nwt_start", UIColors.SELECTED_MANUAL_NWT_START)
            end_color = custom_colors.get("selected_manual_nwt_end", UIColors.SELECTED_MANUAL_NWT_END)
        else:
            start_color = custom_colors.get("unselected_manual_nwt_start", UIColors.UNSELECTED_MANUAL_NWT_START)
            end_color = custom_colors.get("unselected_manual_nwt_end", UIColors.UNSELECTED_MANUAL_NWT_END)
        return start_color, end_color

    def draw_nonwear_period(self, period: ManualNonwearPeriod, is_selected: bool) -> None:
        """Draw start and end markers for a nonwear period."""
        if not period.is_complete:
            return

        start_color, end_color = self._get_nonwear_marker_colors(is_selected)

        # Create labels
        start_label = f"NW {period.marker_index} Start"
        end_label = f"NW {period.marker_index} End"

        # Draw start marker
        start_line = self.create_nonwear_marker_line(period.start_timestamp, start_color, start_label, period, "start", is_selected)
        self.nonwear_marker_lines.append(start_line)

        # Draw end marker
        end_line = self.create_nonwear_marker_line(period.end_timestamp, end_color, end_label, period, "end", is_selected)
        self.nonwear_marker_lines.append(end_line)

    def draw_incomplete_nonwear_marker(self, period: ManualNonwearPeriod) -> None:
        """Draw a temporary marker for an incomplete nonwear period."""
        label = f"NW {period.marker_index} Start?"

        line = self.create_nonwear_marker_line(
            period.start_timestamp,
            UIColors.INCOMPLETE_MANUAL_NWT,
            label,
            None,
            "incomplete",
        )
        self.nonwear_marker_lines.append(line)

    def redraw_nonwear_markers(self) -> None:
        """Redraw all manual nonwear markers."""
        # Remove existing nonwear marker lines
        for line in self.nonwear_marker_lines:
            self.parent.plotItem.removeItem(line)
        self.nonwear_marker_lines.clear()

        # Don't draw if visibility is off
        if not self.nonwear_markers_visible:
            return

        # Get all complete periods
        complete_periods = self.daily_nonwear_markers.get_complete_periods()

        # Draw each complete period
        for period in complete_periods:
            is_selected = period.marker_index == self.selected_nonwear_marker_index
            self.draw_nonwear_period(period, is_selected)

        # Draw incomplete marker being placed
        current_nonwear_marker = getattr(self.parent, "_current_nonwear_marker_being_placed", None)
        if current_nonwear_marker and current_nonwear_marker.start_timestamp:
            self.draw_incomplete_nonwear_marker(current_nonwear_marker)

    def clear_nonwear_markers(self) -> None:
        """Clear all manual nonwear markers from the plot."""
        for line in self.nonwear_marker_lines:
            self.parent.plotItem.removeItem(line)
        self.nonwear_marker_lines.clear()
        self.daily_nonwear_markers = DailyNonwearMarkers()
        self.parent._current_nonwear_marker_being_placed = None

    def get_selected_nonwear_period(self) -> ManualNonwearPeriod | None:
        """Get the currently selected nonwear period."""
        return self.daily_nonwear_markers.get_period_by_slot(self.selected_nonwear_marker_index)

    def select_nonwear_marker_by_period(self, period: ManualNonwearPeriod) -> None:
        """Select the nonwear marker set that contains the given period."""
        old_selection = self.selected_nonwear_marker_index
        self.selected_nonwear_marker_index = period.marker_index

        if old_selection != self.selected_nonwear_marker_index:
            logger.debug(f"Nonwear marker selection changed from {old_selection} to {self.selected_nonwear_marker_index}")
            self.update_nonwear_marker_visual_state()

    def update_nonwear_marker_visual_state(self) -> None:
        """Update the visual state of all nonwear markers to reflect current selection."""
        self._apply_nonwear_marker_visual_state()

    def _update_nonwear_marker_visual_state_no_auto_select(self) -> None:
        """
        Update the visual state of all nonwear markers WITHOUT auto-selecting.

        This is the same as update_nonwear_marker_visual_state since nonwear markers
        don't have auto-selection, but provided for API consistency with sleep markers.
        """
        self._apply_nonwear_marker_visual_state()

    def _apply_nonwear_marker_visual_state(self) -> None:
        """Apply visual state to all nonwear marker lines based on current selection."""
        if not self.nonwear_marker_lines:
            return

        for line in self.nonwear_marker_lines:
            if hasattr(line, "period") and line.period and hasattr(line, "marker_type"):
                is_selected = line.period.marker_index == self.selected_nonwear_marker_index

                start_color, end_color = self._get_nonwear_marker_colors(is_selected)
                if line.marker_type == "start":
                    new_color = start_color
                else:
                    new_color = end_color

                line_width = 4 if is_selected else 2
                line.setPen(pg.mkPen(new_color, width=line_width, style=Qt.PenStyle.DashLine))

                # Update label colors
                if hasattr(line, "label") and line.label:
                    line.label.fill = pg.mkBrush(new_color)
                    line.label.border = pg.mkPen(new_color, width=2)
                    line.label.prepareGeometryChange()
                    line.label.update()

    def set_nonwear_markers_visibility(self, visible: bool) -> None:
        """Set visibility of manual nonwear markers."""
        self.nonwear_markers_visible = visible
        self.redraw_nonwear_markers()

    # ========== Nonwear Marker Drag Handlers ==========

    def _on_nonwear_marker_drag_finished_wrapper(self, line: pg.InfiniteLine) -> None:
        """Wrapper to handle signal without lambda."""
        self._on_nonwear_marker_drag_finished(line)

    def _on_nonwear_marker_dragged_wrapper(self, line: pg.InfiniteLine) -> None:
        """Wrapper to handle signal without lambda."""
        self._on_nonwear_marker_dragged(line)

    def _on_nonwear_marker_clicked_wrapper(self, line: pg.InfiniteLine) -> None:
        """Wrapper to handle signal without lambda."""
        self._on_nonwear_marker_clicked(line)

    def _on_nonwear_marker_drag_finished(self, line: pg.InfiniteLine) -> None:
        """Handle nonwear marker drag completion with snapping."""
        from sleep_scoring_app.core.constants import MarkerCategory

        # Only allow dragging nonwear markers when in NONWEAR mode
        if self.parent.get_active_marker_category() != MarkerCategory.NONWEAR:
            # Revert to original position
            if hasattr(line, "period") and line.period:
                original_pos = line.period.start_timestamp if line.marker_type == "start" else line.period.end_timestamp
                line.setPos(original_pos)
            logger.debug("Reverting nonwear marker drag - not in NONWEAR mode")
            return

        new_pos = line.getPos()[0]

        # Snap to nearest minute
        snapped_pos = round(new_pos / 60) * 60
        line.setPos(snapped_pos)

        if hasattr(line, "period") and line.period:
            # Store original values for potential revert
            original_start = line.period.start_timestamp
            original_end = line.period.end_timestamp

            if line.marker_type == "start":
                line.period.start_timestamp = snapped_pos
            elif line.marker_type == "end":
                line.period.end_timestamp = snapped_pos

            # Validate period (start before end)
            if line.period.is_complete and line.period.start_timestamp >= line.period.end_timestamp:
                # Invalid order - revert
                line.period.start_timestamp = original_start
                line.period.end_timestamp = original_end
                line.setPos(original_start if line.marker_type == "start" else original_end)
                return

            # Validate no overlap with other periods
            if line.period.is_complete and self.daily_nonwear_markers.check_overlap(
                line.period.start_timestamp,
                line.period.end_timestamp,
                exclude_slot=line.period.marker_index,
            ):
                # Overlap detected - revert and notify user
                line.period.start_timestamp = original_start
                line.period.end_timestamp = original_end
                line.setPos(original_start if line.marker_type == "start" else original_end)
                self.parent.marker_limit_exceeded.emit("Nonwear periods cannot overlap")
                return

            # Full redraw after drag completion
            self.redraw_nonwear_markers()

            # Mark as unsaved
            if hasattr(self.parent, "_nonwear_markers_saved"):
                self.parent._nonwear_markers_saved = False

            # Emit signals for UI updates
            self.parent.nonwear_markers_changed.emit(self.daily_nonwear_markers)
            self.parent.nonwear_marker_selected.emit(line.period)

    def _on_nonwear_marker_dragged(self, line: pg.InfiniteLine) -> None:
        """Handle nonwear marker drag in progress."""
        from sleep_scoring_app.core.constants import MarkerCategory

        # Only allow dragging nonwear markers when in NONWEAR mode
        if self.parent.get_active_marker_category() != MarkerCategory.NONWEAR:
            return

        new_pos = line.getPos()[0]

        if hasattr(line, "period") and line.period:
            # Auto-select the marker being dragged
            if line.period.marker_index != self.selected_nonwear_marker_index:
                self.select_nonwear_marker_by_period(line.period)
                # Also deselect sleep markers when dragging nonwear
                self._deselect_sleep_markers()

            if line.marker_type == "start":
                line.period.start_timestamp = new_pos
            elif line.marker_type == "end":
                line.period.end_timestamp = new_pos

            # Emit signal to update tables during drag
            self.parent.nonwear_marker_selected.emit(line.period)

    def _on_nonwear_marker_clicked(self, line: pg.InfiniteLine) -> None:
        """Handle nonwear marker click to select."""
        logger.debug(f"Nonwear marker clicked: {line}")

        from sleep_scoring_app.core.constants import MarkerCategory

        # Only allow interaction with nonwear markers when in NONWEAR mode
        if self.parent.get_active_marker_category() != MarkerCategory.NONWEAR:
            logger.debug("Ignoring nonwear marker click - not in NONWEAR mode")
            return

        self.parent._marker_click_in_progress = True
        QTimer.singleShot(150, lambda: setattr(self.parent, "_marker_click_in_progress", False))

        if hasattr(line, "period") and line.period:
            self.select_nonwear_marker_by_period(line.period)
            self.update_nonwear_marker_visual_state()

            # Deselect sleep markers when nonwear marker is selected
            self._deselect_sleep_markers()

            # Emit signal for table updates with the selected nonwear period
            self.parent.nonwear_marker_selected.emit(line.period)

            self.parent.setFocus()

    def _deselect_sleep_markers(self) -> None:
        """Deselect all sleep markers (make them all unselected visually)."""
        # Set selected index to 0 (no selection) - this is a special value meaning none selected
        self.selected_marker_set_index = 0
        # Use the no-auto-select version to prevent re-selection
        self._update_marker_visual_state_no_auto_select()

    # ========== Nonwear Marker Period Operations ==========

    def clear_selected_nonwear_marker(self) -> None:
        """Clear the currently selected nonwear marker."""
        selected_period = self.get_selected_nonwear_period()
        if selected_period is None:
            return

        # Remove from data structure
        self.daily_nonwear_markers.remove_period_by_slot(self.selected_nonwear_marker_index)

        # Redraw
        self.redraw_nonwear_markers()

        # Mark as unsaved
        if hasattr(self.parent, "_nonwear_markers_saved"):
            self.parent._nonwear_markers_saved = False

        # Auto-select next available
        self._auto_select_next_nonwear_marker()

    def _auto_select_next_nonwear_marker(self) -> None:
        """Automatically select the next available nonwear marker."""
        complete_periods = self.daily_nonwear_markers.get_complete_periods()
        if complete_periods:
            self.selected_nonwear_marker_index = complete_periods[0].marker_index
        else:
            self.selected_nonwear_marker_index = 1

    def adjust_selected_nonwear_marker(self, marker_type: str, seconds_delta: int) -> None:
        """Adjust selected nonwear marker by specified number of seconds."""
        selected_period = self.get_selected_nonwear_period()
        if not selected_period or not selected_period.is_complete:
            return

        # Get current timestamp
        if marker_type == "start":
            current_timestamp = selected_period.start_timestamp
        elif marker_type == "end":
            current_timestamp = selected_period.end_timestamp
        else:
            return

        # Calculate new timestamp
        new_timestamp = current_timestamp + seconds_delta

        # Ensure timestamp is within data bounds
        if not (self.parent.data_start_time <= new_timestamp <= self.parent.data_end_time):
            return

        # CRITICAL FIX #2: Store original values for potential revert on overlap detection
        original_start = selected_period.start_timestamp
        original_end = selected_period.end_timestamp

        # Update the timestamp
        if marker_type == "start":
            if new_timestamp < selected_period.end_timestamp:
                selected_period.start_timestamp = new_timestamp
            else:
                return
        elif marker_type == "end":
            if new_timestamp > selected_period.start_timestamp:
                selected_period.end_timestamp = new_timestamp
            else:
                return

        # CRITICAL FIX #2: Validate no overlap with other periods
        if self.daily_nonwear_markers.check_overlap(
            selected_period.start_timestamp,
            selected_period.end_timestamp,
            exclude_slot=selected_period.marker_index,
        ):
            # Overlap detected - revert and notify user
            selected_period.start_timestamp = original_start
            selected_period.end_timestamp = original_end
            self.parent.marker_limit_exceeded.emit("Nonwear periods cannot overlap")
            return

        self.redraw_nonwear_markers()

        if hasattr(self.parent, "_nonwear_markers_saved"):
            self.parent._nonwear_markers_saved = False

    def _validate_nonwear_period_bounds(self, period: ManualNonwearPeriod | None) -> bool:
        """
        Check if a nonwear period's timestamps are within data bounds.

        Returns True if period is valid (within bounds or None), False if out of bounds.
        """
        if period is None:
            return True

        data_start = self.parent.data_start_time
        data_end = self.parent.data_end_time

        if data_start is None or data_end is None:
            return True  # No bounds to check against

        # Check start
        if period.start_timestamp is not None:
            if not (data_start <= period.start_timestamp <= data_end):
                logger.warning(f"Nonwear period start {period.start_timestamp} outside data bounds [{data_start}, {data_end}]")
                return False

        # Check end
        if period.end_timestamp is not None:
            if not (data_start <= period.end_timestamp <= data_end):
                logger.warning(f"Nonwear period end {period.end_timestamp} outside data bounds [{data_start}, {data_end}]")
                return False

        return True

    def _filter_out_of_bounds_nonwear_markers(self, daily_markers: DailyNonwearMarkers) -> int:
        """
        Remove nonwear periods that are outside the current data bounds.

        Returns the count of periods that were removed.
        """
        removed_count = 0

        for i in range(1, 11):  # Check periods 1-10
            period = daily_markers.get_period_by_slot(i)
            if period and not self._validate_nonwear_period_bounds(period):
                daily_markers.remove_period_by_slot(i)
                removed_count += 1

        return removed_count

    def load_daily_nonwear_markers(self, daily_markers: DailyNonwearMarkers, markers_saved: bool = True) -> None:
        """Load existing daily nonwear markers into the plot widget."""
        # Filter out any periods that are outside data bounds
        removed_count = self._filter_out_of_bounds_nonwear_markers(daily_markers)
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} nonwear period(s) outside data bounds")
            self.parent.marker_limit_exceeded.emit(f"Warning: {removed_count} nonwear period(s) were outside the data range and have been removed")

        self.daily_nonwear_markers = daily_markers
        self.parent._current_nonwear_marker_being_placed = None
        self.parent._nonwear_markers_saved = markers_saved
        self.redraw_nonwear_markers()

        # Auto-select first available
        self._auto_select_next_nonwear_marker()
        self.update_nonwear_marker_visual_state()

    def get_daily_nonwear_markers(self) -> DailyNonwearMarkers:
        """Get the current daily nonwear markers."""
        return self.daily_nonwear_markers

    def cancel_incomplete_nonwear_marker(self) -> None:
        """Cancel the current incomplete nonwear marker placement."""
        if hasattr(self.parent, "_current_nonwear_marker_being_placed"):
            if self.parent._current_nonwear_marker_being_placed is not None:
                logger.debug("Cancelling incomplete nonwear marker placement")
                self.parent._current_nonwear_marker_being_placed = None
                self.redraw_nonwear_markers()
