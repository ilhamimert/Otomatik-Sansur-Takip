def frame_to_seconds(frame_number: int, fps: float) -> float:
    if fps <= 0:
        return 0.0
    return frame_number / fps


def seconds_to_str(seconds: float) -> str:
    total_ms = int(seconds * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    m = total_s // 60
    return f"{m:02d}:{s:02d}:{ms:03d}"


def frame_to_str(frame_number: int, fps: float) -> str:
    return seconds_to_str(frame_to_seconds(frame_number, fps))