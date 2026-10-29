"""TTS 服务适配：把回复文本合成为音频文件，返回可访问的相对 URL。

Mock 模式：返回预置占位 wav（app/static/audio/），由 FastAPI StaticFiles 提供访问。
真实模式（MOCK_AI=0）：调用 OpenAI 兼容的 /audio/speech 接口
（OpenAI TTS、硅基流动、火山方舟等均兼容），保存为 .mp3 后返回 URL。
密钥从环境变量读取（TTS_API_KEY），固定超时 + 一次重试。
"""
from __future__ import annotations

import os
import time

import httpx

from .errors import AIServiceError

STATIC_AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "audio"
)

_TIMEOUT_S = 90


def _is_mock() -> bool:
    return os.getenv("MOCK_AI", "1") == "1"


def synthesize(text: str, turn_no: int) -> str:
    """返回音频相对路径（真实模式 /static/audio/turn_{n}.mp3；Mock 为 wav）。"""
    if _is_mock():
        fname = f"mock_turn_{turn_no}.wav"
        # 若 mock 音频尚未生成，则自动生成一个占位 wav，保证链路可跑
        if not os.path.exists(os.path.join(STATIC_AUDIO_DIR, fname)):
            _gen_placeholder(os.path.join(STATIC_AUDIO_DIR, fname))
        return f"/static/audio/{fname}"

    api_key = os.getenv("TTS_API_KEY", "")
    base_url = os.getenv("TTS_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("TTS_MODEL", "tts-1")
    voice = os.getenv("TTS_VOICE", "alloy")
    if not api_key:
        raise AIServiceError("CONFIG_ERROR", "TTS_API_KEY 未设置")

    payload = {"model": model, "input": text, "voice": voice}
    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(2):
        try:
            resp = httpx.post(
                f"{base_url}/audio/speech",
                headers=headers,
                json=payload,
                timeout=_TIMEOUT_S,
            )
            if resp.status_code == 429 and attempt == 0:
                time.sleep(1)
                continue
            resp.raise_for_status()
            os.makedirs(STATIC_AUDIO_DIR, exist_ok=True)
            fname = f"turn_{turn_no}.mp3"
            with open(os.path.join(STATIC_AUDIO_DIR, fname), "wb") as f:
                f.write(resp.content)
            return f"/static/audio/{fname}"
        except httpx.TimeoutException:
            raise AIServiceError("AI_TIMEOUT", "TTS 请求超时")
        except httpx.HTTPStatusError as e:
            raise AIServiceError("AI_ERROR", f"TTS 请求失败 HTTP {e.response.status_code}")
        except Exception as e:
            raise AIServiceError("AI_ERROR", f"TTS 请求异常: {e}")
    raise AIServiceError("AI_ERROR", "TTS 请求失败（已重试一次）")


def _gen_placeholder(path: str, seconds: float = 1.0) -> None:
    """生成 1 秒 220Hz 正弦波占位 wav（证明音频链路可用，演示时由真实 TTS 覆盖）。"""
    import math
    import struct
    import wave

    rate = 8000
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * seconds)):
            v = int(12000 * math.sin(2 * math.pi * 220 * i / rate))
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))
