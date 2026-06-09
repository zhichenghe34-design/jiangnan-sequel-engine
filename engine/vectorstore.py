"""江南续写引擎 · 向量库 (M0)

负责"语义召回"。M0 提供:
  - VectorStore 抽象接口(Protocol)
  - InMemoryVectorStore 占位实现:字符 n-gram Jaccard 相似度,
    零依赖、立即可跑,用于打通 §6 检索流程。

M1 再接 ChromaVectorStore + 真 embedding(bge-large-zh / Qwen-embedding),
只要实现同一接口,生成层无需改动。对应架构文档 §4–§5。
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    s = "".join(text.split())
    if len(s) < n:
        return {s} if s else set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@runtime_checkable
class VectorStore(Protocol):
    def add(self, id: str, text: str, metadata: Optional[dict] = None) -> None: ...
    def query(
        self, text: str, k: int = 5, where: Optional[dict] = None
    ) -> list[dict]: ...


class InMemoryVectorStore:
    """M0 占位实现。返回结果格式与未来 Chroma 实现一致:
    [{"id", "text", "metadata", "score"}], score 越大越相关。
    """

    def __init__(self, ngram: int = 3):
        self._ngram = ngram
        self._items: list[dict] = []

    def add(self, id: str, text: str, metadata: Optional[dict] = None) -> None:
        # 同 id 覆盖
        self._items = [it for it in self._items if it["id"] != id]
        self._items.append(
            {
                "id": id,
                "text": text,
                "metadata": metadata or {},
                "_grams": _char_ngrams(text, self._ngram),
            }
        )

    def query(
        self, text: str, k: int = 5, where: Optional[dict] = None
    ) -> list[dict]:
        q = _char_ngrams(text, self._ngram)
        scored = []
        for it in self._items:
            if where and not all(it["metadata"].get(kk) == vv for kk, vv in where.items()):
                continue
            scored.append(
                {
                    "id": it["id"],
                    "text": it["text"],
                    "metadata": it["metadata"],
                    "score": _jaccard(q, it["_grams"]),
                }
            )
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._items)
