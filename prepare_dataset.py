"""
Görselleri train/val olarak böl.
dataset/raw/ klasörüne etiketlenmiş görselleri koyun, sonra bu scripti çalıştırın.

Klasör yapısı (LabelImg ile etiketleme sonrası):
  dataset/raw/
    gorsel1.jpg
    gorsel1.txt   ← YOLO formatı etiket
    gorsel2.jpg
    gorsel2.txt
    ...
"""
import os
import shutil
import random
from pathlib import Path

RAW_DIR = Path("dataset/raw")
TRAIN_IMG = Path("dataset/images/train")
VAL_IMG = Path("dataset/images/val")
TRAIN_LBL = Path("dataset/labels/train")
VAL_LBL = Path("dataset/labels/val")

for d in [TRAIN_IMG, VAL_IMG, TRAIN_LBL, VAL_LBL]:
    d.mkdir(parents=True, exist_ok=True)

# Etiketli görselleri bul
images = list(RAW_DIR.glob("*.jpg")) + list(RAW_DIR.glob("*.png"))
labeled = [img for img in images if (RAW_DIR / (img.stem + ".txt")).exists()]

if not labeled:
    print("HATA: dataset/raw/ klasöründe etiketli görsel bulunamadı.")
    print("LabelImg ile etiketleyip .txt dosyalarını aynı klasöre koyun.")
    exit(1)

random.shuffle(labeled)
split = int(len(labeled) * 0.8)
train_imgs = labeled[:split]
val_imgs = labeled[split:]

for imgs, img_dir, lbl_dir in [(train_imgs, TRAIN_IMG, TRAIN_LBL),
                                (val_imgs, VAL_IMG, VAL_LBL)]:
    for img in imgs:
        shutil.copy(img, img_dir / img.name)
        lbl = RAW_DIR / (img.stem + ".txt")
        shutil.copy(lbl, lbl_dir / lbl.name)

print(f"Toplam: {len(labeled)} görsel")
print(f"Train: {len(train_imgs)} | Val: {len(val_imgs)}")
print("Dataset hazır. Şimdi train.py'yi çalıştırın.")
