"""
Windows Service wrapper — pythonservice.exe yerine doğrudan venv Python ile çalışır.
Bu sayede DLL path sorunu yaşanmaz.

sc.exe tarafından su sekilde cagrilir:
  venv\Scripts\python.exe service\run_service.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# DLL dizinlerini kaydet — normal Python sürecinde bu çalışır
_site_packages = ROOT / "venv" / "Lib" / "site-packages"
_dll_dirs = [ROOT / "venv" / "Scripts", _site_packages / "cv2"]
for _d in _site_packages.iterdir():
    if _d.is_dir() and (_d.name.endswith(".libs") or _d.name.endswith("_system32")):
        _dll_dirs.append(_d)

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


if __name__ == "__main__":
    logger.info("run_service.py başlatıldı.")
    try:
        from api.server import app, start_service
        logger.info("Import başarılı.")

        cfg = _load_config()
        api_cfg = cfg.get("api", {})
        host = api_cfg.get("host", "0.0.0.0")
        port = api_cfg.get("port", 8000)

        start_service()
        logger.info(f"REST API başlatılıyor: http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except Exception:
        logger.exception("run_service.py içinde beklenmeyen hata.")
        sys.exit(1)
