"""
Servis modu için PyQt6 bağımsız tarama motoru.
ScanEngine mantığını thread'de çalıştırır, sonuçları callback ile bildirir.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from loguru import logger

from ai.detector import Detector
from ai.label_map import ViolationCategory
from ai.model_manager import ModelManager
from ai.nudenet_detector import NudeNetDetector
from utils.time_utils import frame_to_seconds, frame_to_str
from utils.video_utils import get_video_info, open_capture



@dataclass
class ScanResult:
    timestamp_str: str
    timestamp_sec: float
    category: ViolationCategory
    label: str
    confidence: float
    frame_number: int
    thumbnail_path: str = ""


@dataclass
class ScanReport:
    video_path: str
    video_name: str
    duration_sec: float
    total_frames: int
    scanned_frames: int
    violations: list[ScanResult] = field(default_factory=list)
    error: str = ""


class ScanWorker:
    """
    Tek bir videoyu tarar. Thread-safe, callback tabanlı.
    on_done(ScanReport) çağrıldığında tarama tamamdır.
    """

    WEAPON_CONFIRM = 10
    MAX_PER_SEC = 3

    THUMB_SIZE = (320, 180)
    MAX_THUMBS_PER_CATEGORY = 10

    def __init__(
        self,
        video_path: str,
        model_config: dict,
        active_categories: set[ViolationCategory] | None,
        confidence: float,
        frame_skip: int,
        motion_threshold: int,
        on_done: Callable[[ScanReport], None],
        on_progress: Callable[[str, int, int], None] | None = None,
        thumb_dir: str | None = None,
    ):
        self._video_path = video_path
        self._model_config = model_config
        self._active_categories = active_categories
        self._confidence = confidence
        self._frame_skip = frame_skip
        self._motion_threshold = motion_threshold
        self._on_done = on_done
        self._on_progress = on_progress
        self._thumb_dir = Path(thumb_dir) if thumb_dir else None
        self._cancelled = False
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancelled = True

    def join(self, timeout: float | None = None):
        if self._thread:
            self._thread.join(timeout)

    def _run(self):
        video_name = Path(self._video_path).name
        report = ScanReport(
            video_path=self._video_path,
            video_name=video_name,
            duration_sec=0.0,
            total_frames=0,
            scanned_frames=0,
        )

        try:
            info = get_video_info(self._video_path)
        except Exception as e:
            report.error = f"Video bilgisi alınamadı: {e}"
            self._on_done(report)
            return

        report.duration_sec = info["duration_sec"]
        report.total_frames = info["frame_count"]
        fps = info["fps"]

        try:
            cap = open_capture(self._video_path)
        except ValueError as e:
            report.error = str(e)
            self._on_done(report)
            return

        model_mgr = ModelManager()
        try:
            models = model_mgr.load(self._model_config)
        except RuntimeError as e:
            report.error = str(e)
            cap.release()
            self._on_done(report)
            return

        detector = Detector(models, self._confidence, self._active_categories)

        nudenet = None
        active = self._active_categories
        if active is None or ViolationCategory.NUDITY in active:
            nudenet = NudeNetDetector().load()
            if not nudenet.is_loaded:
                nudenet = None

        if self._thumb_dir:
            self._thumb_dir.mkdir(parents=True, exist_ok=True)

        frame_no = 0
        skip = self._frame_skip
        motion_thresh = self._motion_threshold
        _prev_gray: np.ndarray | None = None
        _weapon_streak: int = 0
        _seen: dict[tuple, int] = {}
        _thumb_counts: dict[str, int] = {}  # kategori başına kaydedilen thumbnail sayısı

        while not self._cancelled:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_no % skip == 0:
                report.scanned_frames += 1

                if motion_thresh > 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.resize(gray, (320, 180))
                    if _prev_gray is not None:
                        diff = cv2.absdiff(gray, _prev_gray)
                        if int(np.sum(diff > 25)) < motion_thresh:
                            _prev_gray = gray
                            frame_no += 1
                            continue
                    _prev_gray = gray

                detections = detector.detect(frame)
                has_weapon = any(d.category == ViolationCategory.WEAPON for d in detections)
                _weapon_streak = _weapon_streak + 1 if has_weapon else 0

                current_sec = int(frame_to_seconds(frame_no, fps))

                for det in detections:
                    if det.category == ViolationCategory.WEAPON:
                        if _weapon_streak < self.WEAPON_CONFIRM:
                            continue

                    seen_key = (current_sec, det.category)
                    if _seen.get(seen_key, 0) >= self.MAX_PER_SEC:
                        continue
                    _seen[seen_key] = _seen.get(seen_key, 0) + 1

                    thumb = self._save_thumbnail(
                        frame, frame_no, fps, det.category.name, _thumb_counts
                    )
                    report.violations.append(ScanResult(
                        timestamp_str=frame_to_str(frame_no, fps),
                        timestamp_sec=frame_to_seconds(frame_no, fps),
                        category=det.category,
                        label=det.label,
                        confidence=det.confidence,
                        frame_number=frame_no,
                        thumbnail_path=thumb,
                    ))

                if nudenet:
                    for nd in nudenet.detect(frame, self._confidence):
                        seen_key = (current_sec, ViolationCategory.NUDITY)
                        if _seen.get(seen_key, 0) >= self.MAX_PER_SEC:
                            continue
                        _seen[seen_key] = _seen.get(seen_key, 0) + 1

                        thumb = self._save_thumbnail(
                            frame, frame_no, fps, "NUDITY", _thumb_counts
                        )
                        report.violations.append(ScanResult(
                            timestamp_str=frame_to_str(frame_no, fps),
                            timestamp_sec=frame_to_seconds(frame_no, fps),
                            category=ViolationCategory.NUDITY,
                            label=nd["nudenet_class"],
                            confidence=nd["confidence"],
                            frame_number=frame_no,
                            thumbnail_path=thumb,
                        ))

            frame_no += 1
            if self._on_progress and frame_no % 60 == 0:
                self._on_progress(video_name, frame_no, report.total_frames)

        cap.release()
        self._on_done(report)

    def _save_thumbnail(
        self,
        frame: np.ndarray,
        frame_no: int,
        fps: float,
        category: str,
        counts: dict[str, int],
    ) -> str:
        if not self._thumb_dir:
            return ""
        if counts.get(category, 0) >= self.MAX_THUMBS_PER_CATEGORY:
            return ""
        try:
            ts = frame_to_str(frame_no, fps).replace(":", "-")
            filename = f"thumb_{ts}_{category.lower()}.jpg"
            path = self._thumb_dir / filename
            resized = cv2.resize(frame, self.THUMB_SIZE)
            cv2.imwrite(str(path), resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
            counts[category] = counts.get(category, 0) + 1
            return str(path)
        except Exception as e:
            logger.warning(f"Thumbnail kaydedilemedi: {e}")
            return ""