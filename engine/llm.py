"""江南续写引擎 · LLM 接口 (M2)

LLMClient 抽象 + StubLLM 占位。M2 用 StubLLM 跑通主循环,不调真模型、
不需 API key。后续接 DeepSeek / 本地模型时实现同一 generate 接口即可,
ContinuationEngine 无需改动。
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def generate(self, prompt: str, **kwargs) -> str: ...


class StubLLM:
    """占位实现:回显式产出可读的占位正文,便于验证 §6 数据流。"""

    def __init__(self, tag: str = "stub"):
        self.tag = tag
        self.last_prompt: Optional[str] = None

    def generate(self, prompt: str, **kwargs) -> str:
        self.last_prompt = prompt
        return (
            "【占位续写 · StubLLM】\n"
            "本段为主循环验证用占位文本,未调用真实模型。\n"
            "接入 DeepSeek / 本地模型后,此处将产出按江南协议生成的续写正文。"
        )
