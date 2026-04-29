"""
TXT rapor üreticisi. Tarama sonucunu standart rapor formatına çevirir.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from service.scan_worker import ScanReport

CATEGORY_LABELS = {
    "CIGARETTE":     "SİGARA",
    "ALCOHOL":       "ALKOL",
    "NUDITY":        "UYGUNSUZ İÇERİK",
    "WEAPON":        "SİLAH",
    "BLOOD":         "KAN / ŞİDDET",
    "DRUG":          "UYUŞTURUCU",
    "CHILD_FACE":    "ÇOCUK YÜZÜ",
    "PRIVATE_PLATE": "PLAKA",
}


def write_txt_report(report: ScanReport, output_dir: str) -> str:
    """
    Raporu TXT dosyasına yazar. Dosya yolunu döndürür.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    stem = Path(report.video_name).stem
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{stem}_{now}.txt"
    full_path = out_path / filename

    lines = _build_report_lines(report)
    full_path.write_text("\n".join(lines), encoding="utf-8")
    return str(full_path)


def _build_report_lines(report: ScanReport) -> list[str]:
    sep = "=" * 60
    thin = "-" * 60
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration = _format_duration(report.duration_sec)

    lines = [
        sep,
        "  CNBC TÜRK — İÇERİK TARAMA RAPORU",
        sep,
        f"  Dosya      : {report.video_name}",
        f"  Tarih      : {now}",
        f"  Süre       : {duration}",
        f"  Kare sayısı: {report.total_frames}  |  Taranan: {report.scanned_frames}",
        sep,
    ]

    if report.error:
        lines += [
            f"  HATA: {report.error}",
            sep,
        ]
        return lines

    if not report.violations:
        lines += [
            "  Herhangi bir ihlal tespit edilmedi.",
            sep,
        ]
        return lines

    lines.append(f"  Toplam ihlal: {len(report.violations)}")
    lines.append(thin)
    lines.append(f"  {'ZAMAN':<14} {'KATEGORİ':<22} {'DETAY':<22} {'GÜVEN'}")
    lines.append(thin)

    for v in sorted(report.violations, key=lambda x: x.timestamp_sec):
        cat_label = CATEGORY_LABELS.get(v.category.name, v.category.name)
        detail = v.label.replace("_", " ").title()
        conf_pct = f"%{v.confidence * 100:.0f}"
        thumb = f"  → {Path(v.thumbnail_path).name}" if v.thumbnail_path else ""
        lines.append(f"  [{v.timestamp_str}]  {cat_label:<22} {detail:<22} {conf_pct}{thumb}")

    lines.append(sep)

    cat_counts: dict[str, int] = {}
    for v in report.violations:
        cat_label = CATEGORY_LABELS.get(v.category.name, v.category.name)
        cat_counts[cat_label] = cat_counts.get(cat_label, 0) + 1

    lines.append("  KATEGORİ ÖZETİ")
    lines.append(thin)
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat:<30} {count} ihlal")

    lines.append(sep)
    return lines


def _format_duration(sec: float) -> str:
    total = int(sec)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
