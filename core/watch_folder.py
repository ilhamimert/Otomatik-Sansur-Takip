from __future__ import annotations

import asyncio
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from loguru import logger

from utils.video_utils import is_video_file


@dataclass
class WatchedFile:
    path: str
    name: str
    ext: str
    size_bytes: int
    status: str = "pending"   # pending | scanning | done | error


class _VideoEventHandler(FileSystemEventHandler):
    """Klasöre yeni dosya gelince tetiklenir."""

    def __init__(self, on_new_video: Callable[[WatchedFile], None]):
        super().__init__()
        self._callback = on_new_video

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        path = event.src_path
        if not is_video_file(path):
            return
        # Dosya yazılmayı bitirene kadar bekle (I/O lock)
        self._wait_until_ready(path)
        try:
            p = Path(path)
            wf = WatchedFile(
                path=path,
                name=p.name,
                ext=p.suffix.lower(),
                size_bytes=p.stat().st_size,
            )
            logger.info(f"Watch Folder: yeni video algılandı → {p.name}")
            self._callback(wf)
        except Exception as e:
            logger.error(f"Watch Folder dosya hatası: {e}")

    def _wait_until_ready(self, path: str, timeout: int = 60):
        """
        Dosya başka bir işlem tarafından kullanılıyorsa (I/O lock)
        serbest kalana kadar bekle. Max timeout saniye.
        """
        deadline = time.time() + timeout
        last_size = -1

        while time.time() < deadline:
            try:
                current_size = Path(path).stat().st_size
                if current_size == last_size and current_size > 0:
                    # Boyut değişmedi → yazma tamamlandı
                    # Ek kontrol: dosyayı okuma modunda açmayı dene
                    with open(path, "rb"):
                        pass
                    return
                last_size = current_size
            except (PermissionError, OSError):
                pass
            time.sleep(2)

        logger.warning(f"Watch Folder: {path} için timeout ({timeout}s)")


class WatchFolderService:
    """
    Belirli bir klasörü izler, yeni video gelince callback'i çağırır.
    Asenkron uyumlu — PyQt thread ile birlikte çalışır.
    """

    def __init__(self, folder: str, on_new_video: Callable[[WatchedFile], None]):
        self._folder = folder
        self._handler = _VideoEventHandler(on_new_video)
        self._observer: Optional[Observer] = None

    def start(self):
        if self._observer and self._observer.is_alive():
            return
        Path(self._folder).mkdir(parents=True, exist_ok=True)
        self._observer = Observer()
        self._observer.schedule(self._handler, self._folder, recursive=False)
        self._observer.start()
        logger.info(f"Watch Folder başlatıldı: {self._folder}")

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None
        logger.info("Watch Folder durduruldu.")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    @property
    def folder(self) -> str:
        return self._folder
