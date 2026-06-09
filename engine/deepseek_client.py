"""江南续写引擎 · DeepSeek 客户端 (task 01)

实现 LLMClient 协议的 generate,调用 DeepSeek 官方 API 生成真实续写正文。
DeepSeek API 兼容 OpenAI 格式,使用 requests 直调,不引入重型依赖。
"""
from __future__ import annotations

import os
import time

import requests


class DeepSeekAPIError(Exception):
    """DeepSeek API 调用异常,携带状态码与响应体摘要。"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"DeepSeek API error {status_code}: {detail}")


class DeepSeekClient:
    """DeepSeek API 续写客户端,实现 generate(prompt) -> str。

    构造参数:
        model:      模型名,默认 deepseek-chat（chat 模型,非 reasoner）。
        temperature: 创意写作,默认 0.8。
        timeout:    HTTP 超时秒数。
        max_retries: 指数退避重试次数（含首次共 1+max_retries 次）。
        api_key:    默认 None → 从环境变量 DEEPSEEK_API_KEY 读取。
    """

    BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-chat"

    SYSTEM_PROMPT = (
        "你是中文小说续写助手,严格遵循随后给出的写作协议与记忆,"
        "只输出续写正文,不复制任何已有作品的原文句子。"
    )

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.8,
        timeout: int = 60,
        max_retries: int = 2,
        api_key: str | None = None,
    ):
        self.model = model or self.DEFAULT_MODEL
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self._api_key = api_key

    # ── api_key 延迟读取 ──────────────────────────────
    @property
    def api_key(self) -> str:
        if self._api_key:
            return self._api_key
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError(
                "未设置 DEEPSEEK_API_KEY。请设置环境变量后重试:\n"
                "  $env:DEEPSEEK_API_KEY = 'sk-...'  (PowerShell)\n"
                "  export DEEPSEEK_API_KEY=sk-...   (Bash)"
            )
        return key

    # ── 核心:generate ─────────────────────────────────
    def generate(self, prompt: str, **kwargs) -> str:
        """调用 DeepSeek chat/completions,返回续写正文。

        prompt 中已含 江南.skill 写作协议、preset、前情记忆与意图,
        此处作为 user message 原样传入。
        """
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": False,
        }

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]

                # ── 非 200 ──
                summary = _truncate(resp.text, 300)
                if resp.status_code == 429:
                    if attempt < self.max_retries:
                        delay = 2**attempt
                        time.sleep(delay)
                        continue
                raise DeepSeekAPIError(resp.status_code, summary)

            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = 2**attempt
                    time.sleep(delay)
                    continue

        raise DeepSeekAPIError(0, str(last_exc)) from last_exc


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len] + "..."
