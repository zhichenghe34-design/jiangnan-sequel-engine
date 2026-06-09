"""M1c 真语义向量库测试:EmbeddingVectorStore + 可插拔 embedding。

用 HashEmbedding(确定性占位)验证机制:嵌入缓存 / 余弦检索 / where 过滤 /
查自己 top1 / 共享词召回。真语义召回需接 APIEmbedding(见 engine/embedding.py)。

运行: python tests/test_m1c.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import EmbeddingVectorStore, HashEmbedding  # noqa: E402


def main() -> int:
    vs = EmbeddingVectorStore(HashEmbedding(dim=256))
    vs.add("CH", "路明非 缺口 伪装 废柴少年", {"type": "character"})
    vs.add("FS", "旧怀表 雨夜 停摆 父亲遗物", {"type": "foreshadow"})
    vs.add("SY", "训练场 独自等待 没有等到的人", {"type": "synopsis"})
    assert len(vs) == 3

    # 查自己 → top1 是自己,余弦≈1
    hits = vs.query("路明非 缺口 伪装 废柴少年", k=3)
    assert hits[0]["id"] == "CH", hits
    assert hits[0]["score"] > 0.99, hits[0]["score"]

    # 共享词的查询能召回(怀表/父亲 → FS)
    h2 = vs.query("怀表 父亲", k=3)
    assert h2[0]["id"] == "FS", h2

    # where 类型过滤
    typed = vs.query("等待", k=5, where={"type": "synopsis"})
    assert typed and all(t["metadata"]["type"] == "synopsis" for t in typed)

    # 接口与 InMemoryVectorStore 一致:返回 id/text/metadata/score
    assert set(hits[0]) == {"id", "text", "metadata", "score"}

    print("OK  M1c 真语义向量库:嵌入缓存 / 余弦检索 / where 过滤 / 查自己 top1 全部通过")
    print(f"    - 查自己 top1: {hits[0]['id']} score={hits[0]['score']:.3f}")
    print(f"    - 共享词召回: '怀表 父亲' → {h2[0]['id']} score={h2[0]['score']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
