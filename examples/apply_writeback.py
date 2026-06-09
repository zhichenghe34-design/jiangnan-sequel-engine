"""把续写回写卡(JSON)灌回知识库，形成滚动续写闭环 (M3)。

用法: python examples/apply_writeback.py <回写卡.json>
流程: 读回写卡 → 解析成标准卡片 → 追加到 knowledge/续写_<series>/ → 重建库

回写卡格式见 engine/writeback.py 顶部注释。
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import StructStore, cards_from_writeback, CardType  # noqa

_FILE = {
    CardType.SYNOPSIS: "synopses.jsonl",
    CardType.FORESHADOW: "foreshadows.jsonl",
    CardType.CHARACTER: "characters.jsonl",
    CardType.SETTING: "settings.jsonl",
}


def main():
    if len(sys.argv) < 2:
        print("用法: python examples/apply_writeback.py <回写卡.json>")
        return 1
    wb = json.load(open(sys.argv[1], encoding="utf-8"))
    series = wb["series"]

    # 用现有库查原卡(回收伏笔取 planted_at、人物更新取 name)
    db = os.path.join(ROOT, "data", f"{series}.sqlite")
    store = StructStore(db) if os.path.exists(db) else None
    cards = cards_from_writeback(wb, store)
    if store:
        store.close()

    # 追加到续写目录(源)，按卡类型分文件
    outdir = os.path.join(ROOT, "knowledge", f"续写_{series}")
    os.makedirs(outdir, exist_ok=True)
    counts = {}
    for c in cards:
        with open(os.path.join(outdir, _FILE[c.card_type]), "a", encoding="utf-8") as f:
            f.write(c.model_dump_json() + "\n")
        counts[c.card_type.value] = counts.get(c.card_type.value, 0) + 1

    print(f"回写第 {wb['chapter']} 章 → {outdir}")
    print("  " + "，".join(f"{k}:{v}" for k, v in counts.items()))

    # 重建库，让新记忆即时可被检索
    print("重建知识库……")
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "examples", "build_knowledge.py")],
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    print("回写完成。下一章续写时这些记忆已并入知识库。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
