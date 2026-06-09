"""江南续写引擎 · 知识层卡片 schema (M0)

五类卡片的 pydantic 模型。所有文本字段都是转述/机制/定位,
不含源作品原文句子(quote-free)。人物/地点专名按项目决定保留原名。
对应架构文档 §3。
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CardType(str, Enum):
    FINGERPRINT = "fingerprint"   # 笔法机制卡
    SETTING = "setting"           # 世界设定卡
    CHARACTER = "character"       # 人物状态卡
    FORESHADOW = "foreshadow"     # 伏笔台账
    SYNOPSIS = "synopsis"         # 章节转述梗概


class ForeshadowStatus(str, Enum):
    OPEN = "open"            # 已埋,未回收
    PAID = "paid"            # 已回收
    ABANDONED = "abandoned"  # 弃用


class BaseCard(BaseModel):
    """所有卡片的公共字段。"""
    id: str
    card_type: CardType
    source_locator: Optional[str] = None  # 原著章/场景定位,绝不含原句
    created_at: str = Field(default_factory=_now)

    def embed_text(self) -> str:
        """返回用于向量化的文本,子类覆盖。"""
        raise NotImplementedError


# §3.1 笔法机制卡 -----------------------------------------------------------
class FingerprintCard(BaseCard):
    card_type: CardType = CardType.FINGERPRINT
    mechanism: str               # 机制名,如"物/动作替代心理"
    stage_config: str = ""       # 适用阶段/配置,如 P4 少年被卷入
    when_to_use: str = ""        # 触发条件(转述)
    how: str = ""                # 操作要点(转述)

    def embed_text(self) -> str:
        return f"{self.mechanism}。{self.when_to_use} {self.how}".strip()


# §3.2 世界设定卡 -----------------------------------------------------------
class SettingCard(BaseCard):
    card_type: CardType = CardType.SETTING
    name: str                    # 设定名(保留原专名)
    kind: str = ""               # 组织/地点/力量体系/规则
    summary: str = ""            # 转述摘要
    constraints: list[str] = Field(default_factory=list)  # 硬约束

    def embed_text(self) -> str:
        return f"{self.name}（{self.kind}）。{self.summary}".strip()


# §3.3 人物状态卡 -----------------------------------------------------------
class CharacterState(BaseModel):
    """人物在某一章的状态快照,按章节版本化。"""
    chapter: int
    status: str                  # 状态描述(转述)
    reality_cost: str = ""       # 此刻他在为什么付代价(v1.1.1 成本层)


class CharacterCard(BaseCard):
    card_type: CardType = CardType.CHARACTER
    name: str                    # 人物名(保留原名)
    gap: str = ""                # 人物缺口(江南感核心)
    disguise: str = ""           # 伪装
    relations: list[str] = Field(default_factory=list)        # 指向其它 CH-id
    states: list[CharacterState] = Field(default_factory=list)

    def state_at(self, chapter: int) -> Optional[CharacterState]:
        """返回截至 chapter(含)的最新状态快照。"""
        prior = [s for s in self.states if s.chapter <= chapter]
        return max(prior, key=lambda s: s.chapter) if prior else None

    def embed_text(self) -> str:
        return f"{self.name}。缺口：{self.gap} 伪装：{self.disguise}".strip()


# §3.4 伏笔台账 -------------------------------------------------------------
class ForeshadowLedger(BaseCard):
    card_type: CardType = CardType.FORESHADOW
    planted_at: int              # 埋设章节
    description: str = ""        # 伏笔内容(转述)
    status: ForeshadowStatus = ForeshadowStatus.OPEN
    paid_at: Optional[int] = None  # 回收章节
    note: str = ""               # 续写时如何圆

    def embed_text(self) -> str:
        return f"{self.description} {self.note}".strip()


# §3.5 章节转述梗概 ---------------------------------------------------------
class ChapterSynopsis(BaseCard):
    card_type: CardType = CardType.SYNOPSIS
    chapter: int
    synopsis: str = ""           # 自己的话复述本章,120-300 字
    key_objects: list[str] = Field(default_factory=list)  # 承重小物/动作
    emotional_turn: str = ""     # 情绪转折点

    def embed_text(self) -> str:
        return self.synopsis.strip()


CARD_CLASSES = {
    CardType.FINGERPRINT: FingerprintCard,
    CardType.SETTING: SettingCard,
    CardType.CHARACTER: CharacterCard,
    CardType.FORESHADOW: ForeshadowLedger,
    CardType.SYNOPSIS: ChapterSynopsis,
}
