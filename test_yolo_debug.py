"""
YOLO debug testi — uygulamayı açmadan direkt YOLO çıktısını gösterir.
Kullanım: venv/Scripts/python.exe test_yolo_debug.py "video.mp4"
"""
import sys
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

video_path = sys.argv[1] if len(sys.argv) > 1 else None
if not video_path:
    print("Kullanım: python test_yolo_debug.py <video_dosyasi>")
    sys.exit(1)

from ai.model_manager import ModelManager
from ai.detector import Detector

print("Model yükleniyor...")
mgr = ModelManager()
model = mgr.load({})
detector = Detector(model, confidence=0.25)   # düşük threshold ile dene

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 25
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Video: {Path(video_path).name}  |  {total} kare  |  {fps:.1f} fps")
print("-" * 50)

frame_no = 0
found = 0
checked = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    if frame_no % 5 == 0:   # her 5 karede bir bak
        checked += 1
        dets = detector.detect(frame)
        if dets:
            for d in dets:
                print(f"  Kare {frame_no:5d} ({frame_no/fps:.1f}s)  →  "
                      f"{d.label:<20} conf={d.confidence:.3f}  cat={d.category.value}")
                found += 1
    frame_no += 1

cap.release()
print("-" * 50)
print(f"Taranan kare: {checked}  |  Toplam tespit: {found}")
if found == 0:
    print("SONUÇ: YOLO hiçbir şey bulmadı → model veya video sorunu")
else:
    print("SONUÇ: YOLO tespit etti → sorun CLIP doğrulayıcıda olabilir")