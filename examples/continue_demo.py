"""续写 demo：加载真知识库 + 检索前情 + 挂江南.skill，组装出完整续写 prompt。

本脚本**不调用模型**，只产出 prompt（交给 DS agent 去续写）。
产出文件： output/续写prompt_<series>_ch<N>.md

用法： $env:PYTHONUTF8 = "1"; python examples/continue_demo.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import (  # noqa: E402
    StructStore, InMemoryVectorStore, SkillAdapter,
    ContinuationIntent, CardType,
)
from engine.pipeline import retrieve, build_prompt  # noqa: E402

# ============ 续写意图（改这里即可换章/换走向/换系列）============
SERIES = "longzu"                       # longzu 或 tianzhichi
TARGET_CHAPTER = 317                     # 续写第几章（龙族IV止于316，317=续命新章）
PRESET = "P4 少年被卷入"                  # 江南 preset（DS 可按 skill 表微调）
GOAL = ("龙族IV之后：路明非交出全部灵魂却依然活着，这本身成谜；楚子航下落不明。"
        "新的危机降临，过去埋下的伏笔（父母下落、路鸣泽的真正目的）开始浮现。")
FOCUS_NAMES = ["路明非", "楚子航"]
# ===============================================================


def _make_vectorstore():
    """默认字符 n-gram 占位;设了 EMBED_MODEL/EMBED_BASE_URL/EMBED_API_KEY_ENV
    三个环境变量则启用真语义 embedding(M1c)。"""
    model = os.environ.get("EMBED_MODEL")
    base = os.environ.get("EMBED_BASE_URL")
    keyenv = os.environ.get("EMBED_API_KEY_ENV")
    if model and base and keyenv:
        from engine import APIEmbedding, EmbeddingVectorStore
        print(f"[向量库] 真语义 embedding: {model}")
        return EmbeddingVectorStore(APIEmbedding(model, base, keyenv))
    print("[向量库] 字符 n-gram 占位(设 EMBED_MODEL/EMBED_BASE_URL/EMBED_API_KEY_ENV 启用真语义)")
    return InMemoryVectorStore()


def rebuild_vectorstore(store):
    vs = _make_vectorstore()
    for ct in CardType:
        for c in store.by_type(ct):
            vs.add(c.id, c.embed_text(), {"type": c.card_type.value})
    return vs


def resolve_ids(store, names):
    chars = store.by_type(CardType.CHARACTER)
    ids = []
    for nm in names:
        for c in chars:
            if nm in c.name:
                ids.append(c.id)
                break
    return ids


def main():
    db = os.path.join(ROOT, "data", f"{SERIES}.sqlite")
    if not os.path.exists(db):
        print(f"找不到知识库 {db}，请先跑 examples/build_knowledge.py")
        return 1

    store = StructStore(db)
    vs = rebuild_vectorstore(store)
    skill = SkillAdapter()

    intent = ContinuationIntent(
        target_chapter=TARGET_CHAPTER, preset=PRESET, goal=GOAL,
        focus_character_ids=resolve_ids(store, FOCUS_NAMES),
    )
    ctx = retrieve(intent, store, vs)
    prompt = build_prompt(skill, ctx, intent)

    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"续写prompt_{SERIES}_ch{TARGET_CHAPTER}.md")
    header = (
        f"<!-- 续写引擎自动组装。DS：请严格遵循下方『系统·风格层(江南.skill)』的写作协议，"
        f"利用『记忆·前情』保持设定/人物/伏笔一致，续写第 {TARGET_CHAPTER} 章正文。"
        f"不复制原文句子，可保留专名。 -->\n\n"
    )
    with open(out, "w", encoding="utf-8") as f:
        f.write(header + prompt)

    # 控制台摘要：让人看到引擎到底调了哪些记忆
    print(f"系列: {SERIES}  续写章: {TARGET_CHAPTER}  preset: {PRESET}")
    print(f"江南.skill 已挂载: {skill.available()}  (协议+preset 已注入 prompt 开头)")
    print(f"聚焦人物: {intent.focus_character_ids}")
    for name, st in ctx.character_states:
        print(f"  - {name} @第{st.chapter}章: {st.status[:30] if st else '无'}" if st
              else f"  - {name}: 无状态记录")
    print(f"召回未回收伏笔: {len(ctx.open_foreshadows)} 条")
    for fzz in ctx.open_foreshadows[:5]:
        print(f"  · [{fzz.id}] {fzz.description[:28]}")
    print(f"邻近章节梗概: {len(ctx.recent_synopses)} 条")
    print(f"\nprompt 已保存: {out}")
    print(f"prompt 长度: {len(prompt)} 字")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
