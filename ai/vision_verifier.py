from __future__ import annotations
import time
from pathlib import Path
import numpy as np
import cv2
from loguru import logger

from ai.label_map import ViolationCategory

# Moondream2 model klasörü (offline kullanım için buraya indirilmeli)
MODEL_DIR = Path("models/moondream2")

# Kategori bazlı doğrulama soruları (İngilizce — daha iyi sonuç verir)
VERIFY_QUESTIONS: dict[ViolationCategory, str] = {
    ViolationCategory.CIGARETTE: "Is there a cigarette or someone smoking in this image? Answer only yes or no.",
    ViolationCategory.WEAPON:    "Is there a weapon such as a gun, knife, or grenade in this image? Answer only yes or no.",
    ViolationCategory.ALCOHOL:   "Is there an alcoholic beverage such as beer, wine, or a bottle of alcohol in this image? Answer only yes or no.",
    ViolationCategory.BLOOD:     "Is there blood or a bloody wound visible in this image? Answer only yes or no.",
    ViolationCategory.NUDITY:    "Does this image contain nudity or explicit content? Answer only yes or no.",
    ViolationCategory.DRUG:      "Is there illegal drug paraphernalia or drugs visible in this image? Answer only yes or no.",
}


class VisionVerifier:
    """
    YOLO tespitlerini moondream2 ile doğrular.
    Model yoksa veya yüklenemezse devre dışı kalır (pass-through).
    """

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._enabled = False

    def load(self) -> "VisionVerifier":
        if not MODEL_DIR.exists():
            logger.warning(
                f"Moondream2 model klasörü bulunamadı: {MODEL_DIR}\n"
                f"İndirmek için: python download_moondream.py"
            )
            return self

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM

            logger.info("Moondream2 yükleniyor...")
            t0 = time.time()

            abs_dir = str(MODEL_DIR.resolve())
            self._tokenizer = AutoTokenizer.from_pretrained(
                abs_dir,
                trust_remote_code=True,
                local_files_only=True,
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                abs_dir,
                trust_remote_code=True,
                local_files_only=True,
                torch_dtype=torch.float32,
            )
            self._model.eval()
            self._loaded = True
            self._enabled = True
            logger.info(f"Moondream2 yüklendi ({time.time() - t0:.1f}s)")
        except Exception as e:
            logger.warning(f"Moondream2 yüklenemedi: {e} — doğrulama devre dışı")

        return self

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def enable(self, state: bool):
        self._enabled = state

    def verify(self, frame: np.ndarray, bbox: tuple, category: ViolationCategory) -> bool:
        """
        YOLO'nun tespit ettiği bölgeyi moondream2 ile doğrula.
        Model yüklü değilse her zaman True döner (pass-through).
        """
        if not self._loaded or not self._enabled:
            return True

        question = VERIFY_QUESTIONS.get(category)
        if not question:
            return True

        crop = self._crop(frame, bbox)
        if crop is None:
            return True

        try:
            answer = self._ask(crop, question)
            result = answer.strip().lower().startswith("yes")
            logger.debug(f"Moondream [{category.name}] → '{answer.strip()}' → {'ONAYLANDI' if result else 'REDDEDİLDİ'}")
            return result
        except Exception as e:
            logger.warning(f"Moondream sorgu hatası: {e}")
            return True  # Hata olursa tespiti geçir

    def _crop(self, frame: np.ndarray, bbox: tuple) -> np.ndarray | None:
        """Bbox bölgesini kırp, biraz padding ekle."""
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        pad = 20
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        return crop

    def _ask(self, frame_bgr: np.ndarray, question: str) -> str:
        """Moondream2'ye görsel + soru sor, cevap al."""
        from PIL import Image
        import torch

        # BGR → RGB → PIL
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        enc_img = self._model.encode_image(pil_img)
        answer = self._model.answer_question(enc_img, question, self._tokenizer)
        return answer