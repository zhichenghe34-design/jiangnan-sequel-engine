"""M1 冒烟测试:卡片 JSON 导入闭环。

写临时 jsonl/json(模拟 DS 蒸馏产出)→ ingest_path 灌入结构库+向量库 →
验证计数、精确查询、向量召回、坏数据被记录而不中断。

运行:  python tests/test_m1.py   (建议 PYTHONUTF8=1)
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import (  # noqa: E402
    StructStore,
    InMemoryVectorStore,
    CardType,
    ForeshadowStatus,
    ChapterSynopsis,
    ingest_path,
)


CHARACTERS = [
    {
        "card_type": "character", "id": "CH-0001", "name": "楚子航",
        "gap": "想被父亲看见,又用冷漠假装不在乎", "disguise": "纪律与剑",
        "states": [
            {"chapter": 1, "status": "独来独往的学长"},
            {"chapter": 50, "status": "开始承认在意同伴", "reality_cost": "靠近意味着可能再次失去"},
        ],
    },
    {
        "card_type": "character", "id": "CH-0002", "name": "路明非",
        "gap": "渴望被需要,又自认平庸", "disguise": "自嘲与拖延",
        "states": [{"chapter": 1, "status": "普通到不能再普通的少年"}],
    },
]

FORESHADOWS = [
    {
        "card_type": "foreshadow", "id": "FS-0001", "planted_at": 12,
        "description": "一枚旧怀表,父亲留下,走时不准", "status": "open",
        "note": "回收时让它在关键时刻停摆",
    },
    {  # 故意缺 planted_at(必填)→ 应被记为错误而不中断
        "card_type": "foreshadow", "id": "FS-BAD",
        "description": "字段不全的坏卡",
    },
]

SYNOPSES = [
    {
        "card_type": "synopsis", "id": "SY-080", "chapter": 80,
        "synopsis": "主角在雨夜独自留在训练场,反复擦拭旧怀表,没有等到要等的人。",
        "emotional_turn": "从期待到默认对方不会来",
    }
]


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        # 模拟 DS 产出:每类一个 jsonl + 一个 json 数组
        with open(os.path.join(d, "characters.jsonl"), "w", encoding="utf-8") as f:
            for c in CHARACTERS:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        with open(os.path.join(d, "foreshadows.jsonl"), "w", encoding="utf-8") as f:
            for c in FORESHADOWS:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        with open(os.path.join(d, "synopses.json"), "w", encoding="utf-8") as f:
            json.dump(SYNOPSES, f, ensure_ascii=False)

        store = StructStore(":memory:")
        vs = InMemoryVectorStore()
        rep = ingest_path(d, store, vs)

    # 1) 计数:4 张合法(2人物+1伏笔+1梗概),1 张坏卡进 errors
    assert rep.ingested == 4, f"应导入 4 张,实际 {rep.ingested}"
    assert rep.by_type["character"] == 2
    assert rep.by_type["foreshadow"] == 1
    assert rep.by_type["synopsis"] == 1
    assert any("FS-BAD" in src or "FS-BAD" in msg for src, msg in rep.errors), \
        "缺字段的坏卡应被记录到 errors"

    # 2) 结构库精确查询正常工作
    open_fs = store.open_foreshadows_before(81)
    assert len(open_fs) == 1 and open_fs[0].id == "FS-0001"
    syn = store.get("SY-080")
    assert isinstance(syn, ChapterSynopsis) and syn.chapter == 80
    chu = store.get("CH-0001")
    assert chu.state_at(80).chapter == 50

    # 3) 向量库召回 + 类型过滤
    hits = vs.query("怀表 没有等到", k=3)
    assert hits and hits[0]["score"] > 0
    chars = vs.query("缺口", k=5, where={"type": CardType.CHARACTER.value})
    assert len(chars) == 2 and all(h["metadata"]["type"] == "character" for h in chars)

    print("OK  M1 导入闭环:JSON → 结构库 + 向量库,精确查询/向量召回/坏卡隔离全部通过")
    print(f"    - {rep.summary()}")
    print(f"    - 坏卡: {rep.errors}")
    print(f"    - 向量 top1: {hits[0]['id']} score={hits[0]['score']:.3f}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
