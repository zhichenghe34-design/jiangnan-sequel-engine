"""M2 冒烟测试:续写主循环。

建少量占位卡 → 入库 → 跑 ContinuationEngine.continue_chapter →
验证 检索召回 / 挂上 skill / 生成 / 校验 / 回写 全链路。

运行:  python tests/test_m2.py   (建议 PYTHONUTF8=1)
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
    StructStore,
    InMemoryVectorStore,
    SkillAdapter,
    StubLLM,
    ContinuationEngine,
    ContinuationIntent,
    evaluate,
)


def seed(store, vs):
    cards = [
        CharacterCard(
            id="CH-0001", name="楚子航",
            gap="想被父亲看见,又用冷漠假装不在乎", disguise="纪律与剑",
            states=[
                CharacterState(chapter=1, status="独来独往的学长"),
                CharacterState(chapter=50, status="开始承认在意同伴", reality_cost="靠近意味着可能再次失去"),
            ],
        ),
        ForeshadowLedger(
            id="FS-0001", planted_at=12,
            description="一枚旧怀表,父亲留下,走时不准",
            status=ForeshadowStatus.OPEN, note="回收时让它在关键时刻停摆",
        ),
        ChapterSynopsis(
            id="SY-080", chapter=80,
            synopsis="主角在雨夜独自留在训练场,反复擦拭旧怀表,没有等到要等的人。",
            emotional_turn="从期待到默认对方不会来",
        ),
        FingerprintCard(
            id="FP-0001", mechanism="物/动作替代心理", stage_config="P4 少年被卷入",
            when_to_use="人物情绪强但不能直说时", how="让一件小物承担情绪,人物只做动作不解释",
        ),
    ]
    store.upsert_many(cards)
    for c in cards:
        vs.add(c.id, c.embed_text(), {"type": c.card_type.value})


def main() -> int:
    store = StructStore(":memory:")
    vs = InMemoryVectorStore()
    seed(store, vs)

    skill = SkillAdapter()
    assert skill.available(), f"未找到 江南.skill,路径:{skill.root}"
    assert "选择成本" in skill.protocol(), "应读到 protocol.md 的选择成本规则(v1.1.1)"

    engine = ContinuationEngine(store, vs, skill=skill, llm=StubLLM())

    intent = ContinuationIntent(
        target_chapter=81,
        preset="P4 少年被卷入",
        goal="怀表停摆,他终于说出等待的人是谁",
        focus_character_ids=["CH-0001"],
        resolve_foreshadow_ids=["FS-0001"],
        character_updates={"CH-0001": "在第81章承认了等待"},
    )
    result = engine.continue_chapter(intent)

    # 1) 检索召回
    assert any(f.id == "FS-0001" for f in result.context.open_foreshadows), "应召回未回收伏笔"
    assert result.context.character_states and result.context.character_states[0][0] == "楚子航"
    assert result.context.character_states[0][1].chapter == 50, "人物状态应取第80章前最新(第50章)"

    # 2) 挂上了 skill 风格层
    assert "风格层" in result.prompt and "选择成本" in result.prompt, "prompt 应注入 skill 协议"
    assert "未回收伏笔" in result.prompt, "prompt 应注入伏笔记忆"

    # 3) 生成 + 校验通过
    assert result.text.strip(), "应有生成正文"
    assert result.evaluation.passed, f"校验应通过:{result.evaluation.gate_note}"

    # 4) 回写闭环
    assert result.writeback["new_synopsis"] == "SY-081"
    assert "FS-0001" in result.writeback["paid_foreshadows"]
    fs_now = store.get("FS-0001")
    assert fs_now.status == ForeshadowStatus.PAID and fs_now.paid_at == 81, "伏笔应被标记回收"
    assert store.get("SY-081") is not None, "应新增第81章梗概"
    chu = store.get("CH-0001")
    assert chu.state_at(81).chapter == 81, "人物应追加第81章状态"
    # 回收后再续写第82章,该伏笔不应再出现
    assert all(f.id != "FS-0001" for f in store.open_foreshadows_before(82))

    # 5) quote-free 拦截路径(给定本地原文片段时生效)
    src = "他站在雨里，把那块旧怀表擦了又擦，最终也没有等到那个人。"
    bad = evaluate(src + "后来天亮了。", known_sources=[src])
    assert not bad.passed and not bad.quotefree_passed, "生成文本逐字命中原文应被拦"

    print("OK  M2 主循环:检索 → 挂skill → 生成 → 校验 → 回写,全链路通过")
    print(f"    - 召回 open 伏笔: FS-0001（第81章后状态:{fs_now.status.value}）")
    print(f"    - 人物状态注入: 楚子航@第50章 -> 追加@第81章")
    print(f"    - 回写: 新增 {result.writeback['new_synopsis']}, 回收 {result.writeback['paid_foreshadows']}")
    print(f"    - prompt 长度: {len(result.prompt)} 字(已含 skill 协议+preset+记忆)")
    print(f"    - quote-free 拦截: {bad.quotefree_detail}")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
