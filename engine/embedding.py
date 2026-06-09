"""真语义向量检索 (M1c)：可插拔 embedding + 纯 Python 余弦检索。

为什么不强用 chromadb/torch：它们对 Python 3.14 的 wheel 尚不稳定。本模块零新依赖
(API 走已有的 requests),260 量级卡片暴力余弦足够,无需 ANN 索引。
`EmbeddingVectorStore` 与 `InMemoryVectorStore` 接口一致,可直接替换。

embedding 来源三选一:
  - HashEmbedding   : 确定性占位,无语义,供测试/完全离线时打通流程。
  - APIEmbedding    : 调 OpenAI 兼容 /embeddings(如 SiliconFlow 的 bge-large-zh、
                      OpenAI text-embedding-3),读环境变量 key,不写死。
  - 本地模型(可选) : sentence-transformers + bge——若你的环境装得上,自己包一个
                      满足 EmbeddingFunction 的可调用对象传进来即可(见文末示例)。
"""
from __future__ import annotations

import hashlib
import math
import os
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class EmbeddingFunction(Protocol):
    def __call__(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedding:
    """确定性占位:把文本的字符 2-gram 散列进固定维向量。无真语义,
    但相同文本得相同向量、共享词的文本向量略近——足以打通与测试检索流程。"""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def __call__(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            s = "".join(t.split())
            toks = [s[i:i + 2] for i in range(len(s) - 1)] or ([s] if s else [])
            v = [0.0] * self.dim
            for tok in toks:
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                v[h % self.dim] += 1.0
            out.append(v)
        return out


class APIEmbedding:
    """OpenAI 兼容 /embeddings 客户端。

    例(SiliconFlow bge-large-zh):
        APIEmbedding(model="BAAI/bge-large-zh-v1.5",
                     base_url="https://api.siliconflow.cn/v1",
                     api_key_env="SILICONFLOW_API_KEY")
    """

    def __init__(self, model: str, base_url: str, api_key_env: str, timeout: int = 30):
        import requests  # 延迟导入
        self._requests = requests
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout

    def __call__(self, texts: list[str]) -> list[list[float]]:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(f"未设置环境变量 {self.api_key_env}")
        resp = self._requests.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"embedding API {resp.status_code}: {resp.text[:200]}")
        return [d["embedding"] for d in resp.json()["data"]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class EmbeddingVectorStore:
    """真语义向量库,接口同 InMemoryVectorStore(add / query),可直接替换。

    向量惰性计算并缓存:add 只登记文本,首次 query 时批量嵌入未处理项。
    """

    def __init__(self, embed_fn: EmbeddingFunction, batch: int = 64):
        self._embed = embed_fn
        self._batch = batch
        self._items: list[dict] = []

    def add(self, id: str, text: str, metadata: Optional[dict] = None) -> None:
        self._items = [it for it in self._items if it["id"] != id]
        self._items.append({"id": id, "text": text, "metadata": metadata or {}, "vec": None})

    def _ensure_embedded(self) -> None:
        todo = [it for it in self._items if it["vec"] is None]
        for i in range(0, len(todo), self._batch):
            chunk = todo[i:i + self._batch]
            for it, v in zip(chunk, self._embed([it["text"] for it in chunk])):
                it["vec"] = v

    def query(self, text: str, k: int = 5, where: Optional[dict] = None) -> list[dict]:
        self._ensure_embedded()
        qv = self._embed([text])[0]
        scored = []
        for it in self._items:
            if where and not all(it["metadata"].get(kk) == vv for kk, vv in where.items()):
                continue
            scored.append({
                "id": it["id"], "text": it["text"],
                "metadata": it["metadata"], "score": _cosine(qv, it["vec"]),
            })
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._items)


# 本地模型接法示例(需自行 pip install sentence-transformers，3.14 兼容性请先验证):
#   from sentence_transformers import SentenceTransformer
#   _m = SentenceTransformer("BAAI/bge-large-zh-v1.5")
#   local_embed = lambda texts: _m.encode(texts, normalize_embeddings=True).tolist()
#   vs = EmbeddingVectorStore(local_embed)
