"""
REST API sunucusunu başlatır. WatchFolder config'den otomatik ayarlanır.
Kullanım: python run_server.py
"""
from __future__ import annotations

import yaml
import uvicorn

from api.server import app, start_service


def _load_config(path: str = "config.yaml") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


if __name__ == "__main__":
    cfg = _load_config()
    api_cfg = cfg.get("api", {})
    host = api_cfg.get("host", "0.0.0.0")
    port = api_cfg.get("port", 8000)

    # Sunucu başlayınca WatchFolder'ı da otomatik başlat
    start_service()

    print("=" * 50)
    print("  CNBC Türk — İçerik Tarama REST API")
    print("=" * 50)
    print(f"  Adres   : http://{host}:{port}/api/status")
    print("  Durdurmak icin: Ctrl+C")
    print("=" * 50)

    uvicorn.run(app, host=host, port=port)
