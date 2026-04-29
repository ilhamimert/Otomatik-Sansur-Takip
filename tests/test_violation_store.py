import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.violation_store import ViolationStore, ViolationRecord
from ai.label_map import ViolationCategory


def make_record(**kwargs) -> ViolationRecord:
    defaults = dict(
        video_path="/test/video.mp4",
        frame_number=100,
        timestamp_sec=4.0,
        timestamp_str="00:04",
        category=ViolationCategory.CIGARETTE,
        label="cigarette",
        confidence=0.87,
        bbox=(10, 20, 100, 200),
    )
    defaults.update(kwargs)
    return ViolationRecord(**defaults)


def test_save_and_load():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = ViolationStore(db_path)
    rec = make_record()
    rid = store.save(rec)
    assert rid > 0

    records = store.load_for_video("/test/video.mp4")
    assert len(records) == 1
    assert records[0].category == ViolationCategory.CIGARETTE
    assert records[0].confidence == 0.87
    store.close()
    os.unlink(db_path)


def test_update_selection():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = ViolationStore(db_path)
    rec = make_record()
    rid = store.save(rec)
    store.update_selection(rid, True)
    records = store.load_for_video("/test/video.mp4")
    assert records[0].is_selected is True
    store.close()
    os.unlink(db_path)


def test_update_false_positive():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = ViolationStore(db_path)
    rec = make_record()
    rid = store.save(rec)
    store.update_false_positive(rid, True)
    records = store.load_for_video("/test/video.mp4")
    assert records[0].is_false_positive is True
    store.close()
    os.unlink(db_path)


def test_clear_for_video():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = ViolationStore(db_path)
    store.save(make_record())
    store.save(make_record(frame_number=200))
    store.clear_for_video("/test/video.mp4")
    records = store.load_for_video("/test/video.mp4")
    assert records == []
    store.close()
    os.unlink(db_path)
