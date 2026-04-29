from __future__ import annotations

import cv2
import numpy as np
import tempfile
import os
from loguru import logger

# NudeNet tespit eşiği
CONFIDENCE_THRESHOLD = 0.35

# Tespit edilecek sınıflar (hassas içerik)
SENSITIVE_CLASSES = {
    "EXPOSED_ANUS",
    "EXPOSED_ARMPITS",
    "EXPOSED_BELLY",
    "EXPOSED_BREAST_F",
    "EXPOSED_BUTTOCKS",
    "EXPOSED_FEET",
    "EXPOSED_GENITALIA_F",
    "EXPOSED_GENITALIA_M",
    "EXPOSED_BREAST_M",
}

# Yayın için sansürlenmesi gerekenler
BROADCAST_SENSITIVE = {
    "EXPOSED_BREAST_F",
    "EXPOSED_GENITALIA_F",
    "EXPOSED_GENITALIA_M",
    "EXPOSED_ANUS",
    "EXPOSED_BUTTOCKS",
    "BUTTOCKS_COVERED",
    "EXPOSED_BELLY",
    "BELLY_EXPOSED",
    "ARMPITS_EXPOSED",
}


class NudeNetDetector:
    """NudeNet tabanlı uygunsuz içerik tespiti. Thread-safe Singleton."""

    _instance = None
    _detector = None
    _lock = __import__("threading").Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def load(self):
        with self._lock:
            if self._detector is not None:
                return self
            try:
                from nudenet import NudeDetector
                self._detector = NudeDetector()
                logger.info("NudeNet yuklendi.")
            except Exception as e:
                logger.warning(f"NudeNet yuklenemedi: {e}")
        return self

    def detect(self, frame: np.ndarray, conf: float = CONFIDENCE_THRESHOLD) -> list[dict]:
        """
        Frame üzerinde uygunsuz içerik tespiti.
        Returns: [{'label': str, 'confidence': float, 'bbox': (x1,y1,x2,y2)}]
        """
        if self._detector is None:
            return []

        tmp = tempfile.mktemp(suffix=".jpg")
        try:
            cv2.imwrite(tmp, frame)
            results = self._detector.detect(tmp)
            detections = []
            for r in results:
                label = r.get("class", "")
                score = r.get("score", 0.0)
                if label in BROADCAST_SENSITIVE and score >= conf:
                    box = r.get("box", [0, 0, 0, 0])
                    x1, y1, w, h = box
                    detections.append({
                        "label": "nudity",
                        "nudenet_class": label,
                        "confidence": score,
                        "bbox": (int(x1), int(y1), int(x1 + w), int(y1 + h)),
                    })
            return detections
        except Exception as e:
            logger.error(f"NudeNet tespit hatasi: {e}")
            return []
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    @property
    def is_loaded(self) -> bool:
        return self._detector is not None
