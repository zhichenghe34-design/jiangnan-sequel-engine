"""江南续写引擎 · 风格层适配 (M2)

读取同目录下 `江南.skill` 的协议/preset/评分门文本,作为生成层的"风格层"。
skill 不复制、不修改,只被引用;升版本只要文件结构不变,引擎无需改动。
对应架构文档 §7。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


class SkillAdapter:
    def __init__(self, skill_root: Optional[str] = None):
        if skill_root:
            self.root = Path(skill_root)
        else:
            # engine/ -> 江南工程/ -> 江南/  ; 同级的 江南.skill
            self.root = Path(__file__).resolve().parents[2] / "江南.skill"

    def available(self) -> bool:
        return (self.root / "core" / "protocol.md").exists()

    def _read(self, rel: str) -> str:
        p = self.root / rel
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def protocol(self) -> str:
        return self._read("core/protocol.md")

    def presets(self) -> str:
        return self._read("core/presets.md")

    def evaluation(self) -> str:
        return self._read("core/evaluation.md")
