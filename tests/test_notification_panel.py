"""
NotificationPanel widget testi — gerçek DB olmadan mock ViolationStore ile çalışır.
Çalıştır: venv/Scripts/python.exe -m pytest tests/test_notification_panel.py -v
"""
from __future__ import annotations

import sys
import os
# Qt uygulaması olmadan test yapabilmek için
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)


from unittest.mock import MagicMock
from ai.label_map import ViolationCategory
from core.violation_store import ViolationRecord


def _make_record(
    record_id: int = 1,
    category: ViolationCategory = ViolationCategory.CIGARETTE,
    confidence: float = 0.85,
    selected: bool = False,
    is_fp: bool = False,
) -> ViolationRecord:
    return ViolationRecord(
        id=record_id,
        video_path="test.mp4",
        frame_number=100 * record_id,
        timestamp_sec=4.0 * record_id,
        timestamp_str=f"00:00:0{record_id}",
        category=category,
        label=category.name.lower(),
        confidence=confidence,
        bbox=(10, 10, 100, 100),
        is_selected=selected,
        is_false_positive=is_fp,
        thumbnail=b"",
    )


def _make_store() -> MagicMock:
    store = MagicMock()
    store.update_selection = MagicMock()
    store.update_false_positive = MagicMock()
    return store


# ── Testler ──────────────────────────────────────────────────────────────────

class TestNotificationPanel:
    def setup_method(self):
        from ui.notification_panel import NotificationPanel
        self._store = _make_store()
        self._panel = NotificationPanel(self._store)

    def test_baslangicta_bos(self):
        assert self._panel.get_all_records() == []
        assert self._panel.get_selected() == []

    def test_ihlal_ekleme(self):
        rec = _make_record(1)
        self._panel.add_violation(rec)
        assert len(self._panel.get_all_records()) == 1

    def test_birden_fazla_ihlal(self):
        for i in range(1, 6):
            self._panel.add_violation(_make_record(i))
        assert len(self._panel.get_all_records()) == 5

    def test_tumunu_sec(self):
        for i in range(1, 4):
            self._panel.add_violation(_make_record(i))
        self._panel.select_all()
        assert all(r.is_selected for r in self._panel.get_all_records())

    def test_secimi_temizle(self):
        for i in range(1, 4):
            self._panel.add_violation(_make_record(i, selected=True))
        self._panel.deselect_all()
        assert all(not r.is_selected for r in self._panel.get_all_records())

    def test_get_selected_filtreler(self):
        self._panel.add_violation(_make_record(1, selected=True))
        self._panel.add_violation(_make_record(2, selected=False))
        self._panel.add_violation(_make_record(3, selected=True))
        selected = self._panel.get_selected()
        assert len(selected) == 2
        assert all(r.is_selected for r in selected)

    def test_clear(self):
        for i in range(1, 4):
            self._panel.add_violation(_make_record(i))
        self._panel.clear()
        assert self._panel.get_all_records() == []
        assert self._panel.get_selected() == []

    def test_select_all_store_cagrilir(self):
        for i in range(1, 3):
            self._panel.add_violation(_make_record(i))
        self._panel.select_all()
        assert self._store.update_selection.call_count == 2

    def test_deselect_all_store_cagrilir(self):
        for i in range(1, 3):
            self._panel.add_violation(_make_record(i, selected=True))
        self._panel.deselect_all()
        assert self._store.update_selection.call_count == 2

    def test_farkli_kategoriler(self):
        cats = list(ViolationCategory)
        for i, cat in enumerate(cats, start=1):
            self._panel.add_violation(_make_record(i, category=cat))
        assert len(self._panel.get_all_records()) == len(cats)


class TestWatchFolderService:
    """WatchFolderService unit testleri — dosya sistemi mock'lanır."""

    def test_baslangicta_durmuş(self):
        from core.watch_folder import WatchFolderService
        svc = WatchFolderService("/tmp/test_watch", on_new_video=lambda _: None)
        assert not svc.is_running

    def test_folder_property(self):
        from core.watch_folder import WatchFolderService
        svc = WatchFolderService("/tmp/test_watch", on_new_video=lambda _: None)
        assert svc.folder == "/tmp/test_watch"

    def test_stop_durmuş_servise_guvenli(self):
        from core.watch_folder import WatchFolderService
        svc = WatchFolderService("/tmp/test_watch", on_new_video=lambda _: None)
        svc.stop()   # hata vermemeli
        assert not svc.is_running