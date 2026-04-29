"""
AI Vision Guard — Etiketleme Aracı
PyQt6 tabanlı, YOLO formatında etiket üretir.

Kullanım:
  venv/Scripts/python.exe annotator.py

Kontroller:
  R          : Dikdörtgen çiz
  D / →      : Sonraki görsel
  A / ←      : Önceki görsel
  Del        : Seçili kutuyu sil
  Ctrl+Z     : Geri al
  Ctrl+S     : Kaydet
"""
from __future__ import annotations
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QFont,
    QKeySequence, QImage, QBrush, QShortcut
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QSplitter, QStatusBar, QFrame,
    QMessageBox, QProgressBar
)

LABELS = ["cigarette", "weapon", "alcohol", "blood", "nudity", "drug"]
CURRENT_LABEL = "cigarette"
IMG_DIR = Path("dataset/raw")
COLORS = {
    "cigarette": QColor(255, 107, 53),
    "weapon":    QColor(255, 230, 109),
    "alcohol":   QColor(78,  205, 196),
    "blood":     QColor(199, 125, 255),
    "nudity":    QColor(255, 59,  59),
    "drug":      QColor(150, 230, 161),
}


class BBox:
    def __init__(self, x1: int, y1: int, x2: int, y2: int, label: str = CURRENT_LABEL):
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)
        self.label = label

    def to_yolo(self, img_w: int, img_h: int) -> str:
        class_id = LABELS.index(self.label) if self.label in LABELS else 0
        cx = ((self.x1 + self.x2) / 2) / img_w
        cy = ((self.y1 + self.y2) / 2) / img_h
        w = (self.x2 - self.x1) / img_w
        h = (self.y2 - self.y1) / img_h
        return f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"

    def rect(self) -> QRect:
        return QRect(QPoint(self.x1, self.y1), QPoint(self.x2, self.y2))


class Canvas(QLabel):
    bbox_added = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setStyleSheet("background-color: #0A1628;")
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._pixmap: QPixmap | None = None
        self._img_w = 0
        self._img_h = 0
        self._bboxes: list[BBox] = []
        self._drawing = False
        self._start: QPoint | None = None
        self._current: QPoint | None = None
        self._offset = QPoint(0, 0)
        self._scale = 1.0
        self.active_label = CURRENT_LABEL

    def load_image(self, path: str, bboxes: list[BBox]):
        self._pixmap = QPixmap(path)
        self._img_w = self._pixmap.width()
        self._img_h = self._pixmap.height()
        self._bboxes = bboxes
        self._drawing = False
        self._start = None
        self._current = None
        self._calc_transform()
        self.update()

    def _calc_transform(self):
        if not self._pixmap:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        cw, ch = self.width(), self.height()
        scale_x = cw / pw
        scale_y = ch / ph
        self._scale = min(scale_x, scale_y)
        dw = int(pw * self._scale)
        dh = int(ph * self._scale)
        self._offset = QPoint((cw - dw) // 2, (ch - dh) // 2)

    def _to_img(self, pt: QPoint) -> QPoint:
        x = int((pt.x() - self._offset.x()) / self._scale)
        y = int((pt.y() - self._offset.y()) / self._scale)
        x = max(0, min(x, self._img_w))
        y = max(0, min(y, self._img_h))
        return QPoint(x, y)

    def _to_canvas(self, pt: QPoint) -> QPoint:
        x = int(pt.x() * self._scale) + self._offset.x()
        y = int(pt.y() * self._scale) + self._offset.y()
        return QPoint(x, y)

    def delete_last(self):
        if self._bboxes:
            self._bboxes.pop()
            self.update()

    def clear_all(self):
        self._bboxes.clear()
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._pixmap:
            self._drawing = True
            self._start = self._to_img(e.position().toPoint())

    def mouseMoveEvent(self, e):
        if self._drawing:
            self._current = self._to_img(e.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, e):
        if self._drawing and self._start and self._current:
            self._drawing = False
            b = BBox(self._start.x(), self._start.y(),
                     self._current.x(), self._current.y(),
                     label=self.active_label)
            if abs(b.x2 - b.x1) > 5 and abs(b.y2 - b.y1) > 5:
                self._bboxes.append(b)
                self.bbox_added.emit()
            self._start = None
            self._current = None
            self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0A1628"))

        if not self._pixmap:
            painter.setPen(QColor("#1E3A5A"))
            painter.setFont(QFont("Segoe UI", 13))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Görsel yükleniyor...")
            return

        self._calc_transform()
        scaled = self._pixmap.scaled(
            int(self._img_w * self._scale),
            int(self._img_h * self._scale),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(self._offset, scaled)

        # Kayıtlı bbox'lar
        for bbox in self._bboxes:
            color = COLORS.get(bbox.label, QColor(255, 107, 53))
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(color.red(), color.green(),
                                           color.blue(), 40)))
            tl = self._to_canvas(QPoint(bbox.x1, bbox.y1))
            br = self._to_canvas(QPoint(bbox.x2, bbox.y2))
            painter.drawRect(QRect(tl, br))

            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.fillRect(QRect(tl.x(), tl.y() - 18,
                                   len(bbox.label) * 8 + 8, 18),
                             QColor(color.red(), color.green(), color.blue(), 200))
            painter.drawText(tl.x() + 4, tl.y() - 4, bbox.label)

        # Çizilen bbox
        if self._drawing and self._start and self._current:
            pen = QPen(QColor("#1E6FD9"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(30, 111, 217, 30)))
            tl = self._to_canvas(self._start)
            br = self._to_canvas(self._current)
            painter.drawRect(QRect(tl, br))

    def resizeEvent(self, e):
        self._calc_transform()
        self.update()


class Annotator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Vision Guard — Etiketleme Aracı")
        self.resize(1200, 750)

        self._images: list[Path] = sorted(IMG_DIR.glob("*.jpg"))
        self._index = 0
        self._bboxes: dict[str, list[BBox]] = {}

        self._build_ui()
        self._build_shortcuts()
        self._load_existing_labels()

        if self._images:
            self._goto(0)
        else:
            QMessageBox.warning(self, "Görsel Yok",
                                f"dataset/raw/ klasöründe .jpg dosyası bulunamadı.")

    def _build_ui(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0A1628; color: #C8D6E8;
                                   font-family: 'Segoe UI'; font-size: 13px; }
            QPushButton { background: #0F2040; color: #8BA3C4; border: 1px solid #162840;
                          border-radius: 6px; padding: 7px 18px; }
            QPushButton:hover { background: #162840; color: #E8F0FC; }
            QPushButton#btn_primary { background: #1E6FD9; color: #fff;
                                      border: none; font-weight: 600; }
            QPushButton#btn_primary:hover { background: #2878E8; }
            QPushButton#btn_danger { background: #3A1820; color: #E05C5C;
                                     border: 1px solid #6A2030; }
            QListWidget { background: #060E1C; border: 1px solid #0F2040;
                          border-radius: 6px; }
            QListWidget::item { padding: 6px 10px; border-bottom: 1px solid #0F2040; }
            QListWidget::item:selected { background: #0F2040; color: #1E6FD9; }
            QProgressBar { background: #0F2040; border: none; border-radius: 3px;
                           height: 6px; }
            QProgressBar::chunk { background: #1E6FD9; border-radius: 3px; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Canvas
        self._canvas = Canvas()
        self._canvas.bbox_added.connect(self._on_bbox_added)
        splitter.addWidget(self._canvas)

        # Sağ panel
        right = QWidget()
        right.setFixedWidth(260)
        right.setStyleSheet("background: #060E1C; border-left: 1px solid #0F2040;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(10)

        # İlerleme
        lbl_prog = QLabel("İLERLEME")
        lbl_prog.setStyleSheet("color:#4A6080; font-size:11px; font-weight:600; letter-spacing:1px;")
        rl.addWidget(lbl_prog)

        self._lbl_progress = QLabel("0 / 0")
        self._lbl_progress.setStyleSheet("color:#FFFFFF; font-size:18px; font-weight:700;")
        rl.addWidget(self._lbl_progress)

        self._progress_bar = QProgressBar()
        rl.addWidget(self._progress_bar)

        self._lbl_labeled = QLabel("Etiketlenen: 0")
        self._lbl_labeled.setStyleSheet("color:#4ADE80; font-size:12px;")
        rl.addWidget(self._lbl_labeled)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #0F2040;")
        rl.addWidget(sep)

        # Etiket seçici
        lbl_sel = QLabel("ETİKET SEÇ")
        lbl_sel.setStyleSheet("color:#4A6080; font-size:11px; font-weight:600; letter-spacing:1px;")
        rl.addWidget(lbl_sel)

        self._label_buttons: dict[str, QPushButton] = {}
        label_colors = {
            "cigarette": "#FF6B35",
            "weapon":    "#FFE66D",
            "alcohol":   "#4ECDC4",
            "blood":     "#C77DFF",
            "nudity":    "#FF3B3B",
            "drug":      "#96E6A1",
        }
        for lbl in LABELS:
            btn = QPushButton(f"  {lbl.capitalize()}")
            btn.setCheckable(True)
            btn.setChecked(lbl == CURRENT_LABEL)
            color = label_colors.get(lbl, "#ffffff")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #0A1628; color: {color};
                    border: 1px solid {color}40;
                    border-radius: 6px; padding: 6px 12px;
                    text-align: left; font-size: 12px;
                }}
                QPushButton:checked {{
                    background: {color}25;
                    border: 1px solid {color};
                    font-weight: 700;
                }}
                QPushButton:hover {{ background: {color}15; }}
            """)
            btn.clicked.connect(lambda _, l=lbl: self._set_label(l))
            self._label_buttons[lbl] = btn
            rl.addWidget(btn)

        self._lbl_active = QLabel("Aktif: cigarette")
        self._lbl_active.setStyleSheet("color:#8BA3C4; font-size:11px;")
        rl.addWidget(self._lbl_active)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #0F2040;")
        rl.addWidget(sep2)

        # Mevcut kutular
        lbl_boxes = QLabel("MEVCUT KUTULAR")
        lbl_boxes.setStyleSheet("color:#4A6080; font-size:11px; font-weight:600; letter-spacing:1px;")
        rl.addWidget(lbl_boxes)

        self._box_list = QListWidget()
        self._box_list.setMaximumHeight(150)
        rl.addWidget(self._box_list)

        btn_del = QPushButton("Son Kutuyu Sil")
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self._delete_last)
        rl.addWidget(btn_del)

        btn_clear = QPushButton("Tüm Kutuları Temizle")
        btn_clear.setObjectName("btn_danger")
        btn_clear.clicked.connect(self._clear_all)
        rl.addWidget(btn_clear)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #0F2040;")
        rl.addWidget(sep3)

        # Navigasyon
        lbl_nav = QLabel("NAVİGASYON")
        lbl_nav.setStyleSheet("color:#4A6080; font-size:11px; font-weight:600; letter-spacing:1px;")
        rl.addWidget(lbl_nav)

        nav = QHBoxLayout()
        self._btn_prev = QPushButton("← Önceki")
        self._btn_next = QPushButton("Sonraki →")
        self._btn_prev.clicked.connect(self._prev)
        self._btn_next.clicked.connect(self._next)
        nav.addWidget(self._btn_prev)
        nav.addWidget(self._btn_next)
        rl.addLayout(nav)

        self._lbl_filename = QLabel("")
        self._lbl_filename.setStyleSheet("color:#4A6080; font-size:11px;")
        self._lbl_filename.setWordWrap(True)
        rl.addWidget(self._lbl_filename)

        rl.addStretch()

        # Kaydet
        btn_save = QPushButton("Kaydet (Ctrl+S)")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self._save_current)
        rl.addWidget(btn_save)

        # Bitir
        btn_done = QPushButton("Etiketlemeyi Bitir")
        btn_done.setObjectName("btn_primary")
        btn_done.clicked.connect(self._finish)
        rl.addWidget(btn_done)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        root.addWidget(splitter)

        # Status bar
        self._statusbar = QStatusBar()
        self._statusbar.setStyleSheet(
            "background:#060E1C; border-top:1px solid #0F2040; color:#4A6080; font-size:11px;")
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage(
            "R: Kutu çiz  |  D/→: Sonraki  |  A/←: Önceki  |  Del: Son kutuyu sil  |  Ctrl+S: Kaydet")

    def _build_shortcuts(self):
        QShortcut(QKeySequence("D"), self, self._next)
        QShortcut(QKeySequence("A"), self, self._prev)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._next)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._prev)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current)
        QShortcut(QKeySequence("Ctrl+Z"), self, self._delete_last)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._delete_last)

    def _load_existing_labels(self):
        for img in self._images:
            txt = img.with_suffix(".txt")
            if txt.exists():
                bboxes = []
                with open(txt) as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) == 5:
                            _, cx, cy, w, h = map(float, parts)
                            iw = QImage(str(img)).width()
                            ih = QImage(str(img)).height()
                            x1 = int((cx - w / 2) * iw)
                            y1 = int((cy - h / 2) * ih)
                            x2 = int((cx + w / 2) * iw)
                            y2 = int((cy + h / 2) * ih)
                            bboxes.append(BBox(x1, y1, x2, y2))
                self._bboxes[str(img)] = bboxes

    def _set_label(self, label: str):
        self._canvas.active_label = label
        self._lbl_active.setText(f"Aktif: {label}")
        for lbl, btn in self._label_buttons.items():
            btn.setChecked(lbl == label)

    def _goto(self, index: int):
        self._save_current()
        self._index = max(0, min(index, len(self._images) - 1))
        img = self._images[self._index]
        bboxes = self._bboxes.get(str(img), [])
        self._canvas.load_image(str(img), bboxes)
        self._bboxes[str(img)] = bboxes
        self._update_ui()

    def _update_ui(self):
        total = len(self._images)
        labeled = sum(1 for p in self._images
                      if p.with_suffix(".txt").exists() or
                      len(self._bboxes.get(str(p), [])) > 0)

        self._lbl_progress.setText(f"{self._index + 1} / {total}")
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(self._index + 1)
        self._lbl_labeled.setText(f"Etiketlenen: {labeled} görsel")
        self._lbl_filename.setText(self._images[self._index].name)
        self._btn_prev.setEnabled(self._index > 0)
        self._btn_next.setEnabled(self._index < total - 1)
        self._update_box_list()

    def _update_box_list(self):
        self._box_list.clear()
        img = self._images[self._index]
        for i, b in enumerate(self._bboxes.get(str(img), []), 1):
            item = QListWidgetItem(f"{i}. {b.label}  [{b.x1},{b.y1} → {b.x2},{b.y2}]")
            self._box_list.addItem(item)

    def _on_bbox_added(self):
        img = self._images[self._index]
        self._bboxes[str(img)] = self._canvas._bboxes
        self._update_box_list()
        self._save_current()

    def _save_current(self):
        if not self._images:
            return
        # Canvas henüz yüklenmemişse kaydetme
        if self._canvas._img_w == 0 or self._canvas._img_h == 0:
            return
        img = self._images[self._index]
        bboxes = self._bboxes.get(str(img), [])
        txt = img.with_suffix(".txt")
        if bboxes:
            lines = [b.to_yolo(self._canvas._img_w, self._canvas._img_h)
                     for b in bboxes]
            txt.write_text("\n".join(lines))
        else:
            txt.write_text("")
        self._update_ui()

    def _delete_last(self):
        self._canvas.delete_last()
        img = self._images[self._index]
        self._bboxes[str(img)] = self._canvas._bboxes
        self._update_box_list()

    def _clear_all(self):
        self._canvas.clear_all()
        img = self._images[self._index]
        self._bboxes[str(img)] = []
        self._update_box_list()

    def _prev(self):
        if self._index > 0:
            self._goto(self._index - 1)

    def _next(self):
        if self._index < len(self._images) - 1:
            self._goto(self._index + 1)
        else:
            self._save_current()
            self._statusbar.showMessage("Son görsel! Etiketlemeyi bitirmek için 'Bitir' butonuna basın.")

    def _finish(self):
        self._save_current()
        labeled = sum(1 for p in self._images if p.with_suffix(".txt").exists())
        QMessageBox.information(
            self, "Etiketleme Tamamlandı",
            f"{labeled} görsel etiketlendi.\n\n"
            f"Şimdi terminalde şunu çalıştırın:\n"
            f"  venv\\Scripts\\python.exe prepare_dataset.py\n"
            f"  venv\\Scripts\\python.exe train.py"
        )
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = Annotator()
    w.show()
    sys.exit(app.exec())
