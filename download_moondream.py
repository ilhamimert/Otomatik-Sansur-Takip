"""
Moondream2 modelini HuggingFace'den indir ve models/moondream2 klasörüne kaydet.
Sadece bir kez çalıştırılması gerekir. Sonrasında tamamen offline çalışır.

Kullanım:
    python download_moondream.py
"""
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM

SAVE_DIR = Path("models/moondream2")
HF_REPO  = "vikhyatk/moondream2"
REVISION = "2024-08-26"  # pyvips gerektirmeyen son stabil sürüm

def main():
    if SAVE_DIR.exists() and any(SAVE_DIR.iterdir()):
        print(f"Model zaten mevcut: {SAVE_DIR}")
        return

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Moondream2 indiriliyor: {HF_REPO} ({REVISION})")
    print("Bu işlem ~2GB indirme yapacak, bir kez çalıştırın...")

    tokenizer = AutoTokenizer.from_pretrained(HF_REPO, revision=REVISION, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(HF_REPO, revision=REVISION, trust_remote_code=True)

    tokenizer.save_pretrained(str(SAVE_DIR))
    model.save_pretrained(str(SAVE_DIR))
    print(f"\nModel kaydedildi: {SAVE_DIR}")
    print("Artık program tamamen offline çalışır.")

if __name__ == "__main__":
    main()