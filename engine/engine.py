"""江南续写引擎 · 主循环 (M2)

ContinuationEngine 串起 §6 数据流:
  检索 → 组装 prompt(挂 skill)→ LLM 生成 → 校验 → 回写。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .llm import LLMClient, StubLLM
from .pipeline import (
    EvalResult,
    RetrievedContext,
    build_prompt,
    evaluate,
    retrieve,
    writeback,
)
from .skilladapter import SkillAdapter
from .structstore import StructStore
from .vectorstore import VectorStore


@dataclass
class ContinuationIntent:
    target_chapter: int
    preset: str
    goal: str
    focus_character_ids: list[str] = field(default_factory=list)
    resolve_foreshadow_ids: list[str] = field(default_factory=list)
    character_updates: dict[str, str] = field(default_factory=dict)


@dataclass
class ContinuationResult:
    text: str
    context: RetrievedContext
    evaluation: EvalResult
    writeback: dict
    prompt: str = ""


class ContinuationEngine:
    def __init__(
        self,
        store: StructStore,
        vs: VectorStore,
        skill: Optional[SkillAdapter] = None,
        llm: Optional[LLMClient] = None,
    ):
        self.store = store
        self.vs = vs
        self.skill = skill or SkillAdapter()
        self.llm = llm or StubLLM()

    def continue_chapter(
        self, intent: ContinuationIntent, known_sources: Optional[list[str]] = None
    ) -> ContinuationResult:
        ctx = retrieve(intent, self.store, self.vs)
        prompt = build_prompt(self.skill, ctx, intent)
        text = self.llm.generate(prompt)
        ev = evaluate(text, known_sources)
        wb = writeback(intent, text, self.store) if ev.passed else {}
        return ContinuationResult(
            text=text, context=ctx, evaluation=ev, writeback=wb, prompt=prompt
        )
