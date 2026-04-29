"""
FastAPI REST server. WatchFolder servisini kontrol eder, kuyruk durumunu sunar.
"""
from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from loguru import logger

from service.job_queue import JobQueue

if TYPE_CHECKING:
    from service.watchfolder import WatchFolder

app = FastAPI(title="CNBC Türk — İçerik Tarama API", version="1.0.0", docs_url=None, redoc_url=None)

# Uygulama genelinde paylaşılan state
_job_queue: JobQueue = JobQueue()
_watchfolder: WatchFolder | None = None
_wf_thread: threading.Thread | None = None
_started_at: datetime | None = None


def _load_config(path: str = "config.yaml") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_job_queue() -> JobQueue:
    return _job_queue


# ── Durum ──────────────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    running = _watchfolder is not None and not _watchfolder._stop_event
    uptime = int((datetime.now() - _started_at).total_seconds()) if _started_at else 0
    return {
        "running": running,
        "uptime_seconds": uptime,
        "queue": _job_queue.snapshot()["counts"],
    }


# ── Servis Kontrolü ────────────────────────────────────────────────────────

@app.post("/api/start")
def start_service():
    global _watchfolder, _wf_thread, _started_at

    if _watchfolder and not _watchfolder._stop_event:
        return {"ok": False, "message": "Servis zaten çalışıyor."}

    cfg = _load_config()
    svc_cfg = cfg.get("service", {})
    watch_dir = svc_cfg.get("watch_dir", "") or "WatchFolder"
    max_workers = svc_cfg.get("max_workers", 2)

    from service.watchfolder import WatchFolder
    _watchfolder = WatchFolder(
        base_dir=watch_dir,
        config_path="config.yaml",
        max_workers=max_workers,
        job_queue=_job_queue,
    )
    _started_at = datetime.now()

    _wf_thread = threading.Thread(target=_watchfolder.start, daemon=True)
    _wf_thread.start()
    logger.info("Servis API üzerinden başlatıldı.")
    return {"ok": True, "message": "Servis başlatıldı."}


@app.post("/api/stop")
def stop_service():
    global _watchfolder
    if not _watchfolder or _watchfolder._stop_event:
        return {"ok": False, "message": "Servis zaten durmuş."}
    _watchfolder.stop()
    logger.info("Servis API üzerinden durduruldu.")
    return {"ok": True, "message": "Servis durduruldu."}


# ── Video Yükleme ──────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    cfg = _load_config()
    svc_cfg = cfg.get("service", {})
    watch_dir = svc_cfg.get("watch_dir", "") or "WatchFolder"
    input_dir = Path(watch_dir) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    allowed = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v", ".ts", ".mts"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen format: {suffix}")

    dest = input_dir / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    job = _job_queue.enqueue(filename=file.filename, filepath=str(dest))
    logger.info(f"Video yüklendi: {file.filename} → job {job.id}")
    return {"ok": True, "job_id": job.id, "filename": file.filename}


# ── Kuyruk ─────────────────────────────────────────────────────────────────

@app.get("/api/queue")
def queue():
    return _job_queue.snapshot()


# ── Raporlar ───────────────────────────────────────────────────────────────

@app.get("/api/reports")
def reports():
    snap = _job_queue.snapshot()
    done_jobs = [j for j in snap["done"] if j.get("status") == "done"]
    return {"reports": done_jobs, "count": len(done_jobs)}


@app.get("/api/reports/{job_id}")
def report_detail(job_id: str):
    job = _job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadı.")
    if job.status != "done":
        return {"job_id": job_id, "status": job.status, "report": None}
    data = job.to_dict()
    data["report"] = job.report
    return data
