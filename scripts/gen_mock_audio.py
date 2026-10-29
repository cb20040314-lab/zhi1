"""生成 Mock TTS 占位音频（data-contract.md 第 4 节约定）。

用法：python scripts/gen_mock_audio.py [份数]
默认生成 5 份（对应 Mock 回复轮数），输出到 app/static/audio/mock_turn_N.wav。
（注：即使不手动运行，tts.py 在首次调用时也会自动生成占位音频。）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.tts import _gen_placeholder  # noqa: E402

COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 5
OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static", "audio"
)

for n in range(1, COUNT + 1):
    path = os.path.join(OUT_DIR, f"mock_turn_{n}.wav")
    _gen_placeholder(path)
    print(f"生成 {path}")
print(f"完成：{COUNT} 份 Mock 音频")
