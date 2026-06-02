"""
WatchFolder motoru. input/ klasörünü izler, yeni video gelince tarar,
raporu output/ klasörüne yazar, videoyu done/ klasörüne taşır.

Paralel tarama: her video ayrı thread'de işlenir (max_workers sınırlı).
"""
from __future__ import annotations

import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from loguru import logger

from ai.label_map import ViolationCategory
from service.job_queue import JobQueue
from service.report_writer import write_txt_report
from service.scan_worker import ScanReport, ScanWorker
from utils.video_utils import ALL_VIDEO_EXTENSIONS


def _report_to_dict(report: ScanReport, txt_path: str) -> dict:
    return {
        "video_name": report.video_name,
        "duration_sec": report.duration_sec,
        "total_frames": report.total_frames,
        "scanned_frames": report.scanned_frames,
        "error": report.error,
        "txt_report": txt_path,
        "violation_count": len(report.violations) if not report.error else 0,
        "violations": [
            {
                "timestamp_str": v.timestamp_str,
                "timestamp_sec": v.timestamp_sec,
                "category": v.category.name,
                "label": v.label,
                "confidence": round(v.confidence, 3),
            }
            for v in (report.violations or [])
        ],
    }


class WatchFolder:
    def __init__(
        self,
        base_dir: str,
        config_path: str = "config.yaml",
        max_workers: int = 2,
        job_queue: JobQueue | None = None,
    ):
        self._base = Path(base_dir)
        self._input = self._base / "input"
        self._processing = self._base / "processing"
        self._done = self._base / "done"
        self._output = self._base / "output"
        self._config_path = config_path
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_files: set[str] = set()
        self._stop_event = False
        self._job_queue = job_queue

    def is_running(self) -> bool:
        return not self._stop_event

        for d in [self._input, self._processing, self._done, self._output]:
            d.mkdir(parents=True, exist_ok=True)

        logger.info(f"WatchFolder başlatıldı: {self._base}")
        logger.info(f"  input     : {self._input}")
        logger.info(f"  processing: {self._processing}")
        logger.info(f"  done      : {self._done}")
        logger.info(f"  output    : {self._output}")

    def start(self, poll_interval: float = 3.0):
        logger.info("İzleme başladı. Çıkmak için Ctrl+C.")
        try:
            while not self._stop_event:
                self._poll()
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Durduruldu.")
        finally:
            self._executor.shutdown(wait=True)

    def stop(self):
        self._stop_event = True

    def _poll(self):
        try:
            entries = list(self._input.iterdir())
        except PermissionError:
            return

        for entry in entries:
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in ALL_VIDEO_EXTENSIONS:
                continue
            if entry.name in self._active_files:
                continue
            if not self._is_file_ready(entry):
                continue

            self._active_files.add(entry.name)
            job_id: str | None = None
            if self._job_queue:
                job = self._job_queue.enqueue(filename=entry.name, filepath=str(entry))
                job_id = job.id
                counts = self._job_queue.snapshot()["counts"]
                logger.info(
                    f"[KUYRUK] Bekliyor: {counts['pending']} | "
                    f"İşleniyor: {counts['processing']} | "
                    f"Tamamlandı: {counts['done']}"
                )
            self._executor.submit(self._process_file, entry, job_id)

    @staticmethod
    def _is_file_ready(path: Path) -> bool:
        try:
            size1 = path.stat().st_size
            time.sleep(1.0)
            size2 = path.stat().st_size
            return size1 == size2 and size1 > 0
        except OSError:
            return False

    def _process_file(self, src: Path, job_id: str | None = None):
        proc_path = self._processing / src.name
        try:
            shutil.move(str(src), str(proc_path))
        except Exception as e:
            logger.error(f"Dosya taşıma hatası ({src.name}): {e}")
            self._active_files.discard(src.name)
            if self._job_queue and job_id:
                self._job_queue.mark_failed(job_id, str(e))
            return

        if self._job_queue and job_id:
            self._job_queue.mark_processing(job_id)
            counts = self._job_queue.snapshot()["counts"]
            logger.info(
                f"[BAŞLADI] {src.name} — "
                f"[KUYRUK] Bekliyor: {counts['pending']} | "
                f"İşleniyor: {counts['processing']} | "
                f"Tamamlandı: {counts['done']}"
            )
        else:
            logger.info(f"[BAŞLADI] {src.name}")

        cfg = self._load_config()
        scan_cfg = cfg.get("scan", {})
        model_cfg = cfg.get("model", {})
        cat_cfg = cfg.get("categories", {})

        active_categories = self._parse_categories(cat_cfg)

        done_event = __import__("threading").Event()
        result_holder: list[ScanReport] = []

        def on_done(report: ScanReport):
            result_holder.append(report)
            done_event.set()

        def on_progress(name: str, current: int, total: int):
            pct = int(current / total * 100) if total > 0 else 0
            logger.info(f"[İLERLEME] {name}: %{pct}")

        thumb_dir = self._output / Path(src.stem)
        worker = ScanWorker(
            video_path=str(proc_path),
            model_config=model_cfg,
            active_categories=active_categories,
            confidence=scan_cfg.get("confidence_threshold", 0.5),
            frame_skip=scan_cfg.get("frame_skip", 5),
            motion_threshold=scan_cfg.get("motion_threshold", 800),
            on_done=on_done,
            on_progress=on_progress,
            thumb_dir=str(thumb_dir),
        )
        worker.start()
        done_event.wait()

        report = result_holder[0]
        report.video_name = src.name

        report_dict: dict = {}
        try:
            report_path = write_txt_report(report, str(self._output))
            report_dict = _report_to_dict(report, report_path)
            logger.info(f"Rapor yazıldı: {report_path}")
        except Exception as e:
            logger.error(f"Rapor yazma hatası: {e}")

        if self._job_queue and job_id:
            if report.error:
                self._job_queue.mark_failed(job_id, report.error)
            else:
                self._job_queue.mark_done(job_id, report_dict)

        done_path = self._done / src.name
        try:
            shutil.move(str(proc_path), str(done_path))
        except Exception as e:
            logger.error(f"Done taşıma hatası: {e}")

        self._active_files.discard(src.name)
        vcount = len(report.violations) if not report.error else 0
        if self._job_queue:
            counts = self._job_queue.snapshot()["counts"]
            logger.info(
                f"[TAMAM] {src.name} — {vcount} ihlal | "
                f"[KUYRUK] Bekliyor: {counts['pending']} | "
                f"İşleniyor: {counts['processing']} | "
                f"Tamamlandı: {counts['done']}"
            )
        else:
            logger.info(f"[TAMAM] {src.name} — {vcount} ihlal")

    def _load_config(self) -> dict:
        try:
            with open(self._config_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Config yüklenemedi: {e}")
            return {}

    @staticmethod
    def _parse_categories(cat_cfg: dict) -> set[ViolationCategory] | None:
        mapping = {
            "cigarette":     ViolationCategory.CIGARETTE,
            "alcohol":       ViolationCategory.ALCOHOL,
            "nudity":        ViolationCategory.NUDITY,
            "weapon":        ViolationCategory.WEAPON,
            "blood":         ViolationCategory.BLOOD,
            "drug":          ViolationCategory.DRUG,
            "child_face":    ViolationCategory.CHILD_FACE,
            "private_plate": ViolationCategory.PRIVATE_PLATE,
        }
        if not cat_cfg:
            return None
        active = {v for k, v in mapping.items() if cat_cfg.get(k, False)}
        return active if active else None
