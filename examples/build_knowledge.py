"""把 knowledge/ 下各卷卡片按系列导入**独立的库**(物理隔离两个世界)。

  龙族系列   -> data/longzu.sqlite
  天之炽系列 -> data/tianzhichi.sqlite

导入顺序按首次出场卷在前，确保跨卷人物 states 正确合并(见 engine/ingest.py)。
向量库 M1 阶段用内存实现(本进程内检索);持久化向量库待 M1c 接 Chroma。

用法:  $env:PYTHONUTF8 = "1"; python examples/build_knowledge.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import StructStore, InMemoryVectorStore, ingest_path  # noqa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KN = os.path.join(ROOT, "knowledge")

# 顺序很重要:首次出场卷在前，后续卷只追加状态
SERIES = {
    "longzu": ["龙族I", "龙族II", "龙族III", "龙族IV", "龙族前传"],
    "tianzhichi": ["天之炽I", "天之炽II"],
}


def build():
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    for series, vols in SERIES.items():
        dbp = os.path.join(ROOT, "data", f"{series}.sqlite")
        if os.path.exists(dbp):
            os.remove(dbp)  # 重建，避免叠加
        store = StructStore(dbp)
        vs = InMemoryVectorStore()
        print(f"== {series} -> data/{series}.sqlite ==")
        errs = []
        for v in vols:
            d = os.path.join(KN, v)
            if not os.path.isdir(d):
                print(f"  {v}: 目录缺失，跳过")
                continue
            rep = ingest_path(d, store, vs)
            errs += rep.errors
            print(f"  {v}: {rep.summary()}")
        n = store.conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        print(f"  -> 唯一卡 {n} 张，错误 {len(errs)} 条")
        if errs:
            for src, msg in errs[:5]:
                print(f"     ! {src}: {msg.splitlines()[0]}")
        store.close()


if __name__ == "__main__":
    build()
