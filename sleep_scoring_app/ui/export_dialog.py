#!/usr/bin/env python3
"""
Export Dialog UI Component
Modal dialog for configuring data export options.
"""

from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from sleep_scoring_app.core.constants import ButtonText, ExportColumn, WindowTitle


class ExportDialog(QDialog):
    """Modal dialog for configuring data export options."""

    def __init__(self, parent, backup_file_path) -> None:
        super().__init__(parent)
        self.backup_file_path = backup_file_path
        self.grouping_option = None
        self.output_path = None
        self.setup_ui()

    def setup_ui(self) -> None:
        """Create the dialog interface."""
        self.setWindowTitle(WindowTitle.EXPORT_DIALOG)
        self.setModal(True)
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel(WindowTitle.EXPORT_DIALOG)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # Data summary - create placeholder first, load data after dialog shows
        self.summary_label = QLabel("Loading data summary...")
        self.summary_label.setStyleSheet("margin: 10px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(self.summary_label)

        # Grouping options
        grouping_group = QGroupBox("Grouping Options")
        grouping_layout = QVBoxLayout(grouping_group)

        self.grouping_group = QButtonGroup()

        # All data in one file
        all_radio = QRadioButton("All data in one file")
        all_radio.setChecked(True)
        self.grouping_group.addButton(all_radio, 0)
        grouping_layout.addWidget(all_radio)

        # By participant ID
        participant_radio = QRadioButton("Separate file for each participant")
        self.grouping_group.addButton(participant_radio, 1)
        grouping_layout.addWidget(participant_radio)

        # By group
        group_radio = QRadioButton("Separate file for each group")
        self.grouping_group.addButton(group_radio, 2)
        grouping_layout.addWidget(group_radio)

        # By timepoint
        timepoint_radio = QRadioButton("Separate file for each timepoint")
        self.grouping_group.addButton(timepoint_radio, 3)
        grouping_layout.addWidget(timepoint_radio)

        layout.addWidget(grouping_group)

        # Output directory selection
        output_group = QGroupBox("Output Directory")
        output_layout = QVBoxLayout(output_group)

        self.output_label = QLabel("No directory selected")
        self.output_label.setStyleSheet("padding: 5px; background-color: white; border: 1px solid #ccc;")
        output_layout.addWidget(self.output_label)

        browse_btn = QPushButton(ButtonText.BROWSE)
        browse_btn.clicked.connect(self.browse_output_directory)
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Buttons
        button_layout = QHBoxLayout()

        export_btn = QPushButton(ButtonText.EXPORT)
        export_btn.clicked.connect(self.accept)
        export_btn.setDefault(True)
        button_layout.addWidget(export_btn)

        cancel_btn = QPushButton(ButtonText.CANCEL)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Load data after dialog is visible
        QTimer.singleShot(0, self._load_data_summary)

    def _load_data_summary(self) -> None:
        """Load data summary after dialog is shown to prevent blocking."""
        try:
            df = pd.read_csv(self.backup_file_path, comment="#")
            summary_text = f"Data to export: {len(df)} records from backup file"

            # Try to show some sample data info
            if ExportColumn.FULL_PARTICIPANT_ID in df.columns:
                unique_participants = df[ExportColumn.FULL_PARTICIPANT_ID].nunique()
                summary_text += f"\nParticipants: {unique_participants}"

            if ExportColumn.PARTICIPANT_GROUP in df.columns:
                unique_groups = df[ExportColumn.PARTICIPANT_GROUP].nunique()
                summary_text += f"\nGroups: {unique_groups}"

        except (OSError, PermissionError, pd.errors.ParserError, ValueError) as e:
            summary_text = f"Error reading backup file: {e}"

        self.summary_label.setText(summary_text)

    def browse_output_directory(self) -> None:
        """Handle directory selection."""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_path = directory
            self.output_label.setText(directory)

    def get_grouping_option(self) -> int:
        """Return selected grouping option."""
        return self.grouping_group.checkedId()

    def get_output_path(self) -> str:
        """Return selected output path."""
        return self.output_path
