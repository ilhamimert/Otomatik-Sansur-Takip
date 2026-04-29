# REST API & Job Queue — Mimari Doküman

## Genel Bakış

Mevcut sistem dosya tabanlı (WatchFolder input/). Bu entegrasyon HTTP arayüzü ekler:
video yükleme, servis kontrolü, kuyruk izleme ve rapor sorgulama.

---

## Akış Diyagramı

```
HTTP Client
    │
    ▼
┌─────────────────────────────┐
│  FastAPI  :8000             │
│  POST /upload               │
│  GET  /status               │
│  POST /start  /stop         │
│  GET  /queue                │
│  GET  /reports/{id}         │
└────────────┬────────────────┘
             │ enqueue(job)
             ▼
┌─────────────────────────────┐
│  JobQueue  (in-memory)      │
│  pending  → deque[Job]      │
│  processing → dict[id,Job]  │
│  done     → list[Job]       │
└────────────┬────────────────┘
             │ dequeue
             ▼
┌─────────────────────────────┐
│  WatchFolder                │
│  ThreadPoolExecutor(n=2)    │
│  ScanWorker per video       │
└────────────┬────────────────┘
             │ on_done(report)
             ▼
┌─────────────────────────────┐
│  ReportWriter               │
│  TXT → output/              │
│  dict → job.report          │
└─────────────────────────────┘
```

---

## Endpoint Tablosu

| Method | Path | Açıklama |
|--------|------|----------|
| `GET` | `/api/status` | Servis durumu + kuyruk özeti |
| `POST` | `/api/start` | WatchFolder'ı başlat |
| `POST` | `/api/stop` | WatchFolder'ı durdur |
| `POST` | `/api/upload` | Video yükle (multipart/form-data) |
| `GET` | `/api/queue` | pending / processing / done listesi |
| `GET` | `/api/reports` | Tüm tamamlanan raporlar |
| `GET` | `/api/reports/{job_id}` | Tek raporun detayı |

---

## Veri Modeli

```python
@dataclass
class Job:
    id: str               # uuid4
    filename: str
    filepath: str
    status: str           # pending | processing | done | failed
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    report: dict | None = None
    error: str | None = None
```

### `/api/status` Örnek Yanıt
```json
{
  "running": true,
  "uptime_seconds": 142,
  "queue": {
    "pending": 3,
    "processing": 2,
    "done": 17,
    "failed": 0
  }
}
```

### `/api/queue` Örnek Yanıt
```json
{
  "pending": [
    {"id": "abc123", "filename": "video1.mp4", "created_at": "2026-04-29T10:00:00"}
  ],
  "processing": [
    {"id": "def456", "filename": "video2.mp4", "started_at": "2026-04-29T10:01:00"}
  ],
  "done": [...]
}
```

---

## Dosya Değişiklikleri

| Dosya | Durum | Değişim |
|-------|-------|---------|
| `service/job_queue.py` | 🆕 Yeni | JobQueue + Job dataclass |
| `api/__init__.py` | 🆕 Yeni | Boş init |
| `api/server.py` | 🆕 Yeni | FastAPI router + endpoint'ler |
| `run_server.py` | 🆕 Yeni | uvicorn başlatıcı |
| `service/watchfolder.py` | ✏️ Güncelle | job_queue entegrasyonu |
| `service/report_writer.py` | ✏️ Güncelle | `dict` döndür |
| `requirements.txt` | ✏️ Güncelle | fastapi, uvicorn, python-multipart |

---

## Kurulum

```bash
pip install fastapi uvicorn python-multipart
python run_server.py          # http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

---

## Konfigürasyon (config.yaml eklentisi)

```yaml
api:
  host: "0.0.0.0"
  port: 8000
  upload_dir: "WatchFolder/input"
```

---

## Doğrulama Adımları

1. `python run_server.py` → sunucu ayağa kalkar
2. `GET /api/status` → `running: true` döner
3. `POST /api/upload` ile `.mp4` gönder → `job_id` alınır
4. `GET /api/queue` → video `processing` statüsünde görünür
5. Tarama bitince `GET /api/reports/{job_id}` → ihlal listesi döner
6. `POST /api/stop` → `GET /api/status` `running: false` gösterir
