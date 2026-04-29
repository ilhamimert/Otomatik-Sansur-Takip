from __future__ import annotations
from typing import List, Optional, Set
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from loguru import logger
from .label_map import ViolationCategory, label_to_category


class Detection:
    __slots__ = ("label", "category", "confidence", "bbox")

    def __init__(self, label: str, category: ViolationCategory, confidence: float, bbox: tuple):
        self.label = label
        self.category = category
        self.confidence = confidence
        self.bbox = bbox  # (x1, y1, x2, y2) int


class Detector:
    # Model sınıflarına göre inference eşiği overrides
    # smooking: yüksek — çok yanlış pozitif üretiyor
    # weapon sınıfları: düşük — AK47/rifle gibi silahları yakalasın
    MODEL_CONF_OVERRIDES = {
        "smooking": 0.50,
    }

    # Bu sınıflar düşük confidence'da inference edilsin
    LOW_CONF_LABELS = {"grenade", "shotgun", "pistol", "rifle", "knife", "handgun", "gun"}
    LOW_CONF_VALUE = 0.50

    # Grenade yüksek eşikte filtrele (kafa ile karışıyor)
    GRENADE_MIN_CONF = 0.82

    def __init__(self, models: list, conf_threshold: float = 0.45,
                 active_categories: Optional[Set[ViolationCategory]] = None):
        if not isinstance(models, list):
            models = [models]
        self._models = models
        self._conf = conf_threshold
        self._active = active_categories
        self._executor = ThreadPoolExecutor(max_workers=len(models))

    def detect(self, frame: np.ndarray) -> List[Detection]:
        all_detections: List[Detection] = []
        seen_boxes: set = set()

        for model in self._models:
            try:
                detections = self._run_model(model, frame)
            except Exception as exc:
                logger.error(f"Model inference hatası: {exc}")
                continue
            for det in detections:
                box_key = (det.bbox[0] // 20, det.bbox[1] // 20,
                           det.bbox[2] // 20, det.bbox[3] // 20, det.category)
                if box_key not in seen_boxes:
                    seen_boxes.add(box_key)
                    all_detections.append(det)

        return all_detections

    def _run_model(self, model, frame: np.ndarray) -> List[Detection]:
        model_labels = {v.lower() for v in model.names.values()}

        # Silah modeli ise düşük eşikle infererce et
        is_weapon_model = bool(model_labels & self.LOW_CONF_LABELS)
        if is_weapon_model:
            infer_conf = self.LOW_CONF_VALUE
        else:
            infer_conf = self._conf
            for label_key, override_conf in self.MODEL_CONF_OVERRIDES.items():
                if label_key in model_labels:
                    infer_conf = override_conf
                    break

        try:
            results = model(frame, verbose=False, conf=infer_conf, imgsz=640)
        except Exception as exc:
            logger.error(f"Inference hatası: {exc}")
            return []

        detections: List[Detection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                label = result.names[int(box.cls[0])].lower()
                det_conf = float(box.conf[0])

                # Grenade kafa ile karışıyor — yüksek eşik uygula
                if label == "grenade" and det_conf < self.GRENADE_MIN_CONF:
                    continue

                # Genel eşik filtresi
                if det_conf < self._conf and label not in self.LOW_CONF_LABELS:
                    continue

                category = label_to_category(label)
                if category is None:
                    continue
                if self._active and category not in self._active:
                    continue

                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                detections.append(Detection(label, category, det_conf, (x1, y1, x2, y2)))

        return detections

    def __del__(self):
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
