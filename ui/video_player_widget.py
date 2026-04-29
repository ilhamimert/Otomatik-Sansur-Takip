import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton, QSizePolicy, QFrame
)

from ai.frame_processor import draw_detections, frame_to_qimage
from core.violation_store import ViolationRecord
from utils.time_utils import frame_to_str, seconds_to_str


class VideoLabel(QLabel):
    """Video karelerini gösterir. Aspect ratio korunur."""

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(480, 270)
        self._pixmap = None
        self.setStyleSheet("background-color: #000000;")

    def set_frame(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._pixmap is None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#000000"))
            painter.setPen(QColor("#333355"))
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Video yükleyin veya sürükleyin")
            return

        painter = QPainter(self)
        scaled = self._pixmap.scaled(self.size(),
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class VideoPlayerWidget(QWidget):
    seek_requested = pyqtSignal(float)   # seconds

    def __init__(self):
        super().__init__()
        self._cap: cv2.VideoCapture | None = None
        self._fps = 25.0
        self._total_frames = 0
        self._current_frame = 0
        self._playing = False
        self._active_violations: list[ViolationRecord] = []
        self._show_bbox = True

        self._timer = QTimer()
        self._timer.timeout.connect(self._next_frame)

        self._build_ui()

    # ── Public API ──

    def load_video(self, path: str):
        if self._cap:
            self._cap.release()
        self._cap = cv2.VideoCapture(path)
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 25.0
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._current_frame = 0
        self._slider.setMaximum(max(1, self._total_frames - 1))
        self._playing = False
        self._show_frame(0)
        self._update_time_label()

    def seek_to_second(self, sec: float):
        frame_no = int(sec * self._fps)
        self._seek(frame_no)

    def set_active_violations(self, violations: list[ViolationRecord]):
        self._active_violations = violations
        self._show_frame(self._current_frame)

    def set_show_bbox(self, show: bool):
        self._show_bbox = show
        self._show_frame(self._current_frame)

    # ── UI ──

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._video_label = VideoLabel()
        layout.addWidget(self._video_label)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self._btn_back = QPushButton("⏮")
        self._btn_play = QPushButton("▶")
        self._btn_fwd = QPushButton("⏭")
        for btn in (self._btn_back, self._btn_play, self._btn_fwd):
            btn.setFixedWidth(40)

        self._btn_back.clicked.connect(self._step_back)
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_fwd.clicked.connect(self._step_fwd)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1)
        self._slider.sliderMoved.connect(self._on_slider_moved)

        self._lbl_time = QLabel("00:00 / 00:00")
        self._lbl_time.setObjectName("label_time")
        self._lbl_time.setFixedWidth(130)

        controls.addWidget(self._btn_back)
        controls.addWidget(self._btn_play)
        controls.addWidget(self._btn_fwd)
        controls.addWidget(self._slider, stretch=1)
        controls.addWidget(self._lbl_time)
        layout.addLayout(controls)

    # ── Playback ──

    def _toggle_play(self):
        if not self._cap:
            return
        self._playing = not self._playing
        if self._playing:
            interval = max(1, int(1000 / self._fps))
            self._timer.start(interval)
            self._btn_play.setText("⏸")
        else:
            self._timer.stop()
            self._btn_play.setText("▶")

    def _next_frame(self):
        if self._cap is None:
            return
        ret, frame = self._cap.read()
        if not ret:
            self._timer.stop()
            self._playing = False
            self._btn_play.setText("▶")
            return
        self._current_frame = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        self._render_frame(frame)
        self._slider.setValue(self._current_frame)
        self._update_time_label()

    def _step_back(self):
        self._seek(max(0, self._current_frame - int(self._fps)))

    def _step_fwd(self):
        self._seek(min(self._total_frames - 1, self._current_frame + int(self._fps)))

    def _seek(self, frame_no: int):
        if not self._cap:
            return
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        self._current_frame = frame_no
        self._show_frame(frame_no)
        self._slider.setValue(frame_no)
        self._update_time_label()

    def _on_slider_moved(self, value: int):
        self._seek(value)

    def _show_frame(self, frame_no: int):
        if not self._cap:
            return
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = self._cap.read()
        if not ret:
            return
        self._current_frame = frame_no
        self._render_frame(frame)

    def _render_frame(self, frame: np.ndarray):
        if self._show_bbox:
            nearby = [v for v in self._active_violations
                      if abs(v.frame_number - self._current_frame) <= 3]
            if nearby:
                from ai.detector import Detection
                dets = [Detection(v.label, v.category, v.confidence, v.bbox) for v in nearby]
                frame = draw_detections(frame, dets)

        qimg = frame_to_qimage(frame)
        self._video_label.set_frame(QPixmap.fromImage(qimg))

    def _update_time_label(self):
        cur = seconds_to_str(self._current_frame / self._fps) if self._fps > 0 else "00:00"
        tot = seconds_to_str(self._total_frames / self._fps) if self._fps > 0 else "00:00"
        self._lbl_time.setText(f"{cur} / {tot}")
