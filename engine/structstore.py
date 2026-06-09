"""江南续写引擎 · 结构库 (M0)

SQLite 存储,负责"精确过滤"类查询(按章号、按 status),
与向量库的"语义召回"互补。对应架构文档 §4。
标准库 sqlite3,零外部依赖。
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from .schema import (
    BaseCard,
    CardType,
    CARD_CLASSES,
    ChapterSynopsis,
    ForeshadowLedger,
    ForeshadowStatus,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id          TEXT PRIMARY KEY,
    card_type   TEXT NOT NULL,
    chapter     INTEGER,          -- synopsis.chapter / foreshadow.planted_at
    status      TEXT,             -- foreshadow.status
    data        TEXT NOT NULL,    -- 完整卡片 JSON
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_type    ON cards(card_type);
CREATE INDEX IF NOT EXISTS idx_chapter ON cards(chapter);
CREATE INDEX IF NOT EXISTS idx_status  ON cards(status);
"""


def _index_fields(card: BaseCard) -> tuple[Optional[int], Optional[str]]:
    """从卡片抽取用于精确查询的列(chapter, status)。"""
    if isinstance(card, ChapterSynopsis):
        return card.chapter, None
    if isinstance(card, ForeshadowLedger):
        return card.planted_at, card.status.value
    return None, None


class StructStore:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)

    # 写 ------------------------------------------------------------------
    def upsert(self, card: BaseCard) -> None:
        chapter, status = _index_fields(card)
        self.conn.execute(
            "INSERT OR REPLACE INTO cards "
            "(id, card_type, chapter, status, data, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                card.id,
                card.card_type.value,
                chapter,
                status,
                card.model_dump_json(),
                card.created_at,
            ),
        )
        self.conn.commit()

    def upsert_many(self, cards) -> None:
        for c in cards:
            self.upsert(c)

    # 读 ------------------------------------------------------------------
    def get(self, card_id: str) -> Optional[BaseCard]:
        row = self.conn.execute(
            "SELECT card_type, data FROM cards WHERE id=?", (card_id,)
        ).fetchone()
        return self._load(row) if row else None

    def by_type(self, card_type: CardType) -> list[BaseCard]:
        rows = self.conn.execute(
            "SELECT card_type, data FROM cards WHERE card_type=?",
            (card_type.value,),
        ).fetchall()
        return [self._load(r) for r in rows]

    def open_foreshadows_before(self, chapter: int) -> list[ForeshadowLedger]:
        """续写第 N 章时,取此前所有尚未回收的伏笔。"""
        rows = self.conn.execute(
            "SELECT card_type, data FROM cards "
            "WHERE card_type=? AND chapter<=? AND status=? "
            "ORDER BY chapter",
            (CardType.FORESHADOW.value, chapter, ForeshadowStatus.OPEN.value),
        ).fetchall()
        return [self._load(r) for r in rows]

    def synopses_window(self, end_chapter: int, span: int = 3) -> list[ChapterSynopsis]:
        """取 [end_chapter-span+1, end_chapter] 的章节梗概,做邻近上下文。"""
        rows = self.conn.execute(
            "SELECT card_type, data FROM cards "
            "WHERE card_type=? AND chapter<=? AND chapter>? "
            "ORDER BY chapter",
            (CardType.SYNOPSIS.value, end_chapter, end_chapter - span),
        ).fetchall()
        return [self._load(r) for r in rows]

    # 内部 ----------------------------------------------------------------
    @staticmethod
    def _load(row) -> BaseCard:
        cls = CARD_CLASSES[CardType(row["card_type"])]
        return cls.model_validate_json(row["data"])

    def close(self) -> None:
        self.conn.close()
