from __future__ import annotations
import threading
from pathlib import Path
from loguru import logger


class ModelManager:
    """
    Çoklu model yöneticisi. Thread-safe Singleton — modeller yalnızca bir kez yüklenir.
    """

    _instance = None
    _lock = threading.Lock()
    _models: list = []
    _missing_models: list[str] = []
    _loaded: bool = False

    def __new__(cls):
        # Singleton — lock gerekmez, CPython GIL yeterli
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_missing_models(self) -> list[str]:
        return list(ModelManager._missing_models)

    def load(self, config: dict) -> list:
        """Tüm modelleri yükle. Thread-safe — yalnızca bir kez yüklenir."""
        with ModelManager._lock:
            if ModelManager._loaded:
                return ModelManager._models

            try:
                from ultralytics import YOLO
            except ImportError:
                raise RuntimeError("ultralytics paketi kurulu değil.")

            models: list = []
            missing: list[str] = []

            custom = self._load_custom_model(YOLO, missing)
            if custom:
                models.append(custom)

            weapon = self._load_weapon_model(YOLO, missing)
            if weapon:
                models.append(weapon)

            smoking = self._load_smoking_model(YOLO, missing)
            if smoking:
                models.append(smoking)

            general = self._load_general_model(YOLO, config)
            if general:
                models.append(general)

            if not models:
                raise RuntimeError("Hiçbir model yüklenemedi.")

            ModelManager._models = models
            ModelManager._missing_models = missing
            ModelManager._loaded = True
            logger.info(f"{len(models)} model yüklendi.")
            return ModelManager._models

    @staticmethod
    def _load_custom_model(YOLO, missing: list) -> object:
        path = Path("models/cigarette_custom.pt")
        if path.exists():
            logger.info(f"Custom model yükleniyor: {path}")
            try:
                model = YOLO(str(path), task="detect")
                logger.info(f"Custom model yüklendi. Sınıflar: {model.names}")
                return model
            except Exception as e:
                logger.warning(f"Custom model yüklenemedi: {e}")
                missing.append("Sigara (cigarette_custom.pt) — yükleme hatası")
        else:
            missing.append("Sigara (cigarette_custom.pt) — dosya bulunamadı")
        return None

    @staticmethod
    def _load_weapon_model(YOLO, missing: list) -> object:
        path = Path("models/weapon_detector.pt")
        if path.exists():
            logger.info(f"Silah modeli yukleniyor: {path}")
            try:
                model = YOLO(str(path), task="detect")
                logger.info(f"Silah modeli yuklendi. Siniflar: {model.names}")
                return model
            except Exception as e:
                logger.warning(f"Silah modeli yuklenemedi: {e}")
                missing.append("Silah (weapon_detector.pt) — yükleme hatası")
        else:
            missing.append("Silah (weapon_detector.pt) — dosya bulunamadı")
        return None

    @staticmethod
    def _load_smoking_model(YOLO, missing: list) -> object:
        path = Path("models/smoking_detector.onnx")
        if path.exists():
            logger.info(f"Sigara modeli yükleniyor: {path}")
            try:
                model = YOLO(str(path), task="detect")
                logger.info(f"Sigara modeli yüklendi. Sınıflar: {model.names}")
                return model
            except Exception as e:
                logger.warning(f"Sigara modeli yüklenemedi: {e}")
                missing.append("Duman (smoking_detector.onnx) — yükleme hatası")
        else:
            logger.warning("Sigara modeli bulunamadı: models/smoking_detector.onnx")
            missing.append("Duman (smoking_detector.onnx) — dosya bulunamadı")
        return None

    @staticmethod
    def _load_general_model(YOLO, config: dict) -> object:
        openvino = config.get("openvino_path", "")
        onnx = config.get("onnx_path", "")
        pt = config.get("path", "models/yolo11n.pt")
        prefer_openvino = config.get("prefer_openvino", True)

        if prefer_openvino and openvino and Path(openvino).exists():
            path = openvino
        elif onnx and Path(onnx).exists():
            path = onnx
        else:
            path = pt

        logger.info(f"Genel model yükleniyor: {path}")
        try:
            model = YOLO(path)
            logger.info(f"Genel model yüklendi. Sınıf sayısı: {len(model.names)}")
            return model
        except Exception as e:
            logger.warning(f"Genel model yüklenemedi: {e}")
        return None

    def unload(self):
        with ModelManager._lock:
            ModelManager._models = []
            ModelManager._loaded = False
        logger.info("Modeller bellekten kaldırıldı.")
