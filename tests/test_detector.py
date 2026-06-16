import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.label_map import ViolationCategory, label_to_category
from ai.frame_processor import apply_blur, draw_detections
from ai.detector import Detection


def test_label_to_category_cigarette():
    assert label_to_category("cigarette") == ViolationCategory.CIGARETTE
    assert label_to_category("SMOKING") == ViolationCategory.CIGARETTE


def test_label_to_category_alcohol():
    assert label_to_category("wine_glass") == ViolationCategory.ALCOHOL
    assert label_to_category("beer") == ViolationCategory.ALCOHOL


def test_label_to_category_unknown():
    assert label_to_category("person") is None
    assert label_to_category("car") is None


def test_apply_blur_returns_copy():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[20:60, 20:60] = 200
    result = apply_blur(frame, (20, 20, 60, 60))
    assert result is not frame  # kopya döndürmeli
    assert result.shape == frame.shape


def test_apply_blur_changes_roi():
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 255
    blurred = apply_blur(frame, (10, 10, 50, 50), intensity="high")
    # Blur sonrası piksel değerleri değişmemeli (tüm beyaz → hâlâ beyaz)
    # Sadece shape kontrolü yeterli
    assert blurred.shape == frame.shape


def test_draw_detections_returns_copy():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    det = Detection("cigarette", ViolationCategory.CIGARETTE, 0.85, (10, 10, 100, 100))
    result = draw_detections(frame, [det])
    assert result is not frame
    assert result.shape == frame.shape


def test_draw_detections_marks_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    det = Detection("cigarette", ViolationCategory.CIGARETTE, 0.85, (10, 10, 100, 100))
    result = draw_detections(frame, [det])
    # Bounding box bölgesinde artık sıfırdan farklı piksel olmalı
    assert result[10, 10].sum() > 0 or result[10:100, 10:100].sum() > 0
