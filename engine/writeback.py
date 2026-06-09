"""回写 (M3)：把续写产出的"回写卡"解析成标准卡片，回灌知识层。

续写一章后，模型给出一张回写卡(JSON)，描述这章产生的记忆增量：
  - synopsis：本章梗概(转述)
  - foreshadows_resolved：回收了哪些旧伏笔(id + paid_at)
  - new_foreshadows：本章新埋的伏笔
  - character_updates：相关人物在本章的新状态

`cards_from_writeback` 把它解析成标准卡片列表，交给 ingest 灌库：
  - 回收伏笔 → 复制原卡、改 status=paid（保留 planted_at/description），靠 upsert 覆盖
  - 人物更新 → 只含新 state 的卡，靠 ingest 的人物合并并入 states
这样"写一章 → 记一章 → 下一章接着记得"形成闭环。
"""
from __future__ import annotations

from typing import Optional

from .schema import (
    BaseCard,
    CharacterCard,
    CharacterState,
    ChapterSynopsis,
    ForeshadowLedger,
    ForeshadowStatus,
)
from .structstore import StructStore


# 回写卡顶层字段示例：
# {
#   "series": "longzu",
#   "chapter": 317,
#   "synopsis": {"id":"SY-LZ-317","synopsis":"...","key_objects":[...],"emotional_turn":"..."},
#   "foreshadows_resolved": [{"id":"FS-LZ1-013","paid_at":317}],
#   "new_foreshadows": [{"id":"FS-LZ4-003","planted_at":317,"description":"...","note":"..."}],
#   "character_updates": [{"id":"CH-LZ1-001","status":"...","reality_cost":"..."}]
# }


def cards_from_writeback(wb: dict, store: Optional[StructStore] = None) -> list[BaseCard]:
    """把回写卡解析成标准卡片列表。

    store 用于查原卡(回收伏笔取 planted_at/description、人物更新取 name)；
    传 None 时退化为用回写卡里自带的字段。
    """
    chapter = wb["chapter"]
    cards: list[BaseCard] = []

    # 1) 本章梗概
    s = wb.get("synopsis")
    if s:
        cards.append(ChapterSynopsis(
            id=s["id"],
            chapter=s.get("chapter", chapter),
            synopsis=s.get("synopsis", ""),
            key_objects=s.get("key_objects", []),
            emotional_turn=s.get("emotional_turn", ""),
            source_locator=s.get("source_locator", f"续写·第{chapter}章"),
        ))

    # 2) 回收旧伏笔：复制原卡，改 paid（保留 planted_at/description/note）
    for r in wb.get("foreshadows_resolved", []):
        orig = store.get(r["id"]) if store else None
        paid_at = r.get("paid_at", chapter)
        if isinstance(orig, ForeshadowLedger):
            cards.append(orig.model_copy(update={
                "status": ForeshadowStatus.PAID, "paid_at": paid_at,
            }))
        else:  # 库里没有原卡：用回写卡自带信息构造
            cards.append(ForeshadowLedger(
                id=r["id"], planted_at=r.get("planted_at", chapter),
                description=r.get("description", ""),
                status=ForeshadowStatus.PAID, paid_at=paid_at,
            ))

    # 3) 新埋伏笔
    for nf in wb.get("new_foreshadows", []):
        cards.append(ForeshadowLedger(
            id=nf["id"], planted_at=nf.get("planted_at", chapter),
            description=nf.get("description", ""), note=nf.get("note", ""),
        ))

    # 4) 人物新状态：只含本章 state 的卡，靠 ingest 合并并入历史 states
    for cu in wb.get("character_updates", []):
        orig = store.get(cu["id"]) if store else None
        name = orig.name if isinstance(orig, CharacterCard) else cu.get("name", cu["id"])
        cards.append(CharacterCard(
            id=cu["id"], name=name,
            states=[CharacterState(
                chapter=cu.get("chapter", chapter),
                status=cu.get("status", ""),
                reality_cost=cu.get("reality_cost", ""),
            )],
        ))

    return cards
