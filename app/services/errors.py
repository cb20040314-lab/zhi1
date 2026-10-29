"""错误类型与统一错误码（docs/data-contract.md 第 3.7 节）。"""
from __future__ import annotations


class AIServiceError(Exception):
    """AI 服务（ASR/LLM/TTS）调用失败；携带错误码，默认 AI_ERROR。"""

    def __init__(self, code: str = "AI_ERROR", message: str = "AI 服务错误"):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
