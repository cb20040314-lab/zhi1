"""ASR 服务适配：将上传音频转为文本。

Mock 模式（MOCK_AI=1，默认）：不请求外部服务，按回合轮换返回预置文本。
真实模式（MOCK_AI=0）：调用 OpenAI 兼容的 /audio/transcriptions 接口
（Whisper API、硅基流动、火山方舟等均兼容），密钥从环境变量读取，超时+一次重试。
"""
from __future__ import annotations

import os
import time

import httpx

from .errors import AIServiceError

# Mock 轮换的预置识别文本（配合 LLM Mock 回复使用）
MOCK_TRANSCRIPTS = [
    "我想了解为什么天空是蓝色的",
    "那太阳为什么会升起和落下",
    "你能给我讲一个关于星星的故事吗",
    "为什么月亮有时是弯的",
    "我想知道蜜蜂是怎么采蜜的",
]

_TIMEOUT_S = 60


def _is_mock() -> bool:
    return os.getenv("MOCK_AI", "1") == "1"


def transcribe(audio_bytes: bytes, turn_index: int, *, mime: str = "audio/webm") -> str:
    """入参：音频字节、回合序号（Mock 轮换用）、MIME 类型。返回识别文本。"""
    if _is_mock():
        return MOCK_TRANSCRIPTS[turn_index % len(MOCK_TRANSCRIPTS)]

    api_key = os.getenv("ASR_API_KEY", "")
    base_url = os.getenv("ASR_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("ASR_MODEL", "whisper-1")
    if not api_key:
        raise AIServiceError("CONFIG_ERROR", "ASR_API_KEY 未设置")

    headers = {"Authorization": f"Bearer {api_key}"}
    files = {
        "file": ("audio.webm", audio_bytes, mime or "audio/webm"),
        "model": (None, model),
    }
    # 一次重试：429 限流时等待 1 秒再试；其他失败重试一次后报错
    for attempt in range(2):
        try:
            resp = httpx.post(
                f"{base_url}/audio/transcriptions",
                headers=headers,
                files=files,
                timeout=_TIMEOUT_S,
            )
            if resp.status_code == 429 and attempt == 0:
                time.sleep(1)
                continue
            resp.raise_for_status()
            return (resp.json().get("text") or "").strip()
        except httpx.TimeoutException:
            raise AIServiceError("AI_TIMEOUT", "ASR 请求超时")
        except httpx.HTTPStatusError as e:
            raise AIServiceError("AI_ERROR", f"ASR 请求失败 HTTP {e.response.status_code}")
        except Exception as e:
            raise AIServiceError("AI_ERROR", f"ASR 请求异常: {e}")
    raise AIServiceError("AI_ERROR", "ASR 请求失败（已重试一次）")
