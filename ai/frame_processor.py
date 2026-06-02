from __future__ import annotations
import cv2
import numpy as np
from .label_map import CATEGORY_COLORS


def draw_detections(frame: np.ndarray, detections) -> np.ndarray:
    """Bounding box ve etiket çiz. Orijinal frame'i değiştirmez."""
    out = frame.copy()
    for det in detections:
        color = CATEGORY_COLORS.get(det.category, (0, 255, 0))
        x1, y1, x2, y2 = det.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label_text = f"{det.category.value} {det.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(out, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(out, label_text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def apply_blur(frame: np.ndarray, bbox: tuple, intensity: str = "high") -> np.ndarray:
    """Verilen bbox bölgesine Gaussian blur uygula."""
    kernels = {"low": (21, 21), "medium": (35, 35), "high": (51, 51)}
    ksize = kernels.get(intensity, (51, 51))
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return frame
    out = frame.copy()
    roi = out[y1:y2, x1:x2]
    out[y1:y2, x1:x2] = cv2.GaussianBlur(roi, ksize, 0)
    return out


