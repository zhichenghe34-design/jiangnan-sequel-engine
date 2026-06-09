"""M3 回写闭环测试:回写卡 → 卡片解析 → 灌库,验证伏笔回收 + 人物状态合并。
隔离运行(内存库),不碰真实 knowledge/data。

运行: python tests/test_m3.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import (  # noqa: E402
    StructStore, InMemoryVectorStore,
    ForeshadowLedger, ForeshadowStatus, CharacterCard, CharacterState,
    cards_from_writeback, ingest,
)


def main() -> int:
    store = StructStore(":memory:")
    vs = InMemoryVectorStore()
    # 预置:一个 open 伏笔 + 一个有历史状态的人物
    store.upsert(ForeshadowLedger(id="FS-T", planted_at=5, description="原伏笔", note="待回收"))
    store.upsert(CharacterCard(id="CH-T", name="测试人物",
                               states=[CharacterState(chapter=1, status="初始状态")]))

    wb = {
        "series": "longzu", "chapter": 100,
        "synopsis": {"id": "SY-T-100", "synopsis": "本章梗概转述", "emotional_turn": "转折"},
        "foreshadows_resolved": [{"id": "FS-T", "paid_at": 100}],
        "new_foreshadows": [{"id": "FS-N", "planted_at": 100, "description": "本章新埋伏笔"}],
        "character_updates": [{"id": "CH-T", "status": "第100章新状态", "reality_cost": "代价"}],
    }

    cards = cards_from_writeback(wb, store)

    # 1) 解析正确
    kinds = [c.card_type.value for c in cards]
    assert kinds.count("synopsis") == 1, kinds
    assert kinds.count("foreshadow") == 2, kinds
    assert kinds.count("character") == 1, kinds
    paid = next(c for c in cards if c.id == "FS-T")
    assert paid.status == ForeshadowStatus.PAID and paid.paid_at == 100
    assert paid.planted_at == 5, "回收应保留原 planted_at(从库复制)"
    assert paid.description == "原伏笔", "回收应保留原描述"

    # 2) 灌库后闭环:伏笔变 paid、人物 states 合并、新卡入库
    ingest(cards, store, vs)
    assert store.get("FS-T").status == ForeshadowStatus.PAID
    assert all(f.id != "FS-T" for f in store.open_foreshadows_before(200)), \
        "回收后不应再出现在 open 列表"
    chu = store.get("CH-T")
    assert [s.chapter for s in chu.states] == [1, 100], "人物新状态应合并进历史"
    assert store.get("SY-T-100") is not None and store.get("FS-N") is not None

    print("OK  M3 回写闭环:回写卡 → 解析 → 灌库,伏笔回收 + 人物状态合并 + 新卡入库全部通过")
    print("    - 伏笔 FS-T: open→paid@100 (planted_at 保留=5)")
    print(f"    - 人物 CH-T states: {[s.chapter for s in chu.states]}")
    print("    - 新增: SY-T-100, FS-N")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
