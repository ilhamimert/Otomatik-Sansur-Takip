from __future__ import annotations
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from ai.label_map import ViolationCategory


@dataclass
class ViolationRecord:
    video_path: str
    frame_number: int
    timestamp_sec: float
    timestamp_str: str
    category: ViolationCategory
    label: str
    confidence: float
    bbox: tuple         # (x1, y1, x2, y2)
    is_selected: bool = False
    is_false_positive: bool = False
    thumbnail: bytes = field(default=b"", repr=False)
    id: int = -1


class ViolationStore:
    def __init__(self, db_path: str = "data/violations.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                video_path       TEXT NOT NULL,
                frame_number     INTEGER NOT NULL,
                timestamp_sec    REAL NOT NULL,
                timestamp_str    TEXT NOT NULL,
                category         TEXT NOT NULL,
                label            TEXT NOT NULL,
                confidence       REAL NOT NULL,
                bbox_x1          INTEGER,
                bbox_y1          INTEGER,
                bbox_x2          INTEGER,
                bbox_y2          INTEGER,
                is_selected      INTEGER DEFAULT 0,
                is_false_positive INTEGER DEFAULT 0,
                thumbnail        BLOB
            )
        """)
        self._conn.commit()
        self._migrate_add_false_positive()

    def _migrate_add_false_positive(self):
        """Eski DB'ye is_false_positive kolonu ekle (idempotent)."""
        cur = self._conn.execute("PRAGMA table_info(violations)")
        columns = {row[1] for row in cur.fetchall()}
        if "is_false_positive" not in columns:
            self._conn.execute(
                "ALTER TABLE violations ADD COLUMN is_false_positive INTEGER DEFAULT 0"
            )
            self._conn.commit()

    def save(self, rec: ViolationRecord) -> int:
        x1, y1, x2, y2 = rec.bbox
        cur = self._conn.execute("""
            INSERT INTO violations
            (video_path, frame_number, timestamp_sec, timestamp_str,
             category, label, confidence,
             bbox_x1, bbox_y1, bbox_x2, bbox_y2,
             is_selected, is_false_positive, thumbnail)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (rec.video_path, rec.frame_number, rec.timestamp_sec, rec.timestamp_str,
              rec.category.name, rec.label, rec.confidence,
              x1, y1, x2, y2,
              int(rec.is_selected), int(rec.is_false_positive), rec.thumbnail))
        self._conn.commit()
        rec.id = cur.lastrowid
        return rec.id

    def load_for_video(self, video_path: str) -> list[ViolationRecord]:
        cur = self._conn.execute(
            "SELECT * FROM violations WHERE video_path=? ORDER BY frame_number",
            (video_path,))
        return [self._row_to_record(r) for r in cur.fetchall()]

    def update_selection(self, record_id: int, selected: bool):
        self._conn.execute("UPDATE violations SET is_selected=? WHERE id=?",
                           (int(selected), record_id))
        self._conn.commit()

    def update_false_positive(self, record_id: int, is_fp: bool):
        self._conn.execute("UPDATE violations SET is_false_positive=? WHERE id=?",
                           (int(is_fp), record_id))
        self._conn.commit()

    def clear_for_video(self, video_path: str):
        self._conn.execute("DELETE FROM violations WHERE video_path=?", (video_path,))
        self._conn.commit()

    def _row_to_record(self, row) -> ViolationRecord:
        (rid, vp, fn, ts, ts_str, cat, lbl, conf,
         x1, y1, x2, y2, sel, fp, thumb) = row
        return ViolationRecord(
            id=rid,
            video_path=vp,
            frame_number=fn,
            timestamp_sec=ts,
            timestamp_str=ts_str,
            category=ViolationCategory[cat],
            label=lbl,
            confidence=conf,
            bbox=(x1, y1, x2, y2),
            is_selected=bool(sel),
            is_false_positive=bool(fp),
            thumbnail=thumb or b"",
        )

    def close(self):
        self._conn.close()
