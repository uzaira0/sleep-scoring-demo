#!/usr/bin/env python3
"""
Dialog managers for Analysis Tab.

Handles keyboard shortcuts and color settings dialogs.
Extracted from analysis_tab.py to reduce god-class complexity.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sleep_scoring_app.core.constants import UIColors

if TYPE_CHECKING:
    from sleep_scoring_app.ui.analysis_tab import AnalysisTab


class AnalysisDialogManager:
    """
    Manages dialogs for the Analysis Tab.

    This class handles the keyboard shortcuts dialog and color settings dialog,
    including color picking, resetting, and applying color changes.
    """

    def __init__(self, parent: AnalysisTab) -> None:
        """
        Initialize dialog manager.

        Args:
            parent: The AnalysisTab instance

        """
        self.parent = parent
        self.color_widgets: dict[str, tuple[QPushButton, str]] = {}

    def show_shortcuts_dialog(self) -> None:
        """Show keyboard shortcuts dialog."""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.setModal(True)
        dialog.resize(450, 300)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        # Title
        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #343a40; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Plot shortcuts section
        plot_section = QFrame()
        plot_section.setStyleSheet("QFrame { border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; }")
        plot_layout = QVBoxLayout(plot_section)

        plot_title = QLabel("Plot Navigation & Marker Control")
        plot_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #495057; margin-bottom: 8px;")
        plot_layout.addWidget(plot_title)

        shortcuts = [
            ("Click", "Place sleep markers on the plot"),
            ("Mouse Wheel", "Zoom in/out"),
            ("Drag", "Pan horizontally"),
            ("C or Delete", "Clear selected marker set or cancel incomplete marker"),
            ("Q", "Move sleep onset left (1 minute)"),
            ("E", "Move sleep onset right (1 minute)"),
            ("A", "Move sleep offset left (1 minute)"),
            ("D", "Move sleep offset right (1 minute)"),
        ]

        for key, description in shortcuts:
            shortcut_layout = QHBoxLayout()

            key_label = QLabel(key)
            key_label.setStyleSheet("""
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 3px;
                padding: 2px 8px;
                font-family: monospace;
                font-weight: bold;
                min-width: 80px;
            """)
            key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            key_label.setMaximumWidth(100)

            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #6c757d; font-size: 12px;")

            shortcut_layout.addWidget(key_label)
            shortcut_layout.addWidget(desc_label, stretch=1)

            plot_layout.addLayout(shortcut_layout)

        layout.addWidget(plot_section)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0056b3;
            }}
            QPushButton:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
            }}
        """)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        dialog.exec()

    def show_color_legend_dialog(self) -> None:
        """Show color legend dialog with color picker functionality."""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Color Settings")
        dialog.setModal(True)
        dialog.resize(600, 850)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        # Title
        title = QLabel("Color Settings & Legend")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #343a40; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Store color widgets for reset functionality
        self.color_widgets = {}

        # Load saved colors from settings
        settings = QSettings("SleepScoring", "ColorSettings")

        # Create scroll area for the legend items
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Sleep Markers Section
        markers_section = QFrame()
        markers_section.setStyleSheet("QFrame { border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; }")
        markers_layout = QVBoxLayout(markers_section)

        markers_title = QLabel("Sleep Markers")
        markers_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #495057; margin-bottom: 8px;")
        markers_layout.addWidget(markers_title)

        # Define color items with actual colors from constants
        marker_items = [
            ("Sleep Onset Marker", "#0080FF", "Vertical line marking sleep start", "onset_marker"),
            ("Sleep Offset Marker", "#FF8000", "Vertical line marking sleep end", "offset_marker"),
            ("Sleep Onset Arrow", "#0066CC", "Arrow showing adjusted sleep onset from 3-minute rule", "onset_arrow"),
            ("Sleep Offset Arrow", "#FFA500", "Arrow showing adjusted sleep offset from 5-minute rule", "offset_arrow"),
        ]

        for name, default_color, description, key in marker_items:
            self._add_color_item(markers_layout, name, default_color, description, key, settings)

        scroll_layout.addWidget(markers_section)

        # Nonwear Regions Section
        nonwear_section = QFrame()
        nonwear_section.setStyleSheet("QFrame { border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; }")
        nonwear_layout = QVBoxLayout(nonwear_section)

        nonwear_title = QLabel("Nonwear Detection Regions")
        nonwear_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #495057; margin-bottom: 8px;")
        nonwear_layout.addWidget(nonwear_title)

        nonwear_items = [
            ("Sensor Nonwear", "rgba(255,215,0,60)", "Device sensor detected nonwear", "sensor_nonwear"),
            ("Choi Algorithm", "rgba(147,112,219,60)", "Choi algorithm detected nonwear", "choi_nonwear"),
            ("Overlap", "rgba(65,105,225,60)", "Both sensor and Choi detected nonwear", "overlap_nonwear"),
        ]

        for name, default_color, description, key in nonwear_items:
            self._add_color_item(nonwear_layout, name, default_color, description, key, settings)

        scroll_layout.addWidget(nonwear_section)

        # Side Tables Section
        tables_section = QFrame()
        tables_section.setStyleSheet("QFrame { border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; }")
        tables_layout = QVBoxLayout(tables_section)

        tables_title = QLabel("Side Tables")
        tables_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #495057; margin-bottom: 8px;")
        tables_layout.addWidget(tables_title)

        table_items = [
            ("Onset Table Row", "#87CEEB", "Current sleep onset marker position", "onset_table"),
            ("Offset Table Row", "#FFDAB9", "Current sleep offset marker position", "offset_table"),
        ]

        for name, default_color, description, key in table_items:
            self._add_color_item(tables_layout, name, default_color, description, key, settings)

        scroll_layout.addWidget(tables_section)

        # Instructions
        instructions = QLabel("Click any color box to customize the color")
        instructions.setStyleSheet("font-style: italic; color: #6c757d; margin-top: 10px;")
        scroll_layout.addWidget(instructions)

        # Set scroll widget
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # Button layout
        button_layout = QHBoxLayout()

        # Reset to defaults button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(lambda: self._reset_colors_to_defaults(settings))
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px;
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
            QPushButton:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
            }}
        """)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0056b3;
            }}
            QPushButton:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
            }}
        """)

        button_layout.addWidget(reset_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def _add_color_item(
        self,
        layout: QVBoxLayout,
        name: str,
        default_color: str,
        description: str,
        key: str,
        settings: QSettings,
    ) -> None:
        """Add a color item row to the layout."""
        item_layout = QHBoxLayout()

        # Load saved color or use default
        saved_color = settings.value(f"colors/{key}", default_color)

        # Color box (clickable)
        color_box = QPushButton()
        is_nonwear = "nonwear" in key
        color_box.setStyleSheet(f"""
            QPushButton {{
                background-color: {saved_color};
                border: 1px solid {"#666" if is_nonwear else "#000"};
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #0066CC;
            }}
        """)
        color_box.setFixedSize(40, 25)

        # Store widget and default color
        self.color_widgets[key] = (color_box, default_color)

        # Connect color picker
        color_box.clicked.connect(lambda checked, cb=color_box, k=key: self._pick_color(cb, k, settings))

        # Text
        text_label = QLabel(f"<b>{name}:</b> {description}")
        text_label.setWordWrap(True)
        text_label.setStyleSheet("font-size: 12px;")

        item_layout.addWidget(color_box)
        item_layout.addWidget(text_label, stretch=1)
        layout.addLayout(item_layout)

    def _pick_color(self, color_box: QPushButton, key: str, settings: QSettings) -> None:
        """Open color picker dialog for the given color box."""
        # Get current color from the button
        current_style = color_box.styleSheet()

        color_match = re.search(r"background-color:\s*([^;]+)", current_style)
        if color_match:
            current_color_str = color_match.group(1).strip()
            current_color = QColor(current_color_str)
        else:
            current_color = QColor("#FFFFFF")

        # Open color dialog
        color = QColorDialog.getColor(current_color, self.parent, f"Choose Color for {key}")

        if color.isValid():
            # Update the button color
            color_str = color.name()
            if "nonwear" in key:
                # Add transparency for nonwear colors
                color_str = f"rgba({color.red()},{color.green()},{color.blue()},60)"

            color_box.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_str};
                    border: 1px solid {"#666" if "nonwear" in key else "#000"};
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    border: 2px solid #0066CC;
                }}
            """)

            # Save to settings
            settings.setValue(f"colors/{key}", color_str)
            settings.sync()

            # Apply the color changes immediately
            self.apply_colors()

    def _reset_colors_to_defaults(self, settings: QSettings) -> None:
        """Reset all colors to their default values."""
        # Clear all saved colors
        settings.beginGroup("colors")
        settings.remove("")  # Remove all keys in the group
        settings.endGroup()
        settings.sync()

        # Update all color boxes to defaults
        for key, (color_box, default_color) in self.color_widgets.items():
            color_box.setStyleSheet(f"""
                QPushButton {{
                    background-color: {default_color};
                    border: 1px solid {"#666" if "nonwear" in key else "#000"};
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    border: 2px solid #0066CC;
                }}
            """)

        # Apply the default colors immediately
        self.apply_colors()

    def apply_colors(self) -> None:
        """Apply the selected colors to the plot in real-time."""
        # Get the saved color settings
        settings = QSettings("SleepScoring", "ColorSettings")

        # Update the constants dynamically (for new elements)
        if hasattr(self.parent, "plot_widget"):
            plot_widget = self.parent.plot_widget

            # Get the colors from settings
            onset_marker_color = settings.value("colors/onset_marker", "#0080FF")
            offset_marker_color = settings.value("colors/offset_marker", "#FF8000")
            onset_arrow_color = settings.value("colors/onset_arrow", "#0066CC")
            offset_arrow_color = settings.value("colors/offset_arrow", "#FFA500")

            # Always set custom marker colors (even if no markers exist yet)
            plot_widget.custom_colors = {
                "selected_onset": onset_marker_color,
                "selected_offset": offset_marker_color,
                "unselected_onset": self._darken_color(onset_marker_color),
                "unselected_offset": self._darken_color(offset_marker_color),
            }

            # Redraw markers if they exist
            if hasattr(plot_widget, "marker_lines") and plot_widget.marker_lines:
                plot_widget.redraw_markers()

            # Always set custom arrow colors (even if no arrows exist yet)
            plot_widget.custom_arrow_colors = {
                "onset": onset_arrow_color,
                "offset": offset_arrow_color,
            }

            # Reapply sleep scoring rules to update arrows if they exist
            if hasattr(plot_widget, "sleep_rule_markers") and plot_widget.sleep_rule_markers:
                selected_period = plot_widget.get_selected_marker_period()
                if selected_period and selected_period.is_complete:
                    plot_widget.apply_sleep_scoring_rules(selected_period)

            # Update nonwear colors
            sensor_color = settings.value("colors/sensor_nonwear", "rgba(255,215,0,60)")
            choi_color = settings.value("colors/choi_nonwear", "rgba(147,112,219,60)")
            overlap_color = settings.value("colors/overlap_nonwear", "rgba(65,105,225,60)")

            # Convert RGBA to hex for nonwear colors
            sensor_hex = self._rgba_to_hex(sensor_color)
            choi_hex = self._rgba_to_hex(choi_color)
            overlap_hex = self._rgba_to_hex(overlap_color)

            # Always set custom nonwear colors
            plot_widget.custom_nonwear_colors = {
                "sensor_brush": sensor_hex,
                "sensor_border": sensor_hex,
                "choi_brush": choi_hex,
                "choi_border": choi_hex,
                "overlap_brush": overlap_hex,
                "overlap_border": overlap_hex,
            }

            # Replot nonwear regions if they exist
            if hasattr(plot_widget, "plot_nonwear_periods") and hasattr(plot_widget, "nonwear_regions"):
                plot_widget.plot_nonwear_periods()

        # Update table colors
        onset_table_color = settings.value("colors/onset_table", "#87CEEB")
        offset_table_color = settings.value("colors/offset_table", "#FFDAB9")

        # Store custom table colors on plot_widget (where main_window expects them)
        if hasattr(self.parent, "plot_widget"):
            plot_widget = self.parent.plot_widget
            plot_widget.custom_table_colors = {
                "onset_bg": onset_table_color,
                "onset_fg": "#000000",
                "offset_bg": offset_table_color,
                "offset_fg": "#000000",
            }

            # Trigger table update to apply new colors
            if hasattr(self.parent.parent, "onset_table") and hasattr(self.parent.parent, "offset_table"):
                if hasattr(self.parent.parent, "update_marker_tables"):
                    if hasattr(self.parent.parent, "_onset_table_data") and hasattr(self.parent.parent, "_offset_table_data"):
                        self.parent.parent.update_marker_tables(self.parent.parent._onset_table_data, self.parent.parent._offset_table_data)

    def _darken_color(self, color_str: str) -> str:
        """Darken a color by reducing its value."""
        color = QColor(color_str)
        # Reduce value by 40%
        h, s, v, a = color.getHsv()
        color.setHsv(h, s, int(v * 0.6), a)
        return color.name()

    def _rgba_to_hex(self, rgba_str: str) -> str:
        """Convert rgba(r,g,b,a) string to hex color."""
        # Extract RGBA values from string like "rgba(255,215,0,60)"
        match = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*(\d+))?\)", rgba_str)
        if match:
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"#{r:02x}{g:02x}{b:02x}"
        # If already hex or can't parse, return as-is
        return rgba_str
