from __future__ import annotations

import sys
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .workflows import AdminProcessor, AppliedChange, JobKind, PreviewResult


@dataclass
class QueueJob:
    path: Path
    preview: PreviewResult
    status: str = "Ready"
    change: AppliedChange | None = None


class EventOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Event Details")
        layout = QFormLayout(self)
        self.event_type = QComboBox()
        self.event_type.addItem("Annual Conference", "annual_conference")
        self.event_type.addItem("Distinguished Lectureship", "distinguished_lectureship")
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(2027)
        layout.addRow("Event type", self.event_type)
        layout.addRow("Event year", self.year)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[str, str]:
        return str(self.event_type.currentData()), str(self.year.value())


class DownloadsInboxDialog(QDialog):
    def __init__(self, paths: list[Path], parent=None):
        super().__init__(parent)
        self.setWindowTitle("SAGP Files in Downloads")
        self.resize(760, 460)
        layout = QVBoxLayout(self)
        intro = QLabel("Select one or more files to add to the processing queue.")
        layout.addWidget(intro)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for path in paths:
            modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %I:%M %p")
            item = QListWidgetItem(f"{path.name}    ·    {modified}")
            item.setData(256, str(path))
            self.list.addItem(item)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_paths(self) -> list[Path]:
        return [Path(item.data(256)) for item in self.list.selectedItems()]


class EventPreviewDialog(QDialog):
    """A website-faithful event preview embedded in the desktop app."""

    def __init__(self, url: QUrl, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Event Website Preview")
        self.resize(1100, 800)
        layout = QVBoxLayout(self)

        note = QLabel(
            "This is the website's rich rendering of the local draft. "
            "Nothing has been committed or published."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self.web_view = QWebEngineView()
        self.web_view.setUrl(url)
        layout.addWidget(self.web_view, 1)

        actions = QHBoxLayout()
        refresh = QPushButton("Refresh Preview")
        browser = QPushButton("Open in Browser")
        close = QPushButton("Close")
        refresh.clicked.connect(self.web_view.reload)
        browser.clicked.connect(lambda: QDesktopServices.openUrl(url))
        close.clicked.connect(self.close)
        actions.addWidget(refresh)
        actions.addWidget(browser)
        actions.addStretch()
        actions.addWidget(close)
        layout.addLayout(actions)


class Worker(QObject):
    log = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, operation):
        super().__init__()
        self.operation = operation

    def run(self):
        try:
            result = self.operation(self.log.emit)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class AdminProcessorWindow(QMainWindow):
    def __init__(self, processor: AdminProcessor | None = None):
        super().__init__()
        self.processor = processor or AdminProcessor()
        self.jobs: list[QueueJob] = []
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self.preview_server: subprocess.Popen | None = None
        self.event_preview_window: EventPreviewDialog | None = None
        self.setWindowTitle("SAGP Administrative Processor")
        self.resize(1280, 820)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        title = QLabel("SAGP Administrative Processor")
        title.setObjectName("appTitle")
        subtitle = QLabel("Review incoming files, process them locally, back out mistakes, and deploy only after approval.")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        intake = QHBoxLayout()
        self.add_button = QPushButton("Choose Files…")
        self.scan_button = QPushButton("Scan Downloads")
        self.remove_button = QPushButton("Remove Selected")
        intake.addWidget(self.add_button)
        intake.addWidget(self.scan_button)
        intake.addWidget(self.remove_button)
        intake.addStretch()
        layout.addLayout(intake)

        splitter = QSplitter()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["File", "Workflow", "Status", "Title"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        details_group = QGroupBox("Validation and Preview")
        details_layout = QVBoxLayout(details_group)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        details_layout.addWidget(self.details)
        splitter.addWidget(self.table)
        splitter.addWidget(details_group)
        splitter.setSizes([620, 660])
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.process_button = QPushButton("Process Selected Locally")
        self.process_all_button = QPushButton("Process All Ready Files")
        self.preview_event_button = QPushButton("Preview Event as Website")
        self.back_button = QPushButton("Back Out Last Change")
        self.back_all_button = QPushButton("Back Out All")
        self.deploy_button = QPushButton("Commit, Push and Deploy…")
        self.deploy_button.setObjectName("deployButton")
        for button in (self.process_button, self.process_all_button, self.preview_event_button, self.back_button, self.back_all_button, self.deploy_button):
            actions.addWidget(button)
        layout.addLayout(actions)

        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        log_layout.addWidget(self.log)
        layout.addWidget(log_group, 1)

        self.status = QLabel()
        layout.addWidget(self.status)

        self.add_button.clicked.connect(self._choose_files)
        self.scan_button.clicked.connect(self._scan_downloads)
        self.remove_button.clicked.connect(self._remove_selected)
        self.table.itemSelectionChanged.connect(self._show_selected)
        self.process_button.clicked.connect(self._process_selected)
        self.process_all_button.clicked.connect(self._process_all)
        self.preview_event_button.clicked.connect(self._open_event_preview)
        self.back_button.clicked.connect(self._back_out_last)
        self.back_all_button.clicked.connect(self._back_out_all)
        self.deploy_button.clicked.connect(self._deploy)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: palette(window);
                color: palette(window-text);
            }
            #appTitle {
                color: palette(window-text);
                font: 30px Georgia;
                margin-top: 8px;
            }
            QPushButton {
                background: palette(button);
                color: palette(button-text);
                padding: 8px 12px;
            }
            QPushButton:disabled {
                color: palette(mid);
            }
            #deployButton {
                background: #5f5a2f;
                color: #ffffff;
                font-weight: bold;
                padding: 10px 16px;
            }
            #deployButton:disabled {
                background: palette(button);
                color: palette(mid);
            }
            QGroupBox {
                color: palette(window-text);
                font-weight: bold;
                border: 1px solid palette(mid);
                border-radius: 3px;
                margin-top: 22px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 1px 6px;
                background: palette(window);
                color: palette(window-text);
            }
            QPlainTextEdit, QTableWidget, QListWidget, QComboBox, QSpinBox {
                background: palette(base);
                color: palette(text);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
            QHeaderView::section {
                background: palette(button);
                color: palette(button-text);
            }
        """)

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose SAGP Administrative Files", str(Path.home() / "Downloads"), "Supported Files (*.json *.docx);;JSON Requests (*.json);;Word Documents (*.docx)")
        self._add_files([Path(item) for item in files])

    def _scan_downloads(self):
        downloads = Path.home() / "Downloads"
        candidates = []
        for pattern in ("membership_*.json", "publication_update_*.json", "*.docx"):
            candidates.extend(downloads.glob(pattern))
        candidates = sorted(set(candidates), key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            QMessageBox.information(self, "No Files Found", "No JSON requests or Word documents were found in Downloads.")
            return
        dialog = DownloadsInboxDialog(candidates, self)
        if dialog.exec() == QDialog.Accepted:
            self._add_files(dialog.selected_paths())

    def _add_files(self, paths: list[Path]):
        existing = {job.path.resolve() for job in self.jobs}
        for path in paths:
            if path.resolve() in existing:
                continue
            if path.suffix.lower() == ".docx":
                dialog = EventOptionsDialog(self)
                if dialog.exec() != QDialog.Accepted:
                    continue
                event_type, year = dialog.values()
                preview = self.processor.preview_file(path, event_type, year)
            else:
                preview = self.processor.preview_file(path)
            status = "Ready" if preview.valid else "Needs attention"
            self.jobs.append(QueueJob(path.resolve(), preview, status))
            existing.add(path.resolve())
        self._refresh()

    def _selected_index(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _remove_selected(self):
        index = self._selected_index()
        if index is None:
            return
        if self.jobs[index].change is not None:
            QMessageBox.warning(self, "Change Already Applied", "Back out this change before removing its file from the queue.")
            return
        self.jobs.pop(index)
        self._refresh()

    def _show_selected(self):
        index = self._selected_index()
        if index is None:
            self.details.clear()
            self._refresh_buttons()
            return
        preview = self.jobs[index].preview
        sections = [preview.summary]
        if preview.warnings:
            sections.extend(["", "Warnings:", *[f"• {item}" for item in preview.warnings]])
        if preview.errors:
            sections.extend(["", "Errors:", *[f"• {item}" for item in preview.errors]])
        self.details.setPlainText("\n".join(sections))
        self._refresh_buttons()

    def _refresh(self):
        selected = self._selected_index()
        self.table.setRowCount(len(self.jobs))
        for row, job in enumerate(self.jobs):
            for column, value in enumerate((job.path.name, job.preview.kind.value, job.status, job.preview.title)):
                self.table.setItem(row, column, QTableWidgetItem(value))
        if selected is not None and selected < len(self.jobs):
            self.table.selectRow(selected)
        self.status.setText(f"{len(self.jobs)} file(s) in queue · {len(self.processor.applied)} uncommitted local change(s)")
        self._refresh_buttons()

    def _refresh_buttons(self):
        busy = self.thread is not None
        index = self._selected_index()
        selected = self.jobs[index] if index is not None and index < len(self.jobs) else None
        self.process_button.setEnabled(not busy and bool(selected and selected.preview.valid and selected.change is None))
        self.process_all_button.setEnabled(not busy and any(job.preview.valid and job.change is None for job in self.jobs))
        self.preview_event_button.setEnabled(not busy and bool(selected and selected.change and selected.preview.kind == JobKind.EVENT_DOCX))
        rollback_available = self.processor.deployment_phase == "local"
        self.back_button.setEnabled(not busy and rollback_available and bool(self.processor.applied))
        self.back_all_button.setEnabled(not busy and rollback_available and bool(self.processor.applied))
        self.deploy_button.setEnabled(not busy and bool(self.processor.applied))
        self.add_button.setEnabled(not busy)
        self.scan_button.setEnabled(not busy)

    def _process_selected(self):
        index = self._selected_index()
        if index is not None:
            self._confirm_and_process([index])

    def _process_all(self):
        indices = [index for index, job in enumerate(self.jobs) if job.preview.valid and job.change is None]
        self._confirm_and_process(indices)

    def _confirm_and_process(self, indices: list[int]):
        if not indices:
            return
        names = "\n".join(f"• {self.jobs[index].preview.kind.value}: {self.jobs[index].preview.title}" for index in indices)
        answer = QMessageBox.question(self, "Process Locally?", f"These changes will be applied locally but not committed or deployed:\n\n{names}\n\nYou can back them out before deployment. Continue?")
        if answer != QMessageBox.Yes:
            return

        def operation(log):
            results = []
            for index in indices:
                job = self.jobs[index]
                log(f"\nProcessing {job.path.name}")
                results.append((index, self.processor.process(job.path, job.preview, log)))
            return results

        self._start_worker(operation, self._processed)

    def _processed(self, results):
        for index, change in results:
            self.jobs[index].change = change
            self.jobs[index].status = "Processed locally"
        self._append_log("Local processing complete. Review the changes before deployment.")
        self._refresh()

    def _back_out_last(self):
        if QMessageBox.question(self, "Back Out Last Change?", "Restore the state from immediately before the most recent local change?") != QMessageBox.Yes:
            return
        try:
            change = self.processor.back_out_last()
            for job in self.jobs:
                if job.change and job.change.change_id == change.change_id:
                    job.change = None
                    job.status = "Backed out"
            self._append_log(f"Backed out: {change.kind.value} — {change.title}")
            self._refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Back Out Change", str(exc))

    def _back_out_all(self):
        if QMessageBox.question(self, "Back Out All Changes?", "Restore every uncommitted local change in reverse order?") != QMessageBox.Yes:
            return
        try:
            reverted = self.processor.back_out_all()
            reverted_ids = {item.change_id for item in reverted}
            for job in self.jobs:
                if job.change and job.change.change_id in reverted_ids:
                    job.change = None
                    job.status = "Backed out"
            self._append_log(f"Backed out {len(reverted)} local change(s).")
            self._refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Back Out Changes", str(exc))

    def _deploy(self):
        summary = self.processor.deployment_summary()
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Final Deployment Approval")
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText("Commit, push, and deploy these approved changes?")
        dialog.setDetailedText(summary)
        dialog.setInformativeText(summary)
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        if dialog.exec() != QMessageBox.Yes:
            return
        self._start_worker(lambda log: self.processor.deploy(log), self._deployed)

    def _deployed(self, _):
        for job in self.jobs:
            if job.change:
                job.status = "Deployed"
                job.change = None
        self._append_log("Deployment workflow completed successfully.")
        self._refresh()
        QMessageBox.information(self, "Deployment Complete", "The approved changes were committed, pushed, and deployed.")

    def _open_event_preview(self):
        index = self._selected_index()
        if index is None:
            return
        change = self.jobs[index].change
        if not change:
            return
        try:
            event_type = change.details["event_type"].replace("_", "-")
            year = change.details["year"]
            url = QUrl(f"http://127.0.0.1:4322/sagp_website/executive/draft-event-preview/{event_type}/{year}/")
            self._ensure_preview_server(url.toString())
            if self.event_preview_window is not None:
                self.event_preview_window.close()
            self.event_preview_window = EventPreviewDialog(url, self)
            self.event_preview_window.setAttribute(Qt.WA_DeleteOnClose)
            self.event_preview_window.destroyed.connect(self._preview_window_closed)
            self.event_preview_window.show()
            self.event_preview_window.raise_()
            self.event_preview_window.activateWindow()
            self._append_log("Opened the rich website rendering of the local event draft inside the app.")
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Open Preview", str(exc))

    def _preview_window_closed(self):
        self.event_preview_window = None

    def _ensure_preview_server(self, preview_url: str):
        self._append_log("Building the local website for a deployment-faithful preview…")
        build = subprocess.run(
            ["npm", "run", "build"],
            cwd=self.processor.website,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if build.returncode:
            raise RuntimeError(f"The local website build failed:\n\n{build.stdout[-4000:]}")

        try:
            urllib.request.urlopen(preview_url, timeout=1).close()
            return
        except (urllib.error.URLError, TimeoutError):
            pass

        if self.preview_server is None or self.preview_server.poll() is not None:
            self._append_log("Starting the local website preview server…")
            self.preview_server = subprocess.Popen(
                ["npm", "run", "preview", "--", "--host", "127.0.0.1", "--port", "4322"],
                cwd=self.processor.website,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.preview_server.poll() is not None:
                raise RuntimeError("The local website preview server stopped unexpectedly.")
            try:
                urllib.request.urlopen(preview_url, timeout=1).close()
                return
            except (urllib.error.URLError, TimeoutError):
                QApplication.processEvents()
                time.sleep(0.2)
        raise TimeoutError("The local website preview did not become ready within 20 seconds.")

    def _start_worker(self, operation, on_success):
        self.thread = QThread(self)
        self.worker = Worker(operation)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append_log)
        self.worker.finished.connect(on_success)
        self.worker.finished.connect(self._finish_worker)
        self.worker.failed.connect(self._worker_failed)
        self.worker.failed.connect(self._finish_worker)
        self.thread.start()
        self._refresh_buttons()

    def _finish_worker(self, *_):
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self._refresh()

    def _worker_failed(self, message: str):
        applied_by_source = {change.source_file: change for change in self.processor.applied}
        for job in self.jobs:
            if job.change is None and job.path in applied_by_source:
                job.change = applied_by_source[job.path]
                job.status = "Processed locally"
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Operation Failed", message)

    def _append_log(self, message: str):
        self.log.appendPlainText(message)

    def closeEvent(self, event):
        if self.processor.applied:
            QMessageBox.warning(
                self,
                "Uncommitted Changes Remain",
                "Back out or deploy all locally processed changes before closing the application.",
            )
            event.ignore()
            return
        if self.preview_server is not None and self.preview_server.poll() is None:
            self.preview_server.terminate()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SAGP Administrative Processor")
    window = AdminProcessorWindow()
    window.show()
    sys.exit(app.exec())
