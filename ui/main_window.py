from __future__ import annotations

from pathlib import Path
import yaml

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QSplitter, QFileDialog, QMessageBox, QStatusBar,
    QToolBar, QLabel, QFrame, QSizePolicy, QToolButton, QMenu
)

from ai.label_map import ViolationCategory
from core.scan_engine import ScanEngine, ScanConfig
from core.export_engine import ExportEngine
from core.violation_store import ViolationStore
from core.watch_folder import WatchFolderService
from ui.video_player_widget import VideoPlayerWidget
from ui.notification_panel import NotificationPanel
from ui.progress_dialog import ProgressDialog
from ui.settings_dialog import SettingsDialog
from ui.watch_folder_panel import WatchFolderPanel
from utils.video_utils import is_video_file

CONFIG_PATH = "config.yaml"


def load_config() -> dict:
    if Path(CONFIG_PATH).exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Vision Guard — Desktop Edition")
        self.setMinimumSize(1280, 720)
        self.resize(1440, 860)
        self.setAcceptDrops(True)

        self._config = load_config()
        self._store = ViolationStore()
        self._video_path: str | None = None
        self._scan_engine: ScanEngine | None = None
        self._export_engine: ExportEngine | None = None
        self._progress_dialog: ProgressDialog | None = None
        self._watch_service: WatchFolderService | None = None
        self._scan_queue: list[str] = []   # Toplu tarama kuyruğu

        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()
        self._update_status("Hazır — Video yüklemek için dosya seçin veya sürükleyip bırakın.")

    # ─────────────────────────────────────────
    # UI Kurulum
    # ─────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Ana splitter: Video | Violations
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)

        # Sol: Video oynatıcı
        self._player = VideoPlayerWidget()
        self._player.setObjectName("video_panel")
        self._splitter.addWidget(self._player)

        # Sağ: İhlal paneli
        self._notif_panel = NotificationPanel(self._store)
        self._notif_panel.setObjectName("violations_panel")
        self._notif_panel.setMinimumWidth(320)
        self._notif_panel.setMaximumWidth(440)
        self._notif_panel.violation_clicked.connect(self._player.seek_to_second)
        self._splitter.addWidget(self._notif_panel)

        # Watch Folder paneli (gizli, açılır kapanır)
        self._watch_panel = WatchFolderPanel()
        self._watch_panel.setMinimumWidth(280)
        self._watch_panel.setMaximumWidth(320)
        self._watch_panel.new_video_detected.connect(self._on_watch_video_detected)
        self._watch_panel.scan_folder_requested.connect(self._on_scan_folder_requested)
        self._watch_panel.hide()
        self._splitter.addWidget(self._watch_panel)

        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 1)

        root.addWidget(self._splitter)

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        # ── Logo / Marka ──
        lbl_brand = QLabel("  AI VISION GUARD")
        lbl_brand.setStyleSheet(
            "color: #1E6FD9; font-size: 13px; font-weight: 700; "
            "letter-spacing: 1.5px; padding-right: 20px;"
        )
        tb.addWidget(lbl_brand)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #0F2040; margin: 10px 4px;")
        tb.addWidget(sep)

        # ── Video Yükle (dropdown menü) ──
        self._btn_load = QToolButton()
        self._btn_load.setText("  Video Yükle")
        self._btn_load.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn_load.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._btn_load.setObjectName("btn_primary")

        load_menu = QMenu(self)
        load_menu.setStyleSheet("""
            QMenu {
                background-color: #0F2040;
                border: 1px solid #162840;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: #8BA3C4;
                border-radius: 4px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #162840;
                color: #E8F0FC;
            }
            QMenu::separator {
                height: 1px;
                background-color: #162840;
                margin: 4px 8px;
            }
        """)

        act_file = load_menu.addAction("  Dosya Seç...")
        act_file.triggered.connect(self._open_video_file)
        load_menu.addSeparator()
        self._act_watch_toggle = load_menu.addAction("  Watch Folder  ●  Kapalı")
        self._act_watch_toggle.setCheckable(True)
        self._act_watch_toggle.triggered.connect(self._toggle_watch_panel)

        self._btn_load.setMenu(load_menu)
        self._btn_load.clicked.connect(self._open_video_file)
        tb.addWidget(self._btn_load)

        tb.addSeparator()

        # ── Tara ──
        self._btn_scan = QToolButton()
        self._btn_scan.setText("  Tara")
        self._btn_scan.setObjectName("btn_primary")
        self._btn_scan.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn_scan.setEnabled(False)
        self._btn_scan.clicked.connect(self._start_scan)
        tb.addWidget(self._btn_scan)

        # ── Duraklat / Devam Et ──
        self._btn_pause = QToolButton()
        self._btn_pause.setText("  Duraklat")
        self._btn_pause.setObjectName("btn_warning")
        self._btn_pause.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn_pause.setEnabled(False)
        self._btn_pause.clicked.connect(self._toggle_pause_scan)
        tb.addWidget(self._btn_pause)

        # ── Durdur ──
        self._btn_stop = QToolButton()
        self._btn_stop.setText("  Durdur")
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_scan)
        tb.addWidget(self._btn_stop)

        tb.addSeparator()

        # ── Export ──
        self._btn_export = QToolButton()
        self._btn_export.setText("  Sansürle & Export")
        self._btn_export.setObjectName("btn_success")
        self._btn_export.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._start_export)
        tb.addWidget(self._btn_export)

        tb.addSeparator()

        # ── Ayarlar ──
        self._btn_settings = QToolButton()
        self._btn_settings.setText("  Ayarlar")
        self._btn_settings.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn_settings.clicked.connect(self._open_settings)
        tb.addWidget(self._btn_settings)

        # ── Sağa hizalı dosya adı ──
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._lbl_file = QLabel("Video yüklenmedi  ")
        self._lbl_file.setObjectName("label_status")
        self._lbl_file.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tb.addWidget(self._lbl_file)

    def _build_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        # Sol: durum mesajı
        self._lbl_status_left = QLabel()
        self._lbl_status_left.setObjectName("label_status")
        self._statusbar.addWidget(self._lbl_status_left, 1)

        # Sağ: Watch Folder durumu
        self._lbl_watch_status = QLabel()
        self._lbl_watch_status.setObjectName("label_status")
        self._lbl_watch_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._statusbar.addPermanentWidget(self._lbl_watch_status)

    # ─────────────────────────────────────────
    # Video İşlemleri
    # ─────────────────────────────────────────

    def _open_video_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Video Seç", "",
            "Video Dosyaları (*.mp4 *.avi *.mov *.mkv *.wmv *.flv "
            "*.ts *.mts *.mxf *.m2ts *.mpg *.mpeg);;Tüm Dosyalar (*)"
        )
        if path:
            self._load_video(path)

    def _load_video(self, path: str):
        self._video_path = path
        self._notif_panel.clear()
        self._player.load_video(path)
        name = Path(path).name
        self._lbl_file.setText(f"{name}  ")
        self._btn_scan.setEnabled(True)
        self._btn_export.setEnabled(False)
        self._update_status(f"Yüklendi: {name}")

    # ─────────────────────────────────────────
    # Tarama
    # ─────────────────────────────────────────

    def _check_missing_models(self):
        """Eksik modelleri kontrol et, varsa kullanıcıya uyar."""
        from ai.model_manager import ModelManager
        mm = ModelManager()
        missing = mm.get_missing_models()
        if missing:
            detail = "\n".join(f"  • {m}" for m in missing)
            QMessageBox.warning(
                self,
                "Eksik Model Dosyaları",
                f"Aşağıdaki model dosyaları bulunamadı veya yüklenemedi.\n"
                f"İlgili kategoriler tespit edilemeyecek:\n\n{detail}\n\n"
                f"Model dosyalarını 'models/' klasörüne kopyalayın."
            )

    def _start_scan(self):
        if not self._video_path:
            return

        self._check_missing_models()

        scan_cfg = self._config.get("scan", {})
        cat_cfg = self._config.get("categories", {})
        active_cats = {
            ViolationCategory[k.upper()]
            for k, v in cat_cfg.items()
            if v and k.upper() in ViolationCategory.__members__
        } or None

        config = ScanConfig(
            frame_skip=scan_cfg.get("frame_skip", 10),
            confidence=scan_cfg.get("confidence_threshold", 0.50),
            confirm_window=scan_cfg.get("confirm_window", 3),
            cpu_sleep_ms=scan_cfg.get("cpu_sleep_ms", 0),
            active_categories=active_cats,
            model_config=self._config.get("model", {}),
            verifier_mode=self._config.get("ai", {}).get("verifier_mode", "none"),
            motion_threshold=scan_cfg.get("motion_threshold", 800),
        )

        self._notif_panel.clear()
        self._btn_scan.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_pause.setText("  Duraklat")
        self._btn_stop.setEnabled(True)
        self._btn_export.setEnabled(False)
        self._btn_load.setEnabled(False)

        self._progress_dialog = ProgressDialog("Video taranıyor...", self)
        self._progress_dialog.show()

        self._scan_engine = ScanEngine(self._video_path, config, self._store)
        self._scan_engine.violation_found.connect(self._on_violation_found)
        self._scan_engine.progress_updated.connect(self._on_scan_progress)
        self._scan_engine.scan_completed.connect(self._on_scan_completed)
        self._scan_engine.scan_error.connect(self._on_scan_error)
        self._scan_engine.start()
        self._update_status("Tarama başlatıldı...")

    def _toggle_pause_scan(self):
        if not self._scan_engine:
            return
        if self._scan_engine.is_paused():
            self._scan_engine.resume()
            self._btn_pause.setText("  Duraklat")
            self._update_status("Tarama devam ediyor...")
        else:
            self._scan_engine.pause()
            self._btn_pause.setText("  Devam Et")
            self._update_status("Tarama duraklatıldı.")

    def _stop_scan(self):
        if self._scan_engine:
            self._scan_engine.cancel()
        if self._progress_dialog:
            self._progress_dialog.reject()
        self._btn_scan.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_pause.setText("  Duraklat")
        self._btn_stop.setEnabled(False)
        self._btn_load.setEnabled(True)
        self._update_status("Tarama durduruldu.")

    def _on_violation_found(self, record):
        self._notif_panel.add_violation(record)
        self._player.set_active_violations(
            self._store.load_for_video(self._video_path))

    def _on_scan_progress(self, current: int, total: int):
        if self._progress_dialog:
            self._progress_dialog.update_progress(current, total)
        if self._progress_dialog and self._progress_dialog.was_cancelled():
            self._stop_scan()

    def _on_scan_completed(self, summary):
        if self._progress_dialog:
            self._progress_dialog.finish()
            self._progress_dialog.close()

        self._btn_scan.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_pause.setText("  Duraklat")
        self._btn_stop.setEnabled(False)
        self._btn_export.setEnabled(True)
        self._btn_load.setEnabled(True)

        self._update_status(
            f"Tarama tamamlandı  —  {summary.violation_count} ihlal bulundu  "
            f"({summary.scanned_frames:,} kare tarandı)"
        )

        self._write_violation_report()

        # Toplu tarama kuyruğu varsa devam et
        if self._scan_queue:
            self._process_scan_queue()
            return

        if summary.violation_count == 0:
            QMessageBox.information(self, "Tarama Tamamlandı",
                                    "İhlal tespit edilmedi.")

    def _on_scan_error(self, msg: str):
        if self._progress_dialog:
            self._progress_dialog.close()
        QMessageBox.critical(self, "Tarama Hatası", f"Hata:\n{msg}")
        self._btn_scan.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_pause.setText("  Duraklat")
        self._btn_stop.setEnabled(False)
        self._btn_load.setEnabled(True)
        self._update_status(f"Hata: {msg}")

    # ─────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────

    def _check_disk_space(self, src_path: str, dst_path: str) -> bool:
        """Hedef diskte yeterli alan var mı kontrol et."""
        import shutil
        try:
            src_size = Path(src_path).stat().st_size
            dst_dir = Path(dst_path).parent
            free = shutil.disk_usage(dst_dir).free
            # Kaynak dosyanın 1.2 katı alan gerekiyor (codec overhead)
            required = int(src_size * 1.2)
            if free < required:
                free_mb = free // (1024 * 1024)
                req_mb = required // (1024 * 1024)
                QMessageBox.critical(
                    self,
                    "Yetersiz Disk Alanı",
                    f"Hedef diskte yeterli alan yok.\n\n"
                    f"Gerekli: ~{req_mb} MB\n"
                    f"Mevcut: {free_mb} MB\n\n"
                    f"Farklı bir konum seçin veya disk alanı açın."
                )
                return False
        except OSError:
            pass  # Boyut alınamazsa devam et
        return True

    def _start_export(self):
        selected = self._notif_panel.get_selected()
        if not selected:
            QMessageBox.warning(self, "Seçim Gerekli",
                                "Sansürlenecek ihlalleri sağ panelden işaretleyin.")
            return

        src = Path(self._video_path)
        default_name = src.stem + "_sansurlu" + src.suffix
        dst, _ = QFileDialog.getSaveFileName(
            self, "Sansürlü Videoyu Kaydet",
            str(src.parent / default_name),
            "Video Dosyaları (*.mp4 *.avi)"
        )
        if not dst:
            return

        if not self._check_disk_space(self._video_path, dst):
            return

        for rec in selected:
            self._store.update_selection(rec.id, True)

        blur = self._config.get("export", {}).get("blur_intensity", "high")
        all_records = self._notif_panel.get_all_records()

        self._progress_dialog = ProgressDialog("Video export ediliyor...", self)
        self._progress_dialog.show()

        self._export_engine = ExportEngine(self._video_path, dst, all_records, blur)
        self._export_engine.progress_updated.connect(self._on_export_progress)
        self._export_engine.export_completed.connect(self._on_export_completed)
        self._export_engine.export_error.connect(self._on_export_error)
        self._export_engine.start()
        self._update_status("Export başlatıldı...")

    def _on_export_progress(self, current: int, total: int):
        if self._progress_dialog:
            self._progress_dialog.update_progress(current, total)

    def _on_export_completed(self, output_path: str):
        if self._progress_dialog:
            self._progress_dialog.finish()
            self._progress_dialog.close()
        QMessageBox.information(self, "Export Tamamlandı",
                                f"Sansürlü video kaydedildi:\n{output_path}")
        self._update_status(f"Export tamamlandı: {Path(output_path).name}")

    def _on_export_error(self, msg: str):
        if self._progress_dialog:
            self._progress_dialog.close()
        QMessageBox.critical(self, "Export Hatası", f"Export hatası:\n{msg}")
        self._update_status(f"Export hatası: {msg}")

    def _write_violation_report(self):
        if not self._video_path:
            return
        records = self._notif_panel.get_all_records()
        video = Path(self._video_path)
        report_path = video.parent / (video.stem + "_ihlal_raporu.txt")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"Video: {video.name}\n")
                f.write(f"Toplam ihlal: {len(records)}\n")
                f.write("-" * 40 + "\n")
                if not records:
                    f.write("İhlal tespit edilmedi.\n")
                else:
                    for rec in records:
                        f.write(f"{rec.timestamp_str}  -  {rec.category.value}  (%{rec.confidence*100:.0f})\n")
        except OSError as e:
            self._update_status(f"Rapor yazılamadı: {e}")
            return
        self._update_status(
            f"Tarama tamamlandı  —  {len(records)} ihlal  |  Rapor: {report_path.name}"
        )

    # ─────────────────────────────────────────
    # Watch Folder
    # ─────────────────────────────────────────

    def _toggle_watch_panel(self, checked: bool):
        self._watch_panel.setVisible(checked)
        if checked:
            self._act_watch_toggle.setText("  Watch Folder  ●  Açık")
            self._lbl_watch_status.setText("Watch Folder: Bekleniyor  ")
        else:
            self._act_watch_toggle.setText("  Watch Folder  ●  Kapalı")
            self._lbl_watch_status.setText("")
            if self._watch_panel._service:
                self._watch_panel._service.stop()

    def _on_watch_video_detected(self, path: str):
        self._load_video(path)
        self._lbl_watch_status.setText(f"Watch: {Path(path).name}  ")
        self._update_status(f"Watch Folder: {Path(path).name} algılandı, taranıyor...")
        self._start_scan()

    def _on_scan_folder_requested(self, paths: list):
        """Klasördeki tüm videoları sırayla tara."""
        if not paths:
            return
        self._scan_queue = paths.copy()
        self._update_status(f"Toplu tarama: {len(self._scan_queue)} video kuyruğa alındı.")
        self._process_scan_queue()

    def _process_scan_queue(self):
        """Kuyruktaki bir sonraki videoyu yükleyip tara."""
        if not self._scan_queue:
            self._update_status("Toplu tarama tamamlandı.")
            self._lbl_watch_status.setText("")
            return
        path = self._scan_queue.pop(0)
        remaining = len(self._scan_queue)
        self._lbl_watch_status.setText(f"Kuyruk: {remaining} video kaldı  ")
        self._load_video(path)
        self._start_scan()

    # ─────────────────────────────────────────
    # Ayarlar
    # ─────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self._config, self)
        if dlg.exec():
            updates = dlg.get_config()
            for key, val in updates.items():
                if isinstance(val, dict) and key in self._config:
                    self._config[key].update(val)
                else:
                    self._config[key] = val
            save_config(self._config)
            self._update_status("Ayarlar kaydedildi.")

    # ─────────────────────────────────────────
    # Drag & Drop
    # ─────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile():
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if is_video_file(path):
                self._load_video(path)
            else:
                QMessageBox.warning(self, "Desteklenmeyen Format",
                                    "Lütfen geçerli bir video dosyası sürükleyin.")

    # ─────────────────────────────────────────
    # Yardımcılar
    # ─────────────────────────────────────────

    def _update_status(self, msg: str):
        self._lbl_status_left.setText(f"  {msg}")

    def closeEvent(self, event):
        if self._scan_engine and self._scan_engine.isRunning():
            self._scan_engine.cancel()
            self._scan_engine.wait(3000)
        if self._export_engine and self._export_engine.isRunning():
            self._export_engine.cancel()
            self._export_engine.wait(3000)
        if self._watch_panel._service:
            self._watch_panel._service.stop()
        self._store.close()
        event.accept()
