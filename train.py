"""
Sigara tespit modeli eğitimi.
prepare_dataset.py'yi çalıştırdıktan sonra bu scripti başlatın.
"""
from ultralytics import YOLO
from pathlib import Path

# Mevcut smoking modelini base al (sıfırdan değil, fine-tune)
BASE_MODEL = "models/smoking_detector.onnx"
# ONNX'ten fine-tune olmaz, yolo11n.pt'yi base alalım
BASE_MODEL = "models/yolo11n.pt"

DATASET = str(Path("dataset/dataset.yaml").absolute())
EPOCHS = 20        # Az veri için 20 epoch yeterli
IMG_SIZE = 320     # 640 yerine 320 — 4x daha hızlı
BATCH = 8          # Daha büyük batch = daha hızlı

print(f"Eğitim başlıyor...")
print(f"Base model: {BASE_MODEL}")
print(f"Dataset: {DATASET}")
print(f"Epochs: {EPOCHS}")
print()

model = YOLO(BASE_MODEL)

results = model.train(
    data=DATASET,
    epochs=EPOCHS,
    imgsz=IMG_SIZE,
    batch=BATCH,
    name="cigarette_custom",
    project="models/training",
    exist_ok=True,
    patience=15,       # 15 epoch iyileşme yoksa dur
    device="cpu",
    workers=0,         # Windows'ta multiprocessing sorunu olmasın
    verbose=True,
    augment=True,      # Az veri için augmentation önemli
    degrees=10,        # Hafif döndürme
    flipud=0.0,
    fliplr=0.5,
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
)

# En iyi modeli ana models klasörüne kopyala
import shutil
best = Path("runs/detect/models/training/cigarette_custom/weights/best.pt")
if best.exists():
    shutil.copy(best, "models/cigarette_custom.pt")
    print(f"\nEğitim tamamlandı!")
    print(f"Model kaydedildi: models/cigarette_custom.pt")
    print(f"Uygulamayı açın ve Ayarlar'dan yeni modeli seçin.")
else:
    print("HATA: En iyi model bulunamadı.")
