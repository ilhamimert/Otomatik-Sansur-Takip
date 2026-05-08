# Otomatik Sansür Takip — AI Vision Guard

YOLO11n tabanlı otomatik video içerik denetim sistemi. Video kayıtlarını gerçek zamanlı olarak tarar, alkol, silah, uyuşturucu, çıplaklık gibi içerikleri tespit eder ve raporlar.

## Özellikler

- **Otomatik Tespit** — YOLO11n modeli ile video içerik analizi
- **OpenVINO Hızlandırma** — Intel CPU'larda optimizasyon
- **Watchfolder** — Belirtilen klasörü izler, gelen videoları otomatik tarar
- **REST API** — FastAPI ile HTTP üzerinden entegrasyon
- **Masaüstü Arayüzü** — PyQt6 ile Türkçe koyu tema arayüzü
- **Dışa Aktarma** — Tespit edilen kareler bulanıklaştırılarak dışa aktarılır
- **Offline** — Model indirildikten sonra internetsiz çalışır

## Tespit Kategorileri

| Kategori | Varsayılan |
|----------|-----------|
| Alkol | Açık |
| Kan | Açık |
| Sigara | Açık |
| Uyuşturucu | Açık |
| Çıplaklık | Açık |
| Silah | Açık |
| Çocuk yüzü | Kapalı |
| Özel plaka | Kapalı |

## Kurulum

```bash
git clone https://github.com/ilhamimert/Otomatik-Sansur-Takip.git
cd Otomatik-Sansur-Takip
pip install -r requirements.txt
```

Modeli indir:

```bash
python download_moondream.py
```

## Kullanım

### Masaüstü Arayüzü

```bash
python main.py
```

veya

```bash
launch.bat
```

### REST API Sunucusu

```bash
python run_server.py
```

API dokümantasyonu: `http://localhost:8000/docs`

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/status` | Servis durumu |
| `POST /api/start` | Taramayı başlat |
| `POST /api/stop` | Taramayı durdur |
| `POST /api/upload` | Video yükle |
| `GET /api/queue` | İş kuyruğunu görüntüle |
| `GET /api/reports` | Tüm raporlar |
| `GET /api/reports/{job_id}` | Belirli iş raporu |

### Windows Servisi

```bash
service_install.bat   # Servisi kur
service_remove.bat    # Servisi kaldır
```

## Yapılandırma

`config.yaml` üzerinden ayarlar değiştirilebilir:

```yaml
scan:
  confidence_threshold: 0.5   # Güven eşiği
  frame_skip: 5               # Her 5 karede bir tara

export:
  blur_intensity: high        # Bulanıklaştırma şiddeti

service:
  watch_dir: "C:/videos"      # İzlenecek klasör
  max_workers: 2              # Paralel iş sayısı
```

## Proje Yapısı

```
├── ai/         ← YOLO dedektör, CLIP doğrulayıcı
├── api/        ← FastAPI sunucusu
├── core/       ← Tarama ve dışa aktarma motorları
├── service/    ← Watchfolder, iş kuyruğu
├── ui/         ← PyQt6 arayüzü
├── utils/      ← Logger, video araçları
├── main.py     ← Masaüstü uygulaması giriş noktası
├── run_server.py ← API sunucusu
└── config.yaml ← Yapılandırma
```

## Teknik Stack

| Bileşen | Teknoloji |
|---------|-----------|
| Nesne Tespiti | YOLO11n (Ultralytics) |
| Hızlandırma | OpenVINO, ONNX Runtime |
| Arayüz | PyQt6 |
| API | FastAPI + uvicorn |
| Görüntü İşleme | OpenCV, Pillow |