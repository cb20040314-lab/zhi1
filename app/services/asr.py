"""ASR 服务适配：将上传音频转为文本。

Mock 模式（MOCK_AI=1，默认）：不请求外部服务，按回合轮换返回预置文本。
真实模式：调用外部 ASR（如 Whisper API / 自建服务），密钥从环境变量读取，
设置超时与一次重试；任何失败抛 AIServiceError，由路由层转为错误码。
"""
from __future__ import annotations

import os

from .errors import AIServiceError

# Mock 轮换的预置识别文本（配合 LLM Mock 回复使用）
MOCK_TRANSCRIPTS = [
    "我想了解为什么天空是蓝色的",
    "那太阳为什么会升起和落下",
    "你能给我讲一个关于星星的故事吗",
    "为什么月亮有时是弯的",
    "我想知道蜜蜂是怎么采蜜的",
]


def _is_mock() -> bool:
    return os.getenv("MOCK_AI", "1") == "1"


def transcribe(audio_bytes: bytes, turn_index: int, *, mime: str = "audio/webm") -> str:
    """入参：音频字节、回合序号（用于 Mock 轮换）、MIME 类型。返回识别文本。"""
    if _is_mock():
        return MOCK_TRANSCRIPTS[turn_index % len(MOCK_TRANSCRIPTS)]

    api_key = os.getenv("ASR_API_KEY", "")
    if not api_key:
        raise AIServiceError("ASR_API_KEY 未设置")
    # ---- 真实 ASR 适配点：调用外部服务，超时+一次重试 ----
    # try:
    #     resp = httpx.post(ASR_URL, headers={"Authorization": f"Bearer {api_key}"},
    #                       files={"audio": ("audio.webm", audio_bytes, mime)}, timeout=10)
    #     resp.raise_for_status()
    #     return resp.json()["text"]
    # except httpx.TimeoutException:
    #     raise AIServiceError("ASR_TIMEOUT")
    # except Exception:
    #     raise AIServiceError("ASR_ERROR")
    raise AIServiceError("ASR_API_KEY 未设置且未实现真实 ASR 适配")
