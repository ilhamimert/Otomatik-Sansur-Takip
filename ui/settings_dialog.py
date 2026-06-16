from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QPushButton
)
from ai.label_map import ViolationCategory


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(380)
        self._config = config
        self._build_ui()
        self._load(config)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Tarama
        scan_group = QGroupBox("Tarama Ayarları")
        scan_form = QFormLayout(scan_group)

        self._spin_skip = QSpinBox()
        self._spin_skip.setRange(1, 30)
        self._spin_skip.setToolTip("Her N. kareyi tara. Artırdıkça hız artar, doğruluk azalır.")
        scan_form.addRow("Frame Atlama (N):", self._spin_skip)

        self._spin_conf = QDoubleSpinBox()
        self._spin_conf.setRange(0.1, 1.0)
        self._spin_conf.setSingleStep(0.05)
        self._spin_conf.setDecimals(2)
        scan_form.addRow("Güven Eşiği:", self._spin_conf)
        layout.addWidget(scan_group)

        # Kategoriler
        cat_group = QGroupBox("Aktif Kategoriler")
        cat_layout = QVBoxLayout(cat_group)
        self._cat_checks: dict[str, QCheckBox] = {}
        for cat in ViolationCategory:
            cb = QCheckBox(cat.value)
            self._cat_checks[cat.name] = cb
            cat_layout.addWidget(cb)
        layout.addWidget(cat_group)

        # AI Doğrulayıcı
        verifier_group = QGroupBox("AI Doğrulayıcı")
        verifier_form = QFormLayout(verifier_group)
        self._combo_verifier = QComboBox()
        self._combo_verifier.addItems(["Kapalı", "CLIP (hızlı ~20x)", "Moondream2 (derin)"])
        self._combo_verifier.setToolTip(
            "Kapalı: Tüm YOLO tespitleri kabul edilir (en hızlı).\n"
            "CLIP: Hızlı doğrulama, ~100-300ms/tespit.\n"
            "Moondream2: Derin analiz, ~5-10sn/tespit."
        )
        verifier_form.addRow("Doğrulayıcı:", self._combo_verifier)
        layout.addWidget(verifier_group)

        # Export
        exp_group = QGroupBox("Export Ayarları")
        exp_form = QFormLayout(exp_group)
        self._combo_blur = QComboBox()
        self._combo_blur.addItems(["Düşük", "Orta", "Yüksek"])
        exp_form.addRow("Blur Yoğunluğu:", self._combo_blur)
        layout.addWidget(exp_group)

        # Butonlar
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("Kaydet")
        btn_cancel = QPushButton("İptal")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _load(self, config: dict):
        scan = config.get("scan", {})
        self._spin_skip.setValue(scan.get("frame_skip", 5))
        self._spin_conf.setValue(scan.get("confidence_threshold", 0.45))

        cats = config.get("categories", {})
        for name, cb in self._cat_checks.items():
            cb.setChecked(cats.get(name.lower(), True))

        verifier_map = {"none": 0, "clip": 1, "moondream": 2}
        ai_cfg = config.get("ai", {})
        self._combo_verifier.setCurrentIndex(
            verifier_map.get(ai_cfg.get("verifier_mode", "none"), 0)
        )

        blur_map = {"low": 0, "medium": 1, "high": 2}
        exp = config.get("export", {})
        self._combo_blur.setCurrentIndex(blur_map.get(exp.get("blur_intensity", "high"), 2))

    def get_config(self) -> dict:
        blur_rev = {0: "low", 1: "medium", 2: "high"}
        verifier_rev = {0: "none", 1: "clip", 2: "moondream"}
        return {
            "scan": {
                "frame_skip": self._spin_skip.value(),
                "confidence_threshold": self._spin_conf.value(),
            },
            "categories": {
                name.lower(): cb.isChecked()
                for name, cb in self._cat_checks.items()
            },
            "ai": {
                "verifier_mode": verifier_rev[self._combo_verifier.currentIndex()],
            },
            "export": {
                "blur_intensity": blur_rev[self._combo_blur.currentIndex()],
            },
        }
