"""
Windows Service kabuğu.
Kurulum  : python service/windows_service.py install
Başlatma : python service/windows_service.py start
Durdurma : python service/windows_service.py stop
Kaldırma : python service/windows_service.py remove
Manuel   : python service/windows_service.py run  (servis olmadan test)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import yaml
from loguru import logger

# Log dosyası ayarı
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "service_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="INFO",
    encoding="utf-8",
)


def _load_service_config() -> dict:
    cfg_path = ROOT / "config.yaml"
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_watchfolder_path() -> str:
    cfg = _load_service_config()
    path = cfg.get("service", {}).get("watch_dir", "")
    if path:
        return path
    default = ROOT / "WatchFolder"
    default.mkdir(exist_ok=True)
    return str(default)


def _get_max_workers() -> int:
    cfg = _load_service_config()
    return cfg.get("service", {}).get("max_workers", 2)


def _run_watchfolder():
    from service.job_queue import JobQueue
    from service.watchfolder import WatchFolder
    watch_dir = _get_watchfolder_path()
    max_workers = _get_max_workers()
    logger.info(f"WatchFolder yolu: {watch_dir}")
    logger.info(f"Paralel tarama sayısı: {max_workers}")
    job_queue = JobQueue()
    wf = WatchFolder(
        watch_dir,
        config_path=str(ROOT / "config.yaml"),
        max_workers=max_workers,
        job_queue=job_queue,
    )
    wf.start()


# ── Windows Service ──────────────────────────────────────────────────────────
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager

    class CnbcScanService(win32serviceutil.ServiceFramework):
        _svc_name_ = "CnbcContentScanner"
        _svc_display_name_ = "CNBC Türk İçerik Tarama Servisi"
        _svc_description_ = "WatchFolder izler, uygunsuz içerik tespiti yapar, TXT rapor üretir."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._wf = None

        def SvcStop(self):
            logger.info("Servis durduruluyor...")
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            if self._wf:
                self._wf.stop()
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            logger.info("Servis başlatıldı.")
            import threading
            from service.job_queue import JobQueue
            from service.watchfolder import WatchFolder

            watch_dir = _get_watchfolder_path()
            max_workers = _get_max_workers()
            self._wf = WatchFolder(
                watch_dir,
                config_path=str(ROOT / "config.yaml"),
                max_workers=max_workers,
                job_queue=JobQueue(),
            )
            t = threading.Thread(target=self._wf.start, daemon=True)
            t.start()
            win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)
            logger.info("Servis durdu.")

    def main():
        if len(sys.argv) == 1:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(CnbcScanService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            win32serviceutil.HandleCommandLine(CnbcScanService)

except ImportError:
    # pywin32 kurulu değil — sadece "run" komutu çalışır
    def main():
        if len(sys.argv) > 1 and sys.argv[1] == "run":
            logger.info("Manuel mod (pywin32 yok) — WatchFolder başlatılıyor.")
            _run_watchfolder()
        else:
            print("pywin32 kurulu değil. Servis kurulumu için:")
            print("  pip install pywin32")
            print("")
            print("Manuel test için:")
            print("  python service/windows_service.py run")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        logger.info("Manuel mod — WatchFolder başlatılıyor.")
        _run_watchfolder()
    else:
        main()
