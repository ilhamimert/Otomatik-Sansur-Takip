from __future__ import annotations
import cv2
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from loguru import logger

from ai.frame_processor import apply_blur
from core.violation_store import ViolationRecord
from utils.video_utils import get_video_info, choose_writer_fourcc, open_capture

# Tespit edilen kare etrafında kaç kare blur uygulansın (frame_skip'in yarısı)
BLUR_WINDOW = 8


class ExportEngine(QThread):
    progress_updated = pyqtSignal(int, int)
    export_completed = pyqtSignal(str)
    export_error = pyqtSignal(str)

    def __init__(self, video_path: str, output_path: str,
                 violations: list[ViolationRecord], blur_intensity: str = "high"):
        super().__init__()
        self._src = video_path
        self._dst = output_path
        self._violations = violations
        self._intensity = blur_intensity
        self._cancelled = False

        # frame_no → list[bbox]
        # Tespit edilen kare ± BLUR_WINDOW kadar genişlet
        self._blur_map: dict[int, list[tuple]] = {}
        for v in violations:
            if not v.is_selected:
                continue
            for offset in range(-BLUR_WINDOW, BLUR_WINDOW + 1):
                fn = v.frame_number + offset
                if fn >= 0:
                    self._blur_map.setdefault(fn, []).append(v.bbox)

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._export()
        except Exception as exc:
            logger.exception(f"Export hatası: {exc}")
            self.export_error.emit(str(exc))

    def _export(self):
        info = get_video_info(self._src)
        fps = info["fps"]
        w, h = info["width"], info["height"]
        total = info["frame_count"]

        fourcc, ext = choose_writer_fourcc()
        dst_path = str(Path(self._dst).with_suffix(ext))
        writer = cv2.VideoWriter(dst_path, fourcc, fps, (w, h))
        if not writer.isOpened():
            self.export_error.emit(f"Video yazıcı açılamadı: {dst_path}")
            return

        try:
            cap = open_capture(self._src)
        except ValueError as e:
            self.export_error.emit(str(e))
            return
        frame_no = 0

        while not self._cancelled:
            ret, frame = cap.read()
            if not ret:
                break

            bboxes = self._blur_map.get(frame_no, [])
            for bbox in bboxes:
                frame = apply_blur(frame, bbox, self._intensity)

            writer.write(frame)
            frame_no += 1

            if frame_no % 30 == 0:
                self.progress_updated.emit(frame_no, total)

        cap.release()
        writer.release()

        if self._cancelled:
            Path(dst_path).unlink(missing_ok=True)
            return

        self.progress_updated.emit(total, total)
        self.export_completed.emit(dst_path)
        logger.info(f"Export tamamlandı: {dst_path}")
