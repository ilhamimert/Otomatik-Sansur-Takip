import sys
import os
import ctypes
from pathlib import Path

# Proje kökünü Python path'e ekle
sys.path.insert(0, str(Path(__file__).parent))

# HuggingFace cache'ini proje içine yönlendir (offline + transformers custom modül desteği)
_models_dir = str(Path(__file__).parent / "models")
os.environ.setdefault("HF_HOME", _models_dir)

# Windows görev çubuğunda Python ikonu yerine uygulama ikonunu göster
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CNBCTurk.AIVisionGuard")
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from utils.logger import setup_logger


def main():
    setup_logger("data/app.log")

    app = QApplication(sys.argv)
    app.setApplicationName("AI Vision Guard")
    app.setOrganizationName("CNBCTurk")
    app.setStyle("Fusion")

    # Uygulama ikonu (başlık çubuğu + görev çubuğu)
    icon_path = Path(__file__).parent / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Koyu tema yükle
    qss_path = Path(__file__).parent / "ui" / "styles" / "dark_theme.qss"
    if qss_path.exists():
        with open(qss_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    from ui.main_window import MainWindow
    window = MainWindow()
    window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
