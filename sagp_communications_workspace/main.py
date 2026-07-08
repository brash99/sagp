import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sagp_core import (
    Audience,
    Message,
    load_audience_dict,
    load_message_dict,
    save_communication,
)
from sagp_engines.communication import CommunicationEngine


def display(value):
    return "" if value is None else str(value)


class CommunicationsWorkspace(QMainWindow):
    def __init__(self):
        super().__init__()

        self.audience = None
        self.message = None
        self.communication = None
        self.engine = CommunicationEngine()

        self.setWindowTitle("SAGP Communications Workspace")
        self.resize(1200, 800)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        top_row = QHBoxLayout()

        self.load_audience_button = QPushButton("Load Audience JSON")
        self.load_message_button = QPushButton("Load Message JSON")
        self.compose_button = QPushButton("Compose Communication")
        self.save_button = QPushButton("Save Communication JSON")

        self.compose_button.setEnabled(False)
        self.save_button.setEnabled(False)

        top_row.addWidget(self.load_audience_button)
        top_row.addWidget(self.load_message_button)
        top_row.addWidget(self.compose_button)
        top_row.addWidget(self.save_button)

        layout.addLayout(top_row)

        summary_group = QGroupBox("Composition Summary")
        summary_layout = QVBoxLayout(summary_group)

        self.audience_summary = QLabel("Audience: none loaded")
        self.message_summary = QLabel("Message: none loaded")
        self.communication_summary = QLabel("Communication: none composed")

        summary_layout.addWidget(self.audience_summary)
        summary_layout.addWidget(self.message_summary)
        summary_layout.addWidget(self.communication_summary)

        layout.addWidget(summary_group)

        self.tabs = QTabWidget()

        self.recipients_preview = QPlainTextEdit()
        self.recipients_preview.setReadOnly(True)

        self.html_preview = QPlainTextEdit()
        self.html_preview.setReadOnly(True)

        self.text_preview = QPlainTextEdit()
        self.text_preview.setReadOnly(True)

        self.audit_preview = QPlainTextEdit()
        self.audit_preview.setReadOnly(True)

        self.tabs.addTab(self.recipients_preview, "Recipients")
        self.tabs.addTab(self.html_preview, "Rich HTML")
        self.tabs.addTab(self.text_preview, "Plain Text")
        self.tabs.addTab(self.audit_preview, "Audit / Metadata")

        layout.addWidget(self.tabs)

        self.load_audience_button.clicked.connect(self._load_audience)
        self.load_message_button.clicked.connect(self._load_message)
        self.compose_button.clicked.connect(self._compose)
        self.save_button.clicked.connect(self._save)

    def _load_audience(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Audience JSON",
            "output/audiences",
            "JSON Files (*.json)",
        )

        if not filename:
            return

        try:
            data = load_audience_dict(filename)
            self.audience = Audience.from_dict(data)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Could Not Load Audience",
                f"Could not load Audience JSON:\n\n{exc}",
            )
            return

        self._refresh_ui()

    def _load_message(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Message JSON",
            "output/messages",
            "JSON Files (*.json)",
        )

        if not filename:
            return

        try:
            data = load_message_dict(filename)
            self.message = Message.from_dict(data)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Could Not Load Message",
                f"Could not load Message JSON:\n\n{exc}",
            )
            return

        self._refresh_ui()

    def _compose(self):
        if self.audience is None or self.message is None:
            return

        try:
            self.communication = self.engine.compose(
                self.audience,
                self.message,
                created_by="communications_workspace",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Could Not Compose Communication",
                f"Could not compose communication:\n\n{exc}",
            )
            return

        self._refresh_ui()

    def _save(self):
        if self.communication is None:
            return

        output_dir = Path("output/communications")
        default_name = output_dir / f"{self.communication.communication_id}.json"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Communication JSON",
            str(default_name),
            "JSON Files (*.json)",
        )

        if not filename:
            return

        try:
            path = save_communication(
                self.communication,
                Path(filename).parent,
            )

            requested = Path(filename)
            if path != requested:
                path.rename(requested)
                path = requested

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Could Not Save Communication",
                f"Could not save Communication JSON:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Communication Saved",
            f"Saved communication artifact:\n\n{path}",
        )

    def _refresh_ui(self):
        if self.audience is None:
            self.audience_summary.setText("Audience: none loaded")
            self.recipients_preview.clear()
        else:
            self.audience_summary.setText(
                f"Audience: {self.audience.name} "
                f"({len(self.audience.recipients):,} recipients)"
            )
            lines = [
                f"Audience ID: {self.audience.audience_id}",
                f"Name: {self.audience.name}",
                f"Description: {self.audience.description}",
                f"Criteria: {self.audience.criteria}",
                "",
                "Recipients:",
            ]
            for recipient in self.audience.recipients:
                lines.append(
                    f"- {display(recipient.name)} <{display(recipient.email)}> "
                    f"[{display(recipient.membership_status)}]"
                )
            self.recipients_preview.setPlainText("\n".join(lines))

        if self.message is None:
            self.message_summary.setText("Message: none loaded")
            self.html_preview.clear()
            self.text_preview.clear()
        else:
            self.message_summary.setText(
                f"Message: {self.message.title} — Subject: {self.message.subject}"
            )
            self.html_preview.setPlainText(self.message.rich_html)
            self.text_preview.setPlainText(self.message.plain_text)

        self.compose_button.setEnabled(
            self.audience is not None and self.message is not None
        )

        if self.communication is None:
            self.communication_summary.setText("Communication: none composed")
            self.audit_preview.clear()
            self.save_button.setEnabled(False)
        else:
            summary = self.communication.summary()
            self.communication_summary.setText(
                f"Communication: {summary['communication_id']} — "
                f"{summary['recipient_count']:,} recipients — "
                f"{summary['delivery_status']}"
            )
            self.audit_preview.setPlainText(
                "\n".join(f"{key}: {value}" for key, value in summary.items())
            )
            self.save_button.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    window = CommunicationsWorkspace()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
