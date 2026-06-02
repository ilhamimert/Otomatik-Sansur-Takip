"""
Windows Service kabuğu — FastAPI + WatchFolder birleşik mod.
Servis başlayınca hem REST API (uvicorn) hem WatchFolder çalışır.

Kurulum  : python service/windows_service.py install
Başlatma : python service/windows_service.py start
Durdurma : python service/windows_service.py stop
Kaldırma : python service/windows_service.py remove
Manuel   : python service/windows_service.py run  (servis olmadan test)
"""
from __future__ import annotations

import os
import socket
import sys
import threading
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Servis olarak çalışırken (LocalSystem) venv DLL dizinlerini PATH'e ekle
# cv2, torch gibi kütüphaneler kullanıcı PATH'ini görmez; tüm .libs dizinlerini ekle
_site_packages = ROOT / "venv" / "Lib" / "site-packages"
_dll_dirs = [ROOT / "venv" / "Scripts", _site_packages]
# site-packages altındaki tüm *.libs ve *_system32 dizinlerini otomatik ekle
for _d in _site_packages.iterdir():
    if _d.is_dir() and (_d.name.endswith(".libs") or _d.name.endswith("_system32")):
        _dll_dirs.append(_d)
_dll_dirs.append(_site_packages / "cv2")

_path_prepend = []
for _dll_dir in _dll_dirs:
    if _dll_dir.exists():
        try:
            os.add_dll_directory(str(_dll_dir))
        except Exception:
            pass
        _path_prepend.append(str(_dll_dir))

os.environ["PATH"] = os.pathsep.join(_path_prepend) + os.pathsep + os.environ.get("PATH", "")

import yaml
import uvicorn
from loguru import logger

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "service_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="INFO",
    encoding="utf-8",
)


def _load_config() -> dict:
    cfg_path = ROOT / "config.yaml"
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _port_in_use(host: str, port: int) -> bool:
    """Verilen port zaten kullanılıyorsa True döner."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host if host != "0.0.0.0" else "127.0.0.1", port)) == 0


def _run_api_server():
    """uvicorn'u bloklayan modda başlatır; servis thread'inde çağrılır."""
    try:
        logger.info("_run_api_server başlıyor — import deneniyor.")
        from api.server import app, start_service
        logger.info("Import başarılı.")

        cfg = _load_config()
        api_cfg = cfg.get("api", {})
        host = api_cfg.get("host", "0.0.0.0")
        port = api_cfg.get("port", 8000)

        if _port_in_use(host, port):
            logger.error(f"Port {port} zaten kullanımda — servis başlatılamıyor.")
            return

        start_service()
        logger.info(f"REST API başlatılıyor: http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except Exception:
        logger.exception("_run_api_server içinde beklenmeyen hata.")


def _run_standalone():
    """Manuel test modu — servis altyapısı olmadan direkt çalıştırır."""
    logger.info("Manuel mod — API sunucusu başlatılıyor.")
    _run_api_server()


# ── Windows Service ──────────────────────────────────────────────────────────
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager

    class CnbcScanService(win32serviceutil.ServiceFramework):
        _svc_name_ = "CnbcContentScanner"
        _svc_display_name_ = "CNBC Türk İçerik Tarama Servisi"
        _svc_description_ = "REST API + WatchFolder: uygunsuz içerik tespiti, TXT rapor üretimi."
        _svc_start_type_ = win32service.SERVICE_AUTO_START  # sistem açılışında otomatik başla

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._win_stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._server_thread: threading.Thread | None = None

        def SvcStop(self):
            logger.info("Servis durduruluyor...")
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._graceful_shutdown()
            win32event.SetEvent(self._win_stop_event)

        def _graceful_shutdown(self):
            """Aktif taramaların bitmesini beklemeden WatchFolder'ı durdurur."""
            try:
                from api.server import stop_service
                stop_service()
                logger.info("WatchFolder durduruldu.")
            except Exception as e:
                logger.warning(f"Graceful shutdown sırasında hata: {e}")

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            logger.info("Servis başlatıldı.")
            self._server_thread = threading.Thread(target=_run_api_server, daemon=True)
            self._server_thread.start()
            win32event.WaitForSingleObject(self._win_stop_event, win32event.INFINITE)
            logger.info("Servis durdu.")

    def main():
        if len(sys.argv) == 1:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(CnbcScanService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            win32serviceutil.HandleCommandLine(CnbcScanService)

except ImportError:
    def main():
        args = sys.argv[1:]
        if args and args[0] == "run":
            _run_standalone()
        elif args and args[0] in ("install", "start", "stop", "remove", "restart"):
            print("Hata: pywin32 kurulu değil, Windows Service işlemleri yapılamıyor.")
            print("")
            print("Kurulum için:")
            print("  pip install pywin32")
            print("  python -m pywin32_postinstall -install")
            sys.exit(1)
        else:
            print("Kullanım:")
            print("  python service/windows_service.py install  — servisi kur")
            print("  python service/windows_service.py start    — servisi başlat")
            print("  python service/windows_service.py stop     — servisi durdur")
            print("  python service/windows_service.py remove   — servisi kaldır")
            print("  python service/windows_service.py run      — manuel test (pywin32 gerekmez)")
            print("")
            print("pywin32 kurulu değil. Servis kurulumu için:")
            print("  pip install pywin32")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        _run_standalone()
    else:
        main()
