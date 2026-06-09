"""江南续写引擎 · 检索 / 组装 / 校验 / 回写 (M2)

对应架构文档 §6 一次续写的数据流的中间环节。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import quotefree
from .schema import (
    CharacterCard,
    CharacterState,
    ChapterSynopsis,
    ForeshadowLedger,
    ForeshadowStatus,
)
from .skilladapter import SkillAdapter
from .structstore import StructStore
from .vectorstore import VectorStore


# ---- 检索 -----------------------------------------------------------------
@dataclass
class RetrievedContext:
    open_foreshadows: list[ForeshadowLedger] = field(default_factory=list)
    recent_synopses: list[ChapterSynopsis] = field(default_factory=list)
    character_states: list[tuple[str, Optional[CharacterState]]] = field(default_factory=list)
    fingerprint_hits: list[dict] = field(default_factory=list)
    setting_hits: list[dict] = field(default_factory=list)


def retrieve(intent, store: StructStore, vs: VectorStore) -> RetrievedContext:
    n = intent.target_chapter
    ctx = RetrievedContext()
    # 结构库:精确召回前情记忆
    ctx.open_foreshadows = store.open_foreshadows_before(n)
    ctx.recent_synopses = store.synopses_window(n - 1, span=3)
    for cid in intent.focus_character_ids:
        c = store.get(cid)
        if isinstance(c, CharacterCard):
            ctx.character_states.append((c.name, c.state_at(n - 1)))
    # 向量库:语义召回笔法与设定
    ctx.fingerprint_hits = vs.query(intent.goal, k=3, where={"type": "fingerprint"})
    ctx.setting_hits = vs.query(intent.goal, k=3, where={"type": "setting"})
    return ctx


# ---- prompt 组装 ----------------------------------------------------------
def build_prompt(skill: SkillAdapter, ctx: RetrievedContext, intent) -> str:
    parts: list[str] = []

    parts.append("# 系统 · 风格层(江南.skill)")
    if skill.available():
        parts.append(skill.protocol())
        parts.append("## 可选 preset 表\n" + skill.presets())
    else:
        parts.append("(警告:未找到 江南.skill,风格层缺失)")

    parts.append("\n# 记忆 · 前情(均为转述,不含原文)")
    if ctx.character_states:
        lines = [
            f"- {name}：{(st.status if st else '无记录')}"
            + (f"（成本：{st.reality_cost}）" if st and st.reality_cost else "")
            for name, st in ctx.character_states
        ]
        parts.append("人物当前状态：\n" + "\n".join(lines))
    if ctx.open_foreshadows:
        lines = [f"- [{f.id}] 第{f.planted_at}章埋：{f.description}（{f.note}）"
                 for f in ctx.open_foreshadows]
        parts.append("未回收伏笔：\n" + "\n".join(lines))
    if ctx.recent_synopses:
        lines = [f"- 第{s.chapter}章：{s.synopsis}" for s in ctx.recent_synopses]
        parts.append("邻近章节梗概：\n" + "\n".join(lines))
    if ctx.fingerprint_hits:
        lines = [f"- {h['text']}" for h in ctx.fingerprint_hits if h.get("score", 0) > 0]
        if lines:
            parts.append("可用笔法：\n" + "\n".join(lines))

    parts.append("\n# 任务")
    parts.append(
        f"续写第 {intent.target_chapter} 章。\n"
        f"目标 preset：{intent.preset}\n"
        f"本章走向：{intent.goal}\n"
        "要求：先立人物缺口与现实成本,让物/动作承重,段尾回疼;"
        "不复制任何原文句子,可保留专名。写完按 24 分评分门自检。"
    )
    return "\n\n".join(parts)


# ---- 校验 -----------------------------------------------------------------
@dataclass
class EvalResult:
    passed: bool
    quotefree_passed: bool
    gate_note: str
    quotefree_detail: str = ""


def evaluate(text: str, known_sources: Optional[list[str]] = None) -> EvalResult:
    """quote-free 真校验 + 24 分门占位。

    known_sources:本地持有的原文片段(仅临时比对,不存储)。
    生成文本若与任一片段高度重叠,判不通过。
    24 分门需 LLM 评审,M2 先占位(只校验正文非空)。
    """
    qf_passed = True
    qf_detail = "无参照原文,跳过比对"
    for src in known_sources or []:
        r = quotefree.scan(text, src)
        if not r.passed:
            qf_passed = False
            qf_detail = f"命中原文:{r.reason}｜「{r.lcs_sample}」"
            break

    gate_ok = bool(text.strip())
    gate_note = "正文非空(24 分门 LLM 评审待 M3 接入)" if gate_ok else "正文为空"

    return EvalResult(
        passed=qf_passed and gate_ok,
        quotefree_passed=qf_passed,
        gate_note=gate_note,
        quotefree_detail=qf_detail,
    )


# ---- 回写 -----------------------------------------------------------------
def writeback(intent, text: str, store: StructStore) -> dict:
    """生成通过后回写知识层:新增本章梗概、回收伏笔、追加人物状态。
    M2 的梗概为占位(取正文前段);M3 接入后由 LLM 概括。
    """
    syn = ChapterSynopsis(
        id=f"SY-{intent.target_chapter:03d}",
        chapter=intent.target_chapter,
        synopsis=text.strip()[:120] or "(空)",
        emotional_turn="(待 LLM 概括)",
        source_locator=None,
    )
    store.upsert(syn)

    paid = []
    for fid in intent.resolve_foreshadow_ids:
        c = store.get(fid)
        if isinstance(c, ForeshadowLedger):
            c.status = ForeshadowStatus.PAID
            c.paid_at = intent.target_chapter
            store.upsert(c)
            paid.append(fid)

    updated = []
    for cid, status_text in intent.character_updates.items():
        c = store.get(cid)
        if isinstance(c, CharacterCard):
            c.states.append(CharacterState(chapter=intent.target_chapter, status=status_text))
            store.upsert(c)
            updated.append(cid)

    return {
        "new_synopsis": syn.id,
        "paid_foreshadows": paid,
        "updated_characters": updated,
    }
