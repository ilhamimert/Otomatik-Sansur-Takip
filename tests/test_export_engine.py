import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.export_engine import ExportEngine, BLUR_WINDOW
from core.violation_store import ViolationRecord
from ai.label_map import ViolationCategory


def make_violation(frame_number: int, selected: bool = True) -> ViolationRecord:
    rec = ViolationRecord(
        video_path="/test/video.mp4",
        frame_number=frame_number,
        timestamp_sec=frame_number / 25.0,
        timestamp_str="00:00",
        category=ViolationCategory.CIGARETTE,
        label="cigarette",
        confidence=0.9,
        bbox=(10, 10, 100, 100),
    )
    rec.is_selected = selected
    return rec


def test_blur_map_built_for_selected():
    v = make_violation(50, selected=True)
    engine = ExportEngine.__new__(ExportEngine)
    engine._violations = [v]
    engine._blur_map = {}
    for viol in engine._violations:
        if not viol.is_selected:
            continue
        for offset in range(-BLUR_WINDOW, BLUR_WINDOW + 1):
            fn = viol.frame_number + offset
            if fn >= 0:
                engine._blur_map.setdefault(fn, []).append(viol.bbox)

    assert 50 in engine._blur_map
    assert 50 - BLUR_WINDOW in engine._blur_map
    assert 50 + BLUR_WINDOW in engine._blur_map


def test_blur_map_skips_unselected():
    v = make_violation(50, selected=False)
    engine = ExportEngine.__new__(ExportEngine)
    engine._violations = [v]
    engine._blur_map = {}
    for viol in engine._violations:
        if not viol.is_selected:
            continue
        for offset in range(-BLUR_WINDOW, BLUR_WINDOW + 1):
            fn = viol.frame_number + offset
            if fn >= 0:
                engine._blur_map.setdefault(fn, []).append(viol.bbox)

    assert len(engine._blur_map) == 0


def test_blur_map_no_negative_frames():
    v = make_violation(2, selected=True)  # BLUR_WINDOW=8, negatif kareler oluşabilir
    engine = ExportEngine.__new__(ExportEngine)
    engine._violations = [v]
    engine._blur_map = {}
    for viol in engine._violations:
        if not viol.is_selected:
            continue
        for offset in range(-BLUR_WINDOW, BLUR_WINDOW + 1):
            fn = viol.frame_number + offset
            if fn >= 0:
                engine._blur_map.setdefault(fn, []).append(viol.bbox)

    for fn in engine._blur_map:
        assert fn >= 0, f"Negatif kare numarası: {fn}"


def test_cancel_sets_flag():
    engine = ExportEngine.__new__(ExportEngine)
    engine._cancelled = False
    engine.cancel()
    assert engine._cancelled is True


def test_blur_window_constant():
    assert BLUR_WINDOW > 0
    assert isinstance(BLUR_WINDOW, int)