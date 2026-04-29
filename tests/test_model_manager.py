import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.model_manager import ModelManager


def _reset_singleton():
    ModelManager._instance = None
    ModelManager._models = []
    ModelManager._missing_models = []


def test_missing_models_tracked_when_no_files():
    _reset_singleton()
    mm = ModelManager()
    # Model dosyaları yokken yüklemeyi simüle et — ultralytics gerekli olmadan
    # Sadece _missing_models mekanizmasını test ediyoruz
    mm._missing_models = ["Silah (weapon_detector.pt) — dosya bulunamadı"]
    missing = mm.get_missing_models()
    assert len(missing) == 1
    assert "Silah" in missing[0]


def test_get_missing_models_returns_copy():
    _reset_singleton()
    mm = ModelManager()
    mm._missing_models = ["Model A"]
    result = mm.get_missing_models()
    result.append("Model B")  # kopya olmalı, orijinali etkilememeli
    assert len(mm._missing_models) == 1


def test_singleton_pattern():
    _reset_singleton()
    mm1 = ModelManager()
    mm2 = ModelManager()
    assert mm1 is mm2


def test_unload_clears_models():
    _reset_singleton()
    mm = ModelManager()
    mm._models = ["fake_model"]
    mm.unload()
    assert mm._models == []