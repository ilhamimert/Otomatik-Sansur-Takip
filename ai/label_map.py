from __future__ import annotations
from enum import Enum


class ViolationCategory(Enum):
    CIGARETTE = "Sigara"
    ALCOHOL = "Alkol"
    NUDITY = "Uygunsuz İçerik"
    WEAPON = "Silah"
    BLOOD = "Kan/Şiddet"
    DRUG = "Uyuşturucu"
    CHILD_FACE = "Çocuk Yüzü"
    PRIVATE_PLATE = "Plaka"


CATEGORY_HEX = {
    ViolationCategory.CIGARETTE:     "#FF6B35",
    ViolationCategory.ALCOHOL:       "#4ECDC4",
    ViolationCategory.NUDITY:        "#FF3B3B",
    ViolationCategory.WEAPON:        "#FFE66D",
    ViolationCategory.BLOOD:         "#C77DFF",
    ViolationCategory.DRUG:          "#96E6A1",
    ViolationCategory.CHILD_FACE:    "#87CEEB",
    ViolationCategory.PRIVATE_PLATE: "#CCCCCC",
}

CATEGORY_COLORS = {
    ViolationCategory.CIGARETTE:    (53,  107, 255),   # Turuncu (BGR)
    ViolationCategory.ALCOHOL:      (196, 205,  78),   # Mavi-Yeşil (BGR)
    ViolationCategory.NUDITY:       (59,  59,  255),   # Kırmızı (BGR)
    ViolationCategory.WEAPON:       (109, 230, 255),   # Sarı (BGR)
    ViolationCategory.BLOOD:        (255, 125, 199),   # Mor (BGR)
    ViolationCategory.DRUG:         (0,   200, 150),   # Yeşil (BGR)
    ViolationCategory.CHILD_FACE:   (255, 200,   0),   # Açık mavi (BGR)
    ViolationCategory.PRIVATE_PLATE:(200, 200, 200),   # Gri (BGR)
}

LABEL_MAP: dict[str, ViolationCategory] = {
    # Sigara (custom model + smoking model etiketleri)
    "cigarette":     ViolationCategory.CIGARETTE,
    "smoking":       ViolationCategory.CIGARETTE,
    "smooking":      ViolationCategory.CIGARETTE,
    "smoke":         ViolationCategory.CIGARETTE,
    "cigar":         ViolationCategory.CIGARETTE,
    "pipe":          ViolationCategory.CIGARETTE,
    # Silah (weapon_detector modeli)
    "weapon":        ViolationCategory.WEAPON,
    "grenade":       ViolationCategory.WEAPON,  # detector.py'de %82+ filtreli
    "knife":         ViolationCategory.WEAPON,
    "pistol":        ViolationCategory.WEAPON,
    "rifle":         ViolationCategory.WEAPON,
    "shotgun":       ViolationCategory.WEAPON,
    "handgun":       ViolationCategory.WEAPON,
    "gun":           ViolationCategory.WEAPON,
    "scissors":      ViolationCategory.WEAPON,
    # Alkol
    "wine glass":    ViolationCategory.ALCOHOL,
    "wine_glass":    ViolationCategory.ALCOHOL,
    "beer":          ViolationCategory.ALCOHOL,
    "bottle":        ViolationCategory.ALCOHOL,
    "cup":           ViolationCategory.ALCOHOL,
    "alcohol":       ViolationCategory.ALCOHOL,
    # Uygunsuz içerik
    "nudity":        ViolationCategory.NUDITY,
    "explicit":      ViolationCategory.NUDITY,
    "nsfw":          ViolationCategory.NUDITY,
    # Kan/şiddet
    "blood":         ViolationCategory.BLOOD,
    "wound":         ViolationCategory.BLOOD,
    "injury":        ViolationCategory.BLOOD,
    # Uyuşturucu
    "drug":          ViolationCategory.DRUG,
    "drugs":         ViolationCategory.DRUG,
    "syringe":       ViolationCategory.DRUG,
}


def label_to_category(label: str) -> ViolationCategory | None:
    return LABEL_MAP.get(label.lower().strip())
