#!/usr/bin/env python3
"""
File Management Widget
Displays imported files with delete functionality.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import ImportedFileInfo
    from sleep_scoring_app.services.file_management_service import FileManagementService

logger = logging.getLogger(__name__)


class FileManagementWidget(QWidget):
    """Widget for managing imported files with delete functionality."""

    # Signal emitted when files are deleted (list of filenames)
    filesDeleted = pyqtSignal(list)

    def __init__(self, file_service: FileManagementService, parent: QWidget | None = None) -> None:
        """
        Initialize the file management widget.

        Args:
            file_service: Service for file management operations
            parent: Parent widget

        """
        super().__init__(parent)
        self.file_service = file_service
        self.imported_files: list[ImportedFileInfo] = []

        self._setup_ui()
        self.refresh_files()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)

        # Table for file list
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(7)
        self.file_table.setHorizontalHeaderLabels(
            [
                "Filename",
                "Participant ID",
                "Start Date",
                "End Date",
                "Records",
                "Has Metrics",
                "Actions",
            ]
        )

        # Configure table
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        self.file_table.setAlternatingRowColors(True)

        # Set column resize modes
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Filename
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Participant
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Start
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # End
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Records
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Metrics
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)  # Actions
        header.resizeSection(6, 100)  # Fixed width for action button

        layout.addWidget(self.file_table)

        # Button row
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_files)
        button_layout.addWidget(self.refresh_btn)

        button_layout.addStretch()

        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.delete_selected_btn.clicked.connect(self._delete_selected_files)
        button_layout.addWidget(self.delete_selected_btn)

        layout.addLayout(button_layout)

    def refresh_files(self) -> None:
        """Refresh the file list from database."""
        try:
            self.imported_files = self.file_service.get_imported_files()
            self._populate_table()
            logger.debug("Refreshed file list: %d files", len(self.imported_files))
        except Exception as e:
            logger.exception("Failed to refresh file list")
            QMessageBox.critical(self, "Error", f"Failed to refresh file list: {e}")

    def _populate_table(self) -> None:
        """Populate the table with file data."""
        self.file_table.setRowCount(len(self.imported_files))

        for row, file_info in enumerate(self.imported_files):
            # Filename
            filename_item = QTableWidgetItem(file_info.filename)
            filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.file_table.setItem(row, 0, filename_item)

            # Participant ID
            participant_item = QTableWidgetItem(file_info.participant_id)
            participant_item.setFlags(participant_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            participant_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.file_table.setItem(row, 1, participant_item)

            # Start Date
            start_item = QTableWidgetItem(file_info.date_range_start)
            start_item.setFlags(start_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            start_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.file_table.setItem(row, 2, start_item)

            # End Date
            end_item = QTableWidgetItem(file_info.date_range_end)
            end_item.setFlags(end_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            end_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.file_table.setItem(row, 3, end_item)

            # Record Count
            records_item = QTableWidgetItem(str(file_info.record_count))
            records_item.setFlags(records_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            records_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.file_table.setItem(row, 4, records_item)

            # Has Metrics
            metrics_text = "Yes" if file_info.has_metrics else "No"
            metrics_item = QTableWidgetItem(metrics_text)
            metrics_item.setFlags(metrics_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            metrics_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if file_info.has_metrics:
                metrics_item.setForeground(Qt.GlobalColor.darkGreen)
            self.file_table.setItem(row, 5, metrics_item)

            # Delete button
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    font-size: 10px;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            delete_btn.clicked.connect(lambda checked, f=file_info: self._delete_single_file(f))
            self.file_table.setCellWidget(row, 6, delete_btn)

    def _delete_single_file(self, file_info: ImportedFileInfo) -> None:
        """
        Delete a single file with confirmation.

        Args:
            file_info: File information to delete

        """
        self._delete_files_with_confirmation([file_info])

    def _delete_selected_files(self) -> None:
        """Delete all selected files with confirmation."""
        selected_rows = {item.row() for item in self.file_table.selectedItems()}

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select files to delete.")
            return

        selected_files = [self.imported_files[row] for row in sorted(selected_rows)]
        self._delete_files_with_confirmation(selected_files)

    def _delete_files_with_confirmation(self, files: list[ImportedFileInfo]) -> None:
        """
        Delete files after showing confirmation dialog.

        Args:
            files: List of files to delete

        """
        if not files:
            return

        # Show confirmation dialog
        from sleep_scoring_app.ui.dialogs.delete_file_dialog import DeleteFileDialog

        dialog = DeleteFileDialog(files, parent=self)
        if dialog.exec() != DeleteFileDialog.DialogCode.Accepted:
            return

        # Perform deletion
        filenames = [f.filename for f in files]
        result = self.file_service.delete_files(filenames)

        # Show results
        if result.successful > 0:
            message = f"Successfully deleted {result.successful} file(s)."
            if result.failed > 0:
                message += f"\nFailed to delete {result.failed} file(s)."
            QMessageBox.information(self, "Deletion Complete", message)

            # Emit signal and refresh
            self.filesDeleted.emit(filenames)
            self.refresh_files()
        else:
            QMessageBox.critical(self, "Deletion Failed", "Failed to delete selected files.")
