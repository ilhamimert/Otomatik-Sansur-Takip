from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QListWidget,
    QListWidgetItem, QGroupBox, QCheckBox, QFrame
)

from core.watch_folder import WatchFolderService, WatchedFile
from utils.video_utils import is_video_file


class WatchFolderPanel(QWidget):
    new_video_detected = pyqtSignal(str)   # video path
    scan_folder_requested = pyqtSignal(list)  # [path1, path2, ...]

    def __init__(self):
        super().__init__()
        self._service: WatchFolderService | None = None
        self._auto_scan = True
        self._queue: list[str] = []
        self._build_ui()

    # ── UI ──

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("WATCH FOLDER")
        title.setObjectName("label_title")
        layout.addWidget(title)

        # Klasör seçimi
        folder_group = QGroupBox("Klasör")
        folder_layout = QHBoxLayout(folder_group)
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText("Klasör seçin...")
        self._folder_input.setReadOnly(True)
        btn_browse = QPushButton("📁")
        btn_browse.setObjectName("btn_icon")
        btn_browse.setFixedWidth(36)
        btn_browse.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self._folder_input)
        folder_layout.addWidget(btn_browse)
        layout.addWidget(folder_group)

        # Toplu tara butonu
        self._btn_scan_all = QPushButton("  Klasördeki Tüm Videoları Tara")
        self._btn_scan_all.setObjectName("btn_primary")
        self._btn_scan_all.setEnabled(False)
        self._btn_scan_all.clicked.connect(self._scan_all_videos)
        layout.addWidget(self._btn_scan_all)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #0F2040;")
        layout.addWidget(sep)

        # Otomatik izleme
        self._chk_auto = QCheckBox("Yeni video gelince otomatik tara")
        self._chk_auto.setChecked(True)
        self._chk_auto.stateChanged.connect(
            lambda s: setattr(self, "_auto_scan",
                              s == Qt.CheckState.Checked.value))
        layout.addWidget(self._chk_auto)

        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("▶  İzlemeyi Başlat")
        self._btn_stop = QPushButton("⏹  Durdur")
        self._btn_stop.setEnabled(False)
        self._btn_start.clicked.connect(self._start_watch)
        self._btn_stop.clicked.connect(self._stop_watch)
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_stop)
        layout.addLayout(btn_row)

        # Durum
        self._lbl_status = QLabel("Klasör seçin.")
        self._lbl_status.setObjectName("label_status")
        self._lbl_status.setWordWrap(True)
        layout.addWidget(self._lbl_status)

        # Video listesi
        list_group = QGroupBox("Videolar")
        list_layout = QVBoxLayout(list_group)
        self._file_list = QListWidget()
        list_layout.addWidget(self._file_list)
        layout.addWidget(list_group, stretch=1)

    # ── Klasör seçimi ──

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Klasör Seç")
        if not folder:
            return
        self._folder_input.setText(folder)
        self._btn_scan_all.setEnabled(True)
        self._scan_folder_contents(folder)

    def _scan_folder_contents(self, folder: str):
        """Klasördeki mevcut videoları listele."""
        self._file_list.clear()
        self._queue.clear()
        videos = [f for f in Path(folder).iterdir()
                  if f.is_file() and is_video_file(str(f))]
        for v in sorted(videos):
            size_mb = v.stat().st_size / 1024 / 1024
            item = QListWidgetItem(f"  {v.name}  ({size_mb:.1f} MB)")
            self._file_list.addItem(item)
            self._queue.append(str(v))

        count = len(videos)
        if count == 0:
            self._lbl_status.setText("Klasörde video bulunamadı.")
            self._btn_scan_all.setEnabled(False)
        else:
            self._lbl_status.setText(f"{count} video bulundu.")

    # ── Toplu Tarama ──

    def _scan_all_videos(self):
        if not self._queue:
            self._lbl_status.setText("Taranacak video yok.")
            return
        self._lbl_status.setText(f"{len(self._queue)} video sıraya alındı...")
        self.scan_folder_requested.emit(list(self._queue))

    # ── Otomatik İzleme ──

    def _start_watch(self):
        folder = self._folder_input.text().strip()
        if not folder:
            self._lbl_status.setText("Önce bir klasör seçin.")
            return
        self._service = WatchFolderService(folder, self._on_new_video)
        self._service.start()
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._lbl_status.setText(f"İzleniyor: {Path(folder).name}")

    def _stop_watch(self):
        if self._service:
            self._service.stop()
            self._service = None
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._lbl_status.setText("İzleme durduruldu.")

    def _on_new_video(self, wf: WatchedFile):
        size_mb = wf.size_bytes / 1024 / 1024
        item = QListWidgetItem(f"  {wf.name}  ({size_mb:.1f} MB)  ← YENİ")
        self._file_list.insertItem(0, item)
        self._lbl_status.setText(f"Yeni: {wf.name}")
        if self._auto_scan:
            self.new_video_detected.emit(wf.path)

    def closeEvent(self, event):
        self._stop_watch()
        event.accept()
