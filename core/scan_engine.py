from __future__ import annotations
import cv2
import numpy as np
from dataclasses import dataclass
from PyQt6.QtCore import QThread, pyqtSignal
from loguru import logger

from ai.model_manager import ModelManager
from ai.detector import Detector
from ai.label_map import ViolationCategory
from ai.nudenet_detector import NudeNetDetector
from ai.vision_verifier import VisionVerifier
from ai.clip_verifier import ClipVerifier
from core.violation_store import ViolationRecord, ViolationStore
from utils.time_utils import frame_to_seconds, frame_to_str
from utils.video_utils import get_video_info, open_capture


@dataclass
class ScanConfig:
    frame_skip: int = 5
    confidence: float = 0.45
    confirm_window: int = 2
    cpu_sleep_ms: int = 10
    active_categories: set | None = None
    model_config: dict = None
    verifier_mode: str = "none"  # "none" | "clip" | "moondream"
    motion_threshold: int = 800  # 0 = hareket filtresi kapalı


def _build_verifier(mode: str):
    if mode == "clip":
        return ClipVerifier().load()
    if mode == "moondream":
        return VisionVerifier().load()
    return VisionVerifier()  # load() yok → pass-through


@dataclass
class ScanSummary:
    total_frames: int
    scanned_frames: int
    violation_count: int
    duration_sec: float


class ScanEngine(QThread):
    violation_found = pyqtSignal(object)      # ViolationRecord
    progress_updated = pyqtSignal(int, int)   # (current_frame, total_frames)
    scan_completed = pyqtSignal(object)       # ScanSummary
    scan_error = pyqtSignal(str)

    def __init__(self, video_path: str, config: ScanConfig, store: ViolationStore):
        super().__init__()
        self._video_path = video_path
        self._config = config
        self._store = store
        self._cancelled = False
        self._paused = False

    def cancel(self):
        self._cancelled = True
        self._paused = False  # pause'dan çık ki thread sonlanabilsin

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def is_paused(self) -> bool:
        return self._paused

    def run(self):
        try:
            self._scan()
        except Exception as exc:
            logger.exception(f"Tarama hatası: {exc}")
            self.scan_error.emit(str(exc))

    def _scan(self):
        info = get_video_info(self._video_path)
        fps = info["fps"]
        total = info["frame_count"]

        model_mgr = ModelManager()
        model = model_mgr.load(self._config.model_config or {})
        detector = Detector(model, self._config.confidence, self._config.active_categories)

        # NudeNet — nudity kategorisi aktifse yükle
        nudenet = None
        active = self._config.active_categories
        if active is None or ViolationCategory.NUDITY in active:
            nudenet = NudeNetDetector().load()
            if not nudenet.is_loaded:
                nudenet = None

        verifier = _build_verifier(self._config.verifier_mode)

        try:
            cap = open_capture(self._video_path)
        except ValueError as e:
            self.scan_error.emit(str(e))
            return

        frame_no = 0
        violation_count = 0
        skip = self._config.frame_skip
        motion_thresh = self._config.motion_threshold
        _prev_gray: np.ndarray | None = None
        # Silah confirm sayacı — kategori bazlı, bbox bağımsız
        _weapon_streak: int = 0
        WEAPON_CONFIRM = 10  # silah 10 ardışık tarama karesinde görünmeli
        # Saniye bazlı tekilleştirme: {(saniye, kategori)} → zaten kaydedildi
        # Saniye bazlı sayaç: {(saniye, kategori): kayıt_sayısı} — max 3
        _seen: dict[tuple, int] = {}
        MAX_PER_SEC = 3

        self._store.clear_for_video(self._video_path)

        while not self._cancelled:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_no % skip == 0:
                # Hareket filtresi — statik kareyi atla
                if motion_thresh > 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.resize(gray, (320, 180))
                    if _prev_gray is not None:
                        diff = cv2.absdiff(gray, _prev_gray)
                        motion_score = int(np.sum(diff > 25))
                        if motion_score < motion_thresh:
                            _prev_gray = gray
                            frame_no += 1
                            continue
                    _prev_gray = gray

                # YOLO tespiti
                detections = detector.detect(frame)
                if detections:
                    logger.debug(f"Kare {frame_no}: {len(detections)} tespit — "
                                 + ", ".join(f"{d.label}({d.confidence:.2f})" for d in detections))

                # Bu karede silah var mı?
                has_weapon = any(d.category == ViolationCategory.WEAPON for d in detections)
                if has_weapon:
                    _weapon_streak += 1
                else:
                    _weapon_streak = 0

                current_sec = int(frame_to_seconds(frame_no, fps))

                for det in detections:
                    if not verifier.verify(frame, det.bbox, det.category):
                        logger.debug(f"Kare {frame_no}: REDDED → {det.label}({det.confidence:.2f})")
                        continue

                    # Silah için streak kontrolü
                    if det.category == ViolationCategory.WEAPON:
                        if _weapon_streak < WEAPON_CONFIRM:
                            logger.debug(f"Kare {frame_no}: silah streak {_weapon_streak}/{WEAPON_CONFIRM} — bekliyor")
                            continue

                    # Aynı saniyede aynı kategoriden max 3 kayıt
                    seen_key = (current_sec, det.category)
                    if _seen.get(seen_key, 0) >= MAX_PER_SEC:
                        continue
                    _seen[seen_key] = _seen.get(seen_key, 0) + 1

                    ts = frame_to_seconds(frame_no, fps)
                    ts_str = frame_to_str(frame_no, fps)
                    thumb = self._make_thumbnail(frame, det.bbox)
                    rec = ViolationRecord(
                        video_path=self._video_path,
                        frame_number=frame_no,
                        timestamp_sec=ts,
                        timestamp_str=ts_str,
                        category=det.category,
                        label=det.label,
                        confidence=det.confidence,
                        bbox=det.bbox,
                        thumbnail=thumb,
                    )
                    self._store.save(rec)
                    violation_count += 1
                    self.violation_found.emit(rec)

                # NudeNet tespiti
                if nudenet:
                    for nd in nudenet.detect(frame, self._config.confidence):
                        if not verifier.verify(frame, nd["bbox"], ViolationCategory.NUDITY):
                            continue

                        seen_key = (current_sec, ViolationCategory.NUDITY)
                        if _seen.get(seen_key, 0) >= MAX_PER_SEC:
                            continue
                        _seen[seen_key] = _seen.get(seen_key, 0) + 1

                        ts = frame_to_seconds(frame_no, fps)
                        ts_str = frame_to_str(frame_no, fps)
                        thumb = self._make_thumbnail(frame, nd["bbox"])
                        rec = ViolationRecord(
                            video_path=self._video_path,
                            frame_number=frame_no,
                            timestamp_sec=ts,
                            timestamp_str=ts_str,
                            category=ViolationCategory.NUDITY,
                            label=nd["nudenet_class"],
                            confidence=nd["confidence"],
                            bbox=nd["bbox"],
                            thumbnail=thumb,
                        )
                        self._store.save(rec)
                        violation_count += 1
                        self.violation_found.emit(rec)

            frame_no += 1
            if frame_no % 30 == 0:
                self.progress_updated.emit(frame_no, total)

            if self._config.cpu_sleep_ms > 0:
                self.msleep(self._config.cpu_sleep_ms)

            # Duraklatma döngüsü
            while self._paused and not self._cancelled:
                self.msleep(100)

        cap.release()
        self.progress_updated.emit(total, total)

        summary = ScanSummary(
            total_frames=total,
            scanned_frames=total // skip,
            violation_count=violation_count,
            duration_sec=info["duration_sec"],
        )
        self.scan_completed.emit(summary)

    def _make_thumbnail(self, frame: np.ndarray, bbox: tuple) -> bytes:
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1 - 10), max(0, y1 - 10)
        x2, y2 = min(frame.shape[1], x2 + 10), min(frame.shape[0], y2 + 10)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return b""
        crop = cv2.resize(crop, (80, 60))
        _, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return buf.tobytes()
