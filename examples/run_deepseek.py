"""Task 01 验收: 用 DeepSeekClient 跑一次完整续写主循环。

前置条件:
  1. 设置环境变量 DEEPSEEK_API_KEY
  2. 工程根已安装 requirements.txt 依赖

运行 (PowerShell):
  $env:PYTHONUTF8 = "1"
  $env:DEEPSEEK_API_KEY = "sk-..."
  python examples/run_deepseek.py

如果是 Bash:
  PYTHONUTF8=1 DEEPSEEK_API_KEY=sk-... python examples/run_deepseek.py

判通过标准: 能成功调到 DeepSeek 并打印出一段中文续写正文,
主循环不报错,回写正常。
"""
from __future__ import annotations

import os
import sys

# 工程根加入 path
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
    DeepSeekClient,
    ContinuationEngine,
    ContinuationIntent,
)


def check_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("❌ 未设置 DEEPSEEK_API_KEY,请先设置后重试:")
        print("   $env:DEEPSEEK_API_KEY = 'sk-...'  (PowerShell)")
        print("   export DEEPSEEK_API_KEY=sk-...   (Bash)")
        sys.exit(1)
    print(f"✅ 已读取 DEEPSEEK_API_KEY ({key[:6]}...)")
    return key


def seed(store: StructStore, vs: InMemoryVectorStore) -> None:
    """造少量占位卡,复刻 test_m2 的种子数据。"""
    cards = [
        CharacterCard(
            id="CH-0001",
            name="楚子航",
            gap="想被父亲看见,又用冷漠假装不在乎",
            disguise="纪律与剑",
            states=[
                CharacterState(chapter=1, status="独来独往的学长"),
                CharacterState(
                    chapter=50,
                    status="开始承认在意同伴",
                    reality_cost="靠近意味着可能再次失去",
                ),
            ],
        ),
        ForeshadowLedger(
            id="FS-0001",
            planted_at=12,
            description="一枚旧怀表,父亲留下,走时不准",
            status=ForeshadowStatus.OPEN,
            note="回收时让它在关键时刻停摆",
        ),
        ChapterSynopsis(
            id="SY-080",
            chapter=80,
            synopsis="主角在雨夜独自留在训练场,反复擦拭旧怀表,没有等到要等的人。",
            emotional_turn="从期待到默认对方不会来",
        ),
        FingerprintCard(
            id="FP-0001",
            mechanism="物/动作替代心理",
            stage_config="P4 少年被卷入",
            when_to_use="人物情绪强但不能直说时",
            how="让一件小物承担情绪,人物只做动作不解释",
        ),
    ]
    store.upsert_many(cards)
    for c in cards:
        vs.add(c.id, c.embed_text(), {"type": c.card_type.value})
    print(f"✅ 已入库 {len(cards)} 张占位卡")


def main() -> int:
    check_key()

    store = StructStore(":memory:")
    vs = InMemoryVectorStore()
    seed(store, vs)

    skill = SkillAdapter()
    assert skill.available(), f"❌ 未找到 江南.skill,路径:{skill.root}"
    print(f"✅ SkillAdapter 就绪,协议长度 {len(skill.protocol())} 字")

    llm = DeepSeekClient()
    print(f"✅ DeepSeekClient 就绪,model={llm.model}, temperature={llm.temperature}")

    engine = ContinuationEngine(store, vs, skill=skill, llm=llm)

    intent = ContinuationIntent(
        target_chapter=81,
        preset="P4 少年被卷入",
        goal="怀表停摆,他终于说出等待的人是谁",
        focus_character_ids=["CH-0001"],
        resolve_foreshadow_ids=["FS-0001"],
        character_updates={"CH-0001": "在第81章承认了等待"},
    )

    print("\n── 调用 DeepSeek 生成中… ──\n")
    result = engine.continue_chapter(intent)

    # ── 输出 ──
    print("=" * 60)
    print("  续写正文 (result.text)")
    print("=" * 60)
    print(result.text)
    print("=" * 60)

    print(f"\n📊 校验: {'✅ 通过' if result.evaluation.passed else '❌ 未通过'}")
    if result.evaluation.gate_note:
        print(f"   gate: {result.evaluation.gate_note}")

    print(f"\n📋 回写:")
    print(f"   新增梗概: {result.writeback.get('new_synopsis', 'N/A')}")
    print(f"   回收伏笔: {result.writeback.get('paid_foreshadows', [])}")
    print(f"   人物更新: {bool(result.writeback.get('character_updates'))}")

    print(f"\n📏 统计:")
    print(f"   prompt 长度: {len(result.prompt)} 字")
    print(f"   生成正文长度: {len(result.text)} 字")

    # 验证回写落盘
    assert result.writeback["new_synopsis"] == "SY-081"
    assert "FS-0001" in result.writeback["paid_foreshadows"]
    fs_now = store.get("FS-0001")
    assert fs_now.status == ForeshadowStatus.PAID, "伏笔应被标记 PAID"
    assert store.get("SY-081") is not None, "梗概应已落盘"
    chu = store.get("CH-0001")
    assert chu.state_at(81).chapter == 81, "人物状态应追加到第81章"
    print("✅ 回写落盘验证通过")

    store.close()
    print("\n🎉 验收完成: DeepSeekClient 在主循环中正常工作。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
