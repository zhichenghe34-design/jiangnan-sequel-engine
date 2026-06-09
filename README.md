# 江南工程 · 续写引擎

一个**长篇续写引擎**:用结构化的"故事记忆"保证长篇不丢设定、不忘伏笔、人物不崩,用 `江南.skill` 保证笔法像江南,大模型负责落笔。

状态:**M0–M2 已实现,端到端续写验证通过**(详见下方进度)。

## 进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | 知识层骨架:卡片 schema + SQLite 结构库 + 向量库接口 + quote-free 扫描器 | ✅ |
| M1 | 知识灌注:DS 蒸馏 → 卡片 JSON → 分系列入库(导入器含跨卷人物 states 合并) | ✅ |
| M2 | 续写主循环:检索前情 → 挂 `江南.skill` → 组装 prompt →(生成)→ 校验 → 回写 | ✅ |
| 续写测试 | 用真知识库 + 江南.skill 生成 prompt,DS 产出第317章,江南味+记忆一致均通过 | ✅ |
| M1c | 接真 embedding(Chroma + bge/Qwen),替换内存占位向量库 | ⬜ 待做 |
| M3 | 回写闭环脚本:把续写新章自动并回知识库(新梗概/伏笔回收/人物状态) | ⬜ 待做 |

当前知识库:longzu 203 张 / tianzhichi 57 张,七卷逐章,跨卷人物状态线与伏笔埋收时间线完整。

## 和 江南.skill 的关系

| | 管什么 | 形态 |
|---|---|---|
| **江南.skill** | 怎么写得像江南(笔法、preset、评分门) | 独立仓库的写作协议 skill |
| **江南工程**(本仓) | 写长了不忘事、不崩设定(剧情记忆 + 续写) | RAG 续写引擎 |

引擎在组装 prompt 时**引用** `江南.skill`(默认路径 `../江南.skill`,见 `engine/skilladapter.py`),不复制、不修改它。skill 升版本,只要文件结构不变,引擎不用动。
> 使用本仓需把 `江南.skill` 放在同级目录(它是独立项目:https://github.com/zhichenghe34-design/JiangNan-feeling-writing )。

## 它不是什么 / 核心红线

- **不是**把原著切片存进向量库检索仿写。向量库存的是**二次创作的记忆与转述**(设定/人物/伏笔/章节梗概卡),**不是原文**。
- **不是** fine-tune——不把原文吸进模型权重。
- **quote-free,但保留专名**:保留人物/地点专名(优先续写代入感),但**绝不复制**原文句子/段落/描写。

详见 [`续写引擎架构设计_v0.1.md`](续写引擎架构设计_v0.1.md) §9。

## 目录结构

```
── 引擎框架(通用,换任何作品都能用)──────────────
  engine/         引擎本体(11 个模块):
                  schema / structstore / vectorstore / quotefree / ingest /
                  skilladapter / llm / deepseek_client / pipeline / engine
  examples/       build_knowledge / continue_demo / ingest_knowledge / run_deepseek
  tests/          test_smoke / test_m1 / test_m2
  README / requirements / 续写引擎架构设计_v0.1.md
── 项目数据(随仓库发布,续写所必需)──────────────
  knowledge/      龙族/天之炽卡片 —— 二创转述 + 保留专名，**非原文**
  tasks/          蒸馏 / 续写的派发文档
── 生成产物(.gitignore，可由上面重建)──────────────
  data/           build_knowledge 生成的 sqlite 库
  output/         continue_demo 生成的 prompt / 续写
```

**发布包含 `knowledge/`**(续写离不开它),它是**二创转述卡,不含任何原文句子**(quote-free)。**从不包含**:原著原文/语料(本就不在本仓)、生成产物(可重建)。

## 快速开始

```powershell
$env:PYTHONUTF8 = "1"
pip install -r requirements.txt          # pydantic + requests

python examples\build_knowledge.py       # 卡片 → data/longzu.sqlite、data/tianzhichi.sqlite
python examples\continue_demo.py         # 组装续写 prompt → output\续写prompt_*.md
# 把 output 里的 prompt 交给 DS / 大模型续写;它会带着江南协议 + 全系列记忆写
```

跑测试:`python tests\test_smoke.py`(M0)/ `test_m1.py` / `test_m2.py`。

## 生成层两种接法

- **DS / 大模型直接续写(当前用法)**:`continue_demo.py` 只组装 prompt,交给对话续写,不需 API key。
- **DeepSeekClient(可选)**:`engine/deepseek_client.py` 走 API 直调,设 `DEEPSEEK_API_KEY` 即可让引擎自动生成。

## 许可与免责

- **代码**(`engine/`、`examples/`、`tests/`)以 MIT 许可发布(见 `LICENSE`)。
- **`knowledge/`** 是《龙族》《天之炽》的**非商业同人衍生数据**——剧情/人物/伏笔的转述与分析,保留专名,**不含原文**。仅供研究与个人续写实验,**非商业用途**。相关作品版权归原作者江南所有;如权利人认为不妥,请提 issue,将立即删除。
