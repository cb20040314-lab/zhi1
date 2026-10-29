"""TTS 服务适配：把回复文本合成为音频文件，返回可访问的相对 URL。

Mock 模式：返回预置音频（scripts/gen_mock_audio.py 生成的占位 wav），
放在 app/static/audio/ 下，由 FastAPI StaticFiles 提供访问。
真实模式：调用外部 TTS，密钥从环境变量读取（TTS_API_KEY），超时 + 一次重试。
"""
from __future__ import annotations

import os

from .errors import AIServiceError

STATIC_AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "audio"
)


def _is_mock() -> bool:
    return os.getenv("MOCK_AI", "1") == "1"


def synthesize(text: str, turn_no: int) -> str:
    """返回音频相对路径（如 /static/audio/turn_1.wav）。"""
    if _is_mock():
        fname = f"mock_turn_{turn_no}.wav"
        # 若 mock 音频尚未生成，则自动生成一个占位 wav，保证链路可跑
        if not os.path.exists(os.path.join(STATIC_AUDIO_DIR, fname)):
            _gen_placeholder(os.path.join(STATIC_AUDIO_DIR, fname))
        return f"/static/audio/{fname}"

    api_key = os.getenv("TTS_API_KEY", "")
    if not api_key:
        raise AIServiceError("TTS_API_KEY 未设置")

    # ---- 真实 TTS 适配点：调用外部 TTS，保存到 STATIC_AUDIO_DIR 后返回 URL ----
    raise AIServiceError("TTS_API_KEY 未设置且未实现真实 TTS 适配")


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
