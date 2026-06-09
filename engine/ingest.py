"""江南续写引擎 · 知识灌注 (M1)

把 DS 蒸馏产出的卡片 JSON 批量导入结构库(StructStore)+ 向量库(VectorStore)。
支持单文件(.json / .jsonl)或整个目录。对应架构文档 §3、§10 M1。

DS 产出的每张卡必须带 `card_type` 字段(fingerprint/setting/character/foreshadow/synopsis),
字段见各卡 schema。卡片只含转述/机制/定位,不含原文(quote-free 在 DS 端约束)。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .schema import CARD_CLASSES, BaseCard, CardType, CharacterCard
from .structstore import StructStore
from .vectorstore import VectorStore


def _merge_character(old: CharacterCard, new: CharacterCard) -> CharacterCard:
    """跨卷同 id 人物卡合并：states 按章号取并集(同章以新卡为准)，
    文本字段优先保留已有非空值(首次出场卷通常最全)，relations 取并集。
    避免后续卷的简略卡覆盖掉早期完整状态。
    """
    by_ch = {s.chapter: s for s in old.states}
    for s in new.states:
        by_ch[s.chapter] = s
    merged_states = [by_ch[c] for c in sorted(by_ch)]
    return old.model_copy(update={
        "states": merged_states,
        "gap": old.gap or new.gap,
        "disguise": old.disguise or new.disguise,
        "name": old.name or new.name,
        "relations": sorted(set(old.relations) | set(new.relations)),
        "source_locator": old.source_locator or new.source_locator,
    })


@dataclass
class IngestReport:
    ingested: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    ids: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)  # (来源, 原因)

    def summary(self) -> str:
        by = "，".join(f"{k}:{v}" for k, v in sorted(self.by_type.items())) or "无"
        s = f"导入 {self.ingested} 张（{by}）"
        if self.errors:
            s += f"；{len(self.errors)} 条问题"
        return s


def card_from_dict(d: dict) -> BaseCard:
    """按 card_type 字段反序列化成对应卡片模型。"""
    if "card_type" not in d:
        raise ValueError("缺少 card_type 字段")
    ct = CardType(d["card_type"])
    return CARD_CLASSES[ct].model_validate(d)


def _iter_card_dicts(path: Path) -> Iterable[tuple[int, dict]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if line:
                yield i, json.loads(line)
    else:  # .json：单对象或数组
        data = json.loads(text)
        if isinstance(data, list):
            for i, obj in enumerate(data, 1):
                yield i, obj
        else:
            yield 1, data


def load_cards(path) -> tuple[list[BaseCard], list[tuple[str, str]]]:
    """从文件或目录读取卡片，返回 (卡片列表, 错误列表)。错误不中断。"""
    p = Path(path)
    files = (
        sorted(f for f in p.rglob("*") if f.suffix in (".json", ".jsonl"))
        if p.is_dir()
        else [p]
    )
    cards: list[BaseCard] = []
    errors: list[tuple[str, str]] = []
    for f in files:
        try:
            for idx, obj in _iter_card_dicts(f):
                try:
                    cards.append(card_from_dict(obj))
                except Exception as e:  # 单卡校验失败，记录后继续
                    cid = obj.get("id", "?") if isinstance(obj, dict) else "?"
                    errors.append((f"{f.name}#{idx}({cid})", str(e)))
        except Exception as e:  # 文件读取/JSON 解析失败
            errors.append((f.name, f"读取失败: {e}"))
    return cards, errors


def ingest(cards, store: StructStore, vs: VectorStore) -> IngestReport:
    """把卡片写入结构库 + 向量库。同一 id 重复出现只入一次(记为问题)。"""
    rep = IngestReport()
    seen: set[str] = set()
    for c in cards:
        # 人物卡：同 id 始终合并(并集 states)——无论同目录多文件还是跨卷，
        # 不依赖文件名顺序、不会因"重复跳过"丢失状态。
        if isinstance(c, CharacterCard):
            existing = store.get(c.id)
            if isinstance(existing, CharacterCard):
                c = _merge_character(existing, c)
            store.upsert(c)
            vs.add(c.id, c.embed_text(), {"type": c.card_type.value})
            if c.id not in seen:
                seen.add(c.id)
                rep.ingested += 1
                rep.by_type["character"] = rep.by_type.get("character", 0) + 1
                rep.ids.append(c.id)
            continue
        # 非人物卡：同 id 视为重复并记录(伏笔跨卷回收走 upsert 自然覆盖)
        if c.id in seen:
            rep.errors.append((c.id, "重复 id，跳过"))
            continue
        seen.add(c.id)
        store.upsert(c)
        vs.add(c.id, c.embed_text(), {"type": c.card_type.value})
        rep.ingested += 1
        rep.by_type[c.card_type.value] = rep.by_type.get(c.card_type.value, 0) + 1
        rep.ids.append(c.id)
    return rep


def ingest_path(path, store: StructStore, vs: VectorStore) -> IngestReport:
    """便捷入口：从路径加载 + 灌注，合并两阶段的错误。"""
    cards, load_errors = load_cards(path)
    rep = ingest(cards, store, vs)
    rep.errors = load_errors + rep.errors
    return rep
