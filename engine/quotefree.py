"""江南续写引擎 · quote-free 扫描器 (M0)

用途:DS 蒸馏出的卡片入库前、或生成正文产出后,比对它与**本地原文**的
字符级重叠,拦截疑似逐字抄录。对应架构文档 §9。

关键:原文 `source` 只作为函数入参临时传入做参照,**绝不被本扫描器存储**。
保留专名是允许的(项目决定);本扫描器拦的是"复制原文句子/段落"。
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _char_ngrams(text: str, n: int) -> set[str]:
    s = "".join(text.split())
    if len(s) < n:
        return set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def _longest_common_substring(a: str, b: str) -> tuple[int, str]:
    """返回 (最长公共子串长度, 子串)。空白已压缩。O(len(a)*len(b))。"""
    a = "".join(a.split())
    b = "".join(b.split())
    if not a or not b:
        return 0, ""
    prev = [0] * (len(b) + 1)
    best, best_end = 0, 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
                    best_end = i
        prev = cur
    return best, a[best_end - best : best_end]


@dataclass
class ScanResult:
    passed: bool
    overlap_ratio: float          # 候选 n-gram 命中原文的比例
    lcs_len: int                  # 最长连续公共子串长度
    lcs_sample: str               # 该子串(供人工核查)
    reason: str = ""
    hit_ngrams: list[str] = field(default_factory=list)


def scan(
    candidate: str,
    source: str,
    n: int = 8,
    lcs_threshold: int = 12,
    ratio_threshold: float = 0.15,
) -> ScanResult:
    """比对 candidate(卡片/生成文本)与 source(本地原文)。

    判 fail(疑似抄录)的条件:最长连续公共子串 >= lcs_threshold 字,
    或 n-gram 重叠率 >= ratio_threshold。两者任一触发即不通过。
    """
    cand_grams = _char_ngrams(candidate, n)
    src_grams = _char_ngrams(source, n)
    hit = cand_grams & src_grams
    ratio = len(hit) / len(cand_grams) if cand_grams else 0.0
    lcs_len, lcs_sample = _longest_common_substring(candidate, source)

    fail_lcs = lcs_len >= lcs_threshold
    fail_ratio = ratio >= ratio_threshold
    passed = not (fail_lcs or fail_ratio)

    reasons = []
    if fail_lcs:
        reasons.append(f"最长连续公共子串 {lcs_len} 字(阈值 {lcs_threshold})")
    if fail_ratio:
        reasons.append(f"{n}-gram 重叠率 {ratio:.0%}(阈值 {ratio_threshold:.0%})")

    return ScanResult(
        passed=passed,
        overlap_ratio=ratio,
        lcs_len=lcs_len,
        lcs_sample=lcs_sample,
        reason="；".join(reasons) if reasons else "通过",
        hit_ngrams=sorted(hit)[:20],
    )
