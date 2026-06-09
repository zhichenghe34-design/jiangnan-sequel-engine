"""M0 冒烟测试:建卡 → 存(结构库+向量库)→ 检索 → quote-free 扫描。

直接运行:  python tests/test_smoke.py
(建议设 PYTHONUTF8=1 以免 Windows 控制台 GBK 编码报错)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import (  # noqa: E402
    CharacterCard,
    CharacterState,
    ForeshadowLedger,
    ForeshadowStatus,
    ChapterSynopsis,
    FingerprintCard,
    CardType,
    StructStore,
    InMemoryVectorStore,
    quotefree,
)


def build_cards():
    chu = CharacterCard(
        id="CH-0001",
        name="楚子航",
        gap="想被父亲看见,又用冷漠假装不在乎",
        disguise="纪律与剑",
        states=[
            CharacterState(chapter=1, status="独来独往的学长", reality_cost="维持距离要付出孤立的代价"),
            CharacterState(chapter=50, status="开始承认在意同伴", reality_cost="靠近意味着可能再次失去"),
        ],
    )
    fs = ForeshadowLedger(
        id="FS-0001",
        planted_at=12,
        description="一枚旧怀表,父亲留下,走时不准",
        status=ForeshadowStatus.OPEN,
        note="回收时让它在关键时刻停摆,承担'迟到的疼'",
    )
    syn = ChapterSynopsis(
        id="SY-080",
        chapter=80,
        synopsis="主角在雨夜独自留在训练场,反复擦拭旧怀表,没有等到要等的人。",
        key_objects=["旧怀表", "训练场的灯"],
        emotional_turn="从期待到默认对方不会来",
    )
    fp = FingerprintCard(
        id="FP-0001",
        mechanism="物/动作替代心理",
        stage_config="P4 少年被卷入",
        when_to_use="人物情绪强但不能直说时",
        how="让一件小物承担情绪,人物只做动作不解释",
    )
    return chu, fs, syn, fp


def main() -> int:
    chu, fs, syn, fp = build_cards()

    # 1) 人物状态版本化
    assert chu.state_at(80).chapter == 50, "state_at 应返回 <=80 的最新快照(第50章)"
    assert chu.state_at(10).chapter == 1
    assert chu.state_at(0) is None

    # 2) 结构库:存 + 精确查询
    store = StructStore(":memory:")
    store.upsert_many([chu, fs, syn, fp])

    got = store.get("CH-0001")
    assert isinstance(got, CharacterCard) and got.name == "楚子航"

    open_fs = store.open_foreshadows_before(80)
    assert len(open_fs) == 1 and open_fs[0].id == "FS-0001", "应召回第80章前的 open 伏笔"
    assert store.open_foreshadows_before(10) == [], "第10章前不该有伏笔(埋于12章)"

    window = store.synopses_window(80, span=3)
    assert len(window) == 1 and window[0].chapter == 80

    # 3) 向量库:语义召回
    vs = InMemoryVectorStore()
    for card in (chu, fs, syn, fp):
        vs.add(card.id, card.embed_text(), {"type": card.card_type.value})
    hits = vs.query("怀表 迟到 没有等到", k=3)
    assert hits and hits[0]["score"] > 0, "应召回与'怀表/等待'相关的卡片"
    typed = vs.query("缺口 伪装", k=5, where={"type": CardType.CHARACTER.value})
    assert all(h["metadata"]["type"] == "character" for h in typed), "where 过滤应只返回人物卡"

    # 4) quote-free:转述通过,逐字抄录拦截
    source = "他站在雨里，把那块旧怀表擦了又擦，最终也没有等到那个人。"
    paraphrase = "主角在雨夜独自留在训练场，反复擦拭旧怀表，没有等到要等的人。"
    verbatim = "他站在雨里，把那块旧怀表擦了又擦，最终也没有等到那个人。已经很久。"

    r_ok = quotefree.scan(paraphrase, source)
    r_bad = quotefree.scan(verbatim, source)
    assert r_ok.passed, f"转述应通过,却被拦:{r_ok.reason}"
    assert not r_bad.passed, "逐字抄录应被拦截"

    print("OK  人物状态版本化、结构库精确查询、向量召回、quote-free 扫描全部通过")
    print(f"    - open 伏笔召回: {open_fs[0].description}")
    print(f"    - 向量 top1: {hits[0]['id']} score={hits[0]['score']:.3f}")
    print(f"    - quote-free 拦截原因: {r_bad.reason}")
    print(f"    - 命中片段示例: 「{r_bad.lcs_sample}」")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
