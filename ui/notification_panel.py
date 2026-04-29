from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QCheckBox, QFrame
)

from ai.label_map import CATEGORY_HEX
from core.violation_store import ViolationRecord, ViolationStore


class ViolationItemWidget(QWidget):
    selection_changed = pyqtSignal(int, bool)   # (record_id, selected)
    jump_requested = pyqtSignal(float)           # timestamp_sec

    def __init__(self, record: ViolationRecord):
        super().__init__()
        self.record = record
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # Thumbnail
        thumb_label = QLabel()
        thumb_label.setFixedSize(80, 60)
        if record := self.record:
            if record.thumbnail:
                pix = QPixmap()
                pix.loadFromData(record.thumbnail)
                thumb_label.setPixmap(pix.scaled(80, 60, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                thumb_label.setStyleSheet("background-color: #12122a;")

        # Info
        info = QVBoxLayout()
        info.setSpacing(2)

        color = CATEGORY_HEX.get(self.record.category, "#ffffff")
        cat_label = QLabel(f'<span style="color:{color};font-weight:700;">'
                           f'{self.record.category.value}</span>')

        time_label = QLabel(f"⏱ {self.record.timestamp_str}  |  "
                            f"<span style='color:#aaa;'>{self.record.confidence:.0%}</span>")
        time_label.setTextFormat(Qt.TextFormat.RichText)

        lbl_label = QLabel(f"<span style='color:#666;font-size:11px;'>{self.record.label}</span>")
        lbl_label.setTextFormat(Qt.TextFormat.RichText)

        info.addWidget(cat_label)
        info.addWidget(time_label)
        info.addWidget(lbl_label)

        # Checkbox + jump
        right = QVBoxLayout()
        right.setSpacing(4)

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(self.record.is_selected)
        self._checkbox.stateChanged.connect(
            lambda s: self.selection_changed.emit(
                self.record.id, s == Qt.CheckState.Checked.value))

        btn_jump = QPushButton("↗")
        btn_jump.setFixedSize(28, 28)
        btn_jump.setToolTip("Bu kareye git")
        btn_jump.clicked.connect(lambda: self.jump_requested.emit(self.record.timestamp_sec))

        right.addWidget(self._checkbox, alignment=Qt.AlignmentFlag.AlignHCenter)
        right.addWidget(btn_jump, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(thumb_label)
        layout.addLayout(info, stretch=1)
        layout.addLayout(right)


class NotificationPanel(QWidget):
    violation_clicked = pyqtSignal(float)  # seek to seconds

    def __init__(self, store: ViolationStore):
        super().__init__()
        self._store = store
        self._records: list[ViolationRecord] = []
        self._build_ui()

    # ── Public API ──

    def add_violation(self, record: ViolationRecord):
        self._records.append(record)
        self._add_item(record)
        self._update_summary()

    def clear(self):
        self._records.clear()
        self._list.clear()
        self._update_summary()

    def get_selected(self) -> list[ViolationRecord]:
        return [r for r in self._records if r.is_selected]

    def get_all_records(self) -> list[ViolationRecord]:
        return list(self._records)

    def select_all(self):
        for rec in self._records:
            rec.is_selected = True
            self._store.update_selection(rec.id, True)
        self._refresh_items()

    def deselect_all(self):
        for rec in self._records:
            rec.is_selected = False
            self._store.update_selection(rec.id, False)
        self._refresh_items()

    # ── UI ──

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Başlık
        title = QLabel("📋  İHLAL BİLDİRİMLERİ")
        title.setObjectName("label_title")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #0f3460;")
        layout.addWidget(sep)

        # Liste
        self._list = QListWidget()
        self._list.setSpacing(2)
        self._list.setUniformItemSizes(False)
        layout.addWidget(self._list, stretch=1)

        # Özet
        self._lbl_summary = QLabel("Henüz ihlal bulunamadı.")
        self._lbl_summary.setObjectName("label_status")
        self._lbl_summary.setWordWrap(True)
        layout.addWidget(self._lbl_summary)

        # Alt butonlar
        btn_row = QHBoxLayout()
        self._btn_all = QPushButton("Tümünü Seç")
        self._btn_none = QPushButton("Seçimi Temizle")
        self._btn_all.clicked.connect(self.select_all)
        self._btn_none.clicked.connect(self.deselect_all)
        btn_row.addWidget(self._btn_all)
        btn_row.addWidget(self._btn_none)
        layout.addLayout(btn_row)

    def _add_item(self, record: ViolationRecord):
        item_widget = ViolationItemWidget(record)
        item_widget.selection_changed.connect(self._on_selection_changed)
        item_widget.jump_requested.connect(self.violation_clicked)

        list_item = QListWidgetItem(self._list)
        list_item.setSizeHint(item_widget.sizeHint())
        self._list.addItem(list_item)
        self._list.setItemWidget(list_item, item_widget)

    def _refresh_items(self):
        self._list.clear()
        for rec in self._records:
            self._add_item(rec)

    def _on_selection_changed(self, record_id: int, selected: bool):
        for rec in self._records:
            if rec.id == record_id:
                rec.is_selected = selected
                self._store.update_selection(record_id, selected)
                break
        self._update_summary()

    def _update_summary(self):
        total = len(self._records)
        selected = sum(1 for r in self._records if r.is_selected)
        if total == 0:
            self._lbl_summary.setText("Henüz ihlal bulunamadı.")
        else:
            self._lbl_summary.setText(
                f"Toplam: <b>{total}</b> ihlal  |  Seçili: <b>{selected}</b> ihlal")
        self._lbl_summary.setTextFormat(Qt.TextFormat.RichText)
