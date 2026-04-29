from __future__ import annotations
import cv2
import tempfile
import os
import subprocess
from pathlib import Path


# MXF ve diğer broadcast formatları FFmpeg ile açılır
MXF_EXTENSIONS = {".mxf", ".mts", ".m2ts", ".m2v", ".gxf", ".lxf"}
ALL_VIDEO_EXTENSIONS = {
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv",
    ".webm", ".ts", ".mxf", ".mts", ".m2ts", ".m2v",
    ".gxf", ".lxf", ".mpg", ".mpeg"
}


def _ffmpeg_path() -> str:
    """FFmpeg'in sistem PATH'indeki konumunu döndür."""
    for candidate in ["ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe"]:
        try:
            r = subprocess.run([candidate, "-version"],
                               capture_output=True, timeout=3)
            if r.returncode == 0:
                return candidate
        except Exception:
            pass
    return ""


def _is_mxf_like(path: str) -> bool:
    return Path(path).suffix.lower() in MXF_EXTENSIONS


def open_capture(path: str) -> cv2.VideoCapture:
    """
    Video dosyasını aç. MXF gibi broadcast formatları için
    FFmpeg backend kullanır.
    """
    # Önce doğrudan dene
    cap = cv2.VideoCapture(path)
    if cap.isOpened():
        return cap
    cap.release()

    # FFmpeg backend ile dene (CAP_FFMPEG)
    cap = cv2.VideoCapture(path, cv2.CAP_FFMPEG)
    if cap.isOpened():
        return cap
    cap.release()

    raise ValueError(f"Video açılamadı: {path}\n"
                     f"Desteklenen formatlar: {', '.join(sorted(ALL_VIDEO_EXTENSIONS))}")


def get_video_info(path: str) -> dict:
    cap = open_capture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # MXF dosyalarında frame_count güvenilmez — süre hesabı farklı
    if frame_count <= 0 and _is_mxf_like(path):
        frame_count = _estimate_frame_count_ffprobe(path, fps)

    info = {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_sec": frame_count / fps if fps > 0 and frame_count > 0 else 0.0,
    }
    cap.release()
    return info


def _estimate_frame_count_ffprobe(path: str, fps: float) -> int:
    """FFprobe ile MXF dosyasının süresini al, frame sayısına çevir."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip())
        return int(duration * fps)
    except Exception:
        return 0


def is_video_file(path: str) -> bool:
    return Path(path).suffix.lower() in ALL_VIDEO_EXTENSIONS


def _test_codec(fourcc_str: str, ext: str, w: int = 640, h: int = 480) -> bool:
    import numpy as np
    tmp = tempfile.mktemp(suffix=ext)
    try:
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        writer = cv2.VideoWriter(tmp, fourcc, 25.0, (w, h))
        if not writer.isOpened():
            return False
        writer.write(np.zeros((h, w, 3), dtype=np.uint8))
        writer.release()
        return os.path.exists(tmp) and os.path.getsize(tmp) > 0
    except Exception:
        return False
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def choose_writer_fourcc() -> tuple:
    candidates = [
        ("mp4v", ".mp4"),
        ("XVID", ".avi"),
        ("MJPG", ".avi"),
        ("avc1", ".mp4"),
    ]
    for fourcc_str, ext in candidates:
        if _test_codec(fourcc_str, ext):
            return cv2.VideoWriter_fourcc(*fourcc_str), ext
    return cv2.VideoWriter_fourcc(*"MJPG"), ".avi"
