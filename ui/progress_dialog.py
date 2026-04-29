from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton
)


class ProgressDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._cancelled = False
        self._build_ui(title)

    def _build_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._lbl = QLabel(title)
        self._lbl.setWordWrap(True)
        layout.addWidget(self._lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        layout.addWidget(self._bar)

        self._lbl_detail = QLabel("")
        self._lbl_detail.setObjectName("label_status")
        layout.addWidget(self._lbl_detail)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton("İptal")
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

    def update_progress(self, current: int, total: int):
        if total > 0:
            pct = int(current / total * 100)
            self._bar.setValue(pct)
            self._lbl_detail.setText(f"{current:,} / {total:,} kare işlendi  ({pct}%)")

    def set_message(self, msg: str):
        self._lbl.setText(msg)

    def was_cancelled(self) -> bool:
        return self._cancelled

    def finish(self):
        self._btn_cancel.setEnabled(False)
        self._bar.setValue(100)

    def _on_cancel(self):
        self._cancelled = True
        self._btn_cancel.setEnabled(False)
        self._lbl.setText("İptal ediliyor...")
