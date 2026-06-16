from __future__ import annotations

import time
from typing import NamedTuple

import cv2
import numpy as np
from loguru import logger

from ai.label_map import ViolationCategory

_CLIP_MODEL_NAME = "ViT-B/32"

_SKIP_CATEGORIES: frozenset[ViolationCategory] = frozenset({
    ViolationCategory.CHILD_FACE,
    ViolationCategory.PRIVATE_PLATE,
})

_PROMPTS: dict[ViolationCategory, tuple[list[str], list[str]]] = {
    ViolationCategory.CIGARETTE: (
        ["a cigarette", "someone smoking", "a lit cigarette", "cigarette smoke"],
        ["no cigarette", "clean air", "a person not smoking", "an empty hand"],
    ),
    ViolationCategory.WEAPON: (
        ["a gun", "a pistol", "a knife", "a rifle", "a grenade", "armed person"],
        ["no weapon", "an empty hand", "a toy", "a phone", "a remote control"],
    ),
    ViolationCategory.ALCOHOL: (
        ["a beer bottle", "a wine glass", "an alcohol bottle", "drinking alcohol"],
        ["no alcohol", "a water bottle", "a soft drink", "juice"],
    ),
    ViolationCategory.BLOOD: (
        ["blood on skin", "a bloody wound", "bleeding injury", "blood stain"],
        ["no blood", "clean skin", "no wound", "a healthy person"],
    ),
    ViolationCategory.NUDITY: (
        ["nudity", "explicit content", "naked body", "nsfw image"],
        ["clothed person", "no nudity", "a fully dressed person", "safe content"],
    ),
    ViolationCategory.DRUG: (
        ["illegal drugs", "drug paraphernalia", "a syringe with drugs", "drug use"],
        ["no drugs", "medicine", "a clean surface", "no paraphernalia"],
    ),
}

_DEFAULT_THRESHOLD = 0.18
_DEFAULT_MARGIN = 0.01


class _ClipResult(NamedTuple):
    positive_score: float
    negative_score: float
    verified: bool


class ClipVerifier:
    """
    CLIP (ViT-B/32) tabanlı görüntü doğrulayıcı.
    Moondream2'ye göre ~20-50x daha hızlı, CPU'da frame başına ~100-300ms.
    Model yüklenemezse pass-through (True) döner.
    """

    def __init__(
        self,
        threshold: float = _DEFAULT_THRESHOLD,
        margin: float = _DEFAULT_MARGIN,
    ) -> None:
        self._threshold = threshold
        self._margin = margin
        self._model = None
        self._preprocess = None
        self._device: str = "cpu"
        self._loaded = False
        self._enabled = False

    def load(self) -> "ClipVerifier":
        try:
            import torch
            import clip

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"CLIP yükleniyor ({_CLIP_MODEL_NAME}, device={self._device})...")
            t0 = time.time()

            self._model, self._preprocess = clip.load(_CLIP_MODEL_NAME, device=self._device)
            self._model.eval()

            # Text promptlarını bir kez encode et, her frame'de tekrar yapma
            self._text_features: dict[ViolationCategory, tuple] = {}
            with torch.no_grad():
                for cat, (pos_prompts, neg_prompts) in _PROMPTS.items():
                    all_prompts = pos_prompts + neg_prompts
                    tokens = clip.tokenize(all_prompts).to(self._device)
                    feats = self._model.encode_text(tokens)
                    feats = feats / feats.norm(dim=-1, keepdim=True)
                    self._text_features[cat] = (feats, len(pos_prompts))

            self._loaded = True
            self._enabled = True
            logger.info(f"CLIP yüklendi ({time.time() - t0:.1f}s)")
        except ImportError:
            logger.warning(
                "openai-clip paketi bulunamadı. "
                "Kurmak için: pip install git+https://github.com/openai/CLIP.git"
            )
        except Exception as e:
            logger.warning(f"CLIP yüklenemedi: {e} — doğrulama devre dışı")
        return self

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def enable(self, state: bool) -> None:
        self._enabled = state

    def verify(self, frame: np.ndarray, bbox: tuple, category: ViolationCategory) -> bool:
        if not self._loaded or not self._enabled:
            return True

        if category in _SKIP_CATEGORIES:
            return True

        if category not in self._text_features:
            return True

        crop = self._crop(frame, bbox)
        if crop is None:
            return True

        try:
            result = self._compare(crop, category)
            verdict = "ONAYLANDI" if result.verified else "REDDEDİLDİ"
            logger.debug(
                f"CLIP [{category.name}] pos={result.positive_score:.3f} "
                f"neg={result.negative_score:.3f} → {verdict}"
            )
            return result.verified
        except Exception as e:
            logger.warning(f"CLIP sorgu hatası: {e}")
            return True

    def _crop(self, frame: np.ndarray, bbox: tuple) -> np.ndarray | None:
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        pad = 20
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        crop = frame[y1:y2, x1:x2]
        return crop if crop.size > 0 else None

    def _compare(self, frame_bgr: np.ndarray, category: ViolationCategory) -> _ClipResult:
        import torch
        from PIL import Image

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        image_input = self._preprocess(pil_img).unsqueeze(0).to(self._device)

        with torch.no_grad():
            image_features = self._model.encode_image(image_input)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Pre-computed text features kullan
            text_features, n_pos = self._text_features[category]
            similarities = (image_features @ text_features.T).squeeze(0)

        pos_score = float(similarities[:n_pos].max())
        neg_score = float(similarities[n_pos:].max())
        verified = (pos_score >= self._threshold) and (pos_score > neg_score + self._margin)
        return _ClipResult(positive_score=pos_score, negative_score=neg_score, verified=verified)