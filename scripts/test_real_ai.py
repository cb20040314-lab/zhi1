"""真实 AI 链路单项测试：直接调用 services 模块验证 ASR/LLM/TTS 三个真实接口。

用法：python scripts/test_real_ai.py
退出码 0 = 三项全部通过（LLM 需返回有效文本、TTS 需生成音频文件；
ASR 用正弦波占位音频，识别文本可为空，只要接口返回 200 即算链路通）。
"""
from __future__ import annotations

import io
import math
import os
import struct
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 先加载 .env（与 app.main 一致）
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

os.environ["MOCK_AI"] = "0"

from app.services import asr, llm, tts  # noqa: E402


def make_wav(seconds: float = 1.0, freq: int = 440) -> bytes:
    rate = 8000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * seconds)):
            v = int(12000 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def step(name: str, ok: bool, extra: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' - ' + extra) if extra else ''}")
    if not ok:
        sys.exit(1)


def main() -> None:
    print(f"== 真实 AI 链路测试 (MOCK_AI=0) ==")
    print(f"   LLM: {os.getenv('LLM_BASE_URL')} / {os.getenv('LLM_MODEL')}")
    print(f"   ASR: {os.getenv('ASR_BASE_URL')} / {os.getenv('ASR_MODEL')}")
    print(f"   TTS: {os.getenv('TTS_BASE_URL')} / {os.getenv('TTS_MODEL')}")

    # 1. LLM
    try:
        reply = llm.generate_reply("为什么天空是蓝色的？", [], 0)
        step("LLM 对话", bool(reply and len(reply) > 5), f"回复: {reply[:60]}...")
    except Exception as e:
        step("LLM 对话", False, str(e))

    # 2. TTS（先生成音频，再测 ASR 用同一段文本）
    try:
        url = tts.synthesize("你好，小朋友，我们来学点有趣的知识吧", 1)
        # 音频写在 app/static/audio 下：url 形如 /static/audio/xxx，对应 app + url
        fpath = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app",
            url.lstrip("/"),
        )
        size = os.path.getsize(fpath) if os.path.exists(fpath) else 0
        step("TTS 合成", url.startswith("/static/audio/") and size > 0,
             f"{url} ({size} bytes)")
    except Exception as e:
        step("TTS 合成", False, str(e))

    # 3. ASR（占位正弦波；接口 200 即链路通，识别文本允许为空）
    try:
        text = asr.transcribe(make_wav(), 0, mime="audio/wav")
        step("ASR 识别", True, f"返回文本: {text[:40]!r}（正弦波无语义，链路通即可）")
    except Exception as e:
        step("ASR 识别", False, str(e))

    print("== 真实链路测试完成 ==")


if __name__ == "__main__":
    main()
