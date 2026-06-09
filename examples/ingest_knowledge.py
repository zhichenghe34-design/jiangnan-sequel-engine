"""把 DS 蒸馏产出的卡片(knowledge/<作品>/*.jsonl)导入知识库并打印报告。

用法:
    $env:PYTHONUTF8 = "1"
    python examples/ingest_knowledge.py            # 默认导入 knowledge/龙族
    python examples/ingest_knowledge.py knowledge/龙族I

结构库落盘到 data/knowledge.sqlite(已被 .gitignore 忽略);
向量库 M1 阶段用内存实现(同进程内可检索),持久化向量库待 M1c 接 Chroma。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import StructStore, InMemoryVectorStore, ingest_path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    rel = sys.argv[1] if len(sys.argv) > 1 else "knowledge/龙族"
    src = (ROOT / rel).resolve()
    if not src.exists():
        print(f"找不到卡片目录:{src}")
        print("请先让 DS 按 tasks/02_蒸馏龙族正传.md 产出卡片到该目录。")
        return 1

    (ROOT / "data").mkdir(exist_ok=True)
    store = StructStore(str(ROOT / "data" / "knowledge.sqlite"))
    vs = InMemoryVectorStore()

    rep = ingest_path(src, store, vs)

    print(f"源目录:{src}")
    print(f"结果:{rep.summary()}")
    if rep.errors:
        print(f"\n问题卡({len(rep.errors)}):")
        for src_name, msg in rep.errors:
            print(f"  - {src_name}: {msg.splitlines()[0]}")

    # 抽样自检:随便查一下,确认能召回
    if rep.ingested:
        hits = vs.query("缺口 伤口 等待", k=3)
        print("\n抽样向量召回 top3:")
        for h in hits:
            print(f"  - [{h['metadata'].get('type')}] {h['id']}  score={h['score']:.3f}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
