import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.scan_engine import ScanEngine, ScanConfig, ScanSummary
from core.violation_store import ViolationStore
from ai.label_map import ViolationCategory


def make_engine() -> ScanEngine:
    engine = ScanEngine.__new__(ScanEngine)
    engine._video_path = "/test/video.mp4"
    engine._config = ScanConfig()
    engine._cancelled = False
    engine._paused = False
    return engine


def test_cancel_sets_flag():
    engine = make_engine()
    engine.cancel()
    assert engine._cancelled is True


def test_cancel_also_clears_pause():
    engine = make_engine()
    engine._paused = True
    engine.cancel()
    assert engine._paused is False  # pause'dan çıkmalı ki thread sonlanabilsin


def test_pause_resume():
    engine = make_engine()
    assert engine.is_paused() is False
    engine.pause()
    assert engine.is_paused() is True
    engine.resume()
    assert engine.is_paused() is False


def test_scan_config_defaults():
    cfg = ScanConfig()
    assert cfg.frame_skip == 5
    assert cfg.confidence == 0.45
    assert cfg.confirm_window == 2


def test_scan_summary_fields():
    s = ScanSummary(total_frames=1000, scanned_frames=200, violation_count=5, duration_sec=40.0)
    assert s.total_frames == 1000
    assert s.scanned_frames == 200
    assert s.violation_count == 5
    assert s.duration_sec == 40.0