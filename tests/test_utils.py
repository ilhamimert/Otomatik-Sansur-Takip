import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.time_utils import frame_to_seconds, seconds_to_str, frame_to_str


def test_frame_to_seconds():
    assert frame_to_seconds(0, 25.0) == 0.0
    assert frame_to_seconds(25, 25.0) == 1.0
    assert frame_to_seconds(150, 25.0) == 6.0


def test_frame_to_seconds_zero_fps():
    assert frame_to_seconds(100, 0) == 0.0


def test_seconds_to_str_minutes():
    assert seconds_to_str(65) == "01:05"
    assert seconds_to_str(0) == "00:00"
    assert seconds_to_str(3661) == "01:01:01"


def test_frame_to_str():
    result = frame_to_str(750, 25.0)  # 30 saniye
    assert result == "00:30"
